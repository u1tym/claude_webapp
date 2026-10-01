from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.config import Config, load_config
from app.errors import DeviceOperationError, InvalidInputError, NotFoundError
from app.logger import write
from app.switchbot.client import SwitchBotApi, SwitchBotClient, SwitchBotError
from app.timeutil import iso_seconds, now_jst

# 機器のキー（API の `device`）
CEILING_LIGHT = "ceiling_light"
INDIRECT_LIGHT = "indirect_light"
INDOOR_SPEAKER = "indoor_speaker"
BEDSIDE_SPEAKER = "bedside_speaker"
FRONT_DOOR = "front_door"

DEVICE_KEYS: tuple[str, ...] = (
    CEILING_LIGHT,
    INDIRECT_LIGHT,
    INDOOR_SPEAKER,
    BEDSIDE_SPEAKER,
    FRONT_DOOR,
)

# SwitchBot へ問い合わせる機器（電灯は未実装のため含めない）
_PLUG_KEYS: tuple[str, ...] = (INDIRECT_LIGHT, INDOOR_SPEAKER, BEDSIDE_SPEAKER)
_QUERY_KEYS: tuple[str, ...] = (*_PLUG_KEYS, FRONT_DOOR)

DeviceState = dict[str, Any]

# 切替のあと、実機の反映を待つ間隔（秒）。上限は設定値 ROOM_SETTLE_SECONDS
SETTLE_INTERVAL_SECONDS = 1.5


def _sleep(seconds: float) -> None:
    """待つ。テストでは、実際には待たないよう差し替える。"""
    time.sleep(seconds)


def settle_step(waited: float, limit: float) -> float:
    """次に待つ秒数。上限（limit）までの残りが、間隔より短ければ、その残りだけ待つ。上限なら 0。"""
    return max(0.0, min(SETTLE_INTERVAL_SECONDS, limit - waited))


@dataclass(frozen=True)
class StateSnapshot:
    """5 機器の状態と取得日時。"""

    fetched_at: datetime
    devices: dict[str, DeviceState]

    def to_dict(self) -> dict[str, Any]:
        return {"fetched_at": iso_seconds(self.fetched_at), "devices": self.devices}


def device_id_for(cfg: Config, device: str) -> str:
    """機器のキーから SwitchBot の機器識別子を引く（コード・応答・ログに出さない）。"""
    mapping = {
        INDIRECT_LIGHT: cfg.device_indirect_light_id,
        INDOOR_SPEAKER: cfg.device_indoor_speaker_id,
        BEDSIDE_SPEAKER: cfg.device_bedside_speaker_id,
        FRONT_DOOR: cfg.device_front_door_id,
    }
    return mapping.get(device, "")


def build_client(cfg: Config | None = None) -> SwitchBotApi | None:
    """設定から SwitchBot のクライアントを作る。認証情報が未設定なら None。"""
    cfg = cfg or load_config()
    if not cfg.switchbot_token or not cfg.switchbot_secret:
        return None
    return SwitchBotClient(cfg.switchbot_token, cfg.switchbot_secret, cfg.switchbot_timeout_seconds)


def error_state(device: str) -> DeviceState:
    """取得できなかった機器の状態。状態を推測した値は返さない。"""
    state: DeviceState = {"status": "error", "state": None}
    if device == FRONT_DOOR:
        state["battery"] = None
    return state


def ceiling_light_state() -> DeviceState:
    """電灯は未実装のため、常に OFF を返す。"""
    return {"status": "ok", "state": "off", "implemented": False}


def _parse_plug(body: dict[str, Any]) -> DeviceState:
    power = body.get("power")
    if power in ("on", "off"):
        return {"status": "ok", "state": power}
    raise ValueError("電源の状態が想定外の値")


def _parse_lock(body: dict[str, Any]) -> DeviceState:
    lock_state = body.get("lockState")
    # locked / unlocked 以外（施錠が不完全な状態など）は取得エラーとして扱う
    if lock_state not in ("locked", "unlocked"):
        raise ValueError("施錠の状態が想定外の値")
    battery = body.get("battery")
    if isinstance(battery, bool) or not isinstance(battery, int) or not 0 <= battery <= 100:
        battery = None
    return {"status": "ok", "state": lock_state, "battery": battery}


def read_device(client: SwitchBotApi, cfg: Config, device: str) -> DeviceState:
    """1 機器の状態を SwitchBot から取得する。失敗は error の状態にして返す（例外にしない）。"""
    device_id = device_id_for(cfg, device)
    if not device_id:
        write("ERR", f"状態取得失敗 device={device} 理由=機器の識別子が未設定")
        return error_state(device)
    try:
        body = client.get_status(device_id)
        parsed = _parse_lock(body) if device == FRONT_DOOR else _parse_plug(body)
    except SwitchBotError as exc:
        write("WRN", f"状態取得失敗 device={device} 理由={exc}")
        return error_state(device)
    except ValueError as exc:
        write("WRN", f"状態取得失敗 device={device} 理由={exc}")
        return error_state(device)
    return parsed


@dataclass(frozen=True)
class SwitchResult:
    """個別切替の結果。applied は機器へ指示を送ったか（電灯は False）。"""

    device: str
    applied: bool
    fetched_at: datetime
    result: DeviceState

    def to_dict(self) -> dict[str, Any]:
        return {
            "device": self.device,
            "applied": self.applied,
            "fetched_at": iso_seconds(self.fetched_at),
            "result": self.result,
        }


# 機器ごとの「取り得る目標の状態 → SwitchBot のコマンド」
_ON_OFF_COMMANDS = {"on": "turnOn", "off": "turnOff"}
_LOCK_COMMANDS = {"locked": "lock", "unlocked": "unlock"}


def command_for(device: str, target: str) -> str | None:
    """目標の状態を SwitchBot のコマンドにする。その機器で取り得ない値なら None。"""
    table = _LOCK_COMMANDS if device == FRONT_DOOR else _ON_OFF_COMMANDS
    return table.get(target)


def send_switch(
    active: SwitchBotApi | None,
    cfg: Config,
    device: str,
    target: str,
    command: str,
    actor: str,
) -> None:
    """SwitchBot へ指示を 1 回だけ送る（再試行しない）。失敗は DeviceOperationError にする。"""
    device_id = device_id_for(cfg, device)
    if active is None or not device_id:
        write("ERR", f"機器切替失敗 device={device} target={target} 理由=SwitchBot の設定が未完了")
        raise DeviceOperationError()
    try:
        active.send_command(device_id, command)
    except SwitchBotError as exc:
        write("ERR", f"機器切替失敗 device={device} target={target} 主体={actor} 理由={exc}")
        raise DeviceOperationError() from None


def read_settled(
    active: SwitchBotApi | None, cfg: Config, device: str, target: str
) -> tuple[DeviceState, int]:
    """指示のあと、実機の反映を待ちながら、目標の状態になるまで状態を取り直す。

    間隔（SETTLE_INTERVAL_SECONDS）をおいて取得し、目標の状態になったら、そこで返す。
    待った合計が上限（cfg.switch_settle_seconds）に達しても、ならなければ、最後の値を返す。
    取得できなかった（error）ときも、上限まで取り直す。上限が 0 なら、待たずに 1 回だけ取得する。
    """
    limit = cfg.switch_settle_seconds
    waited = 0.0
    reads = 0
    while True:
        step = settle_step(waited, limit)
        if step > 0:
            _sleep(step)
            waited += step
        result = read_device(active, cfg, device)
        reads += 1
        if (result["status"] == "ok" and result["state"] == target) or waited >= limit:
            return result, reads


def switch_device(
    device: str,
    target: str | None,
    actor: str,
    username: str = "",
    client: SwitchBotApi | None = None,
) -> SwitchResult:
    """1 機器を目標の状態に切り替える。

    「反転」は受けず、目標の状態を必ず明示させる。指示は 1 回だけ行い、再試行しない。
    電灯は未実装のため、機器へ何も指示せず OFF を返す。成功したら、その機器の状態を取得し直して返す。
    """
    write("INF", f"機器切替要求 device={device} target={target} 主体={actor} username={username}")
    if device not in DEVICE_KEYS:
        write("WRN", f"機器切替失敗 device={device} 理由=機器が存在しない")
        raise NotFoundError()
    command = command_for(device, target) if target is not None else None
    if command is None:
        write("WRN", f"機器切替失敗 device={device} target={target} 理由=その機器で取り得ない状態")
        raise InvalidInputError()

    if device == CEILING_LIGHT:
        write("INF", f"機器切替 device={device} target={target} 判断=未実装のため何も指示しない")
        return SwitchResult(device, False, now_jst(), ceiling_light_state())

    cfg = load_config()
    active = client if client is not None else build_client(cfg)
    send_switch(active, cfg, device, target, command, actor)

    # 指示のあとに状態を取得し直す。実機の反映が遅れるため、目標の状態になるまで、
    # 間隔をおいて取り直す（上限は設定値）。食い違ったままなら、最後に取得した値を返す
    result, reads = read_settled(active, cfg, device, target)
    outcome = result.get("state")
    write(
        "INF",
        f"機器切替成功 device={device} target={target} 主体={actor} 取得した状態={outcome} 取得回数={reads}",
    )
    if result["status"] == "ok" and outcome != target:
        write("WRN", f"機器切替の結果が目標と異なる device={device} target={target} 取得した状態={outcome}")
    return SwitchResult(device, True, now_jst(), result)


def fetch_states(client: SwitchBotApi | None = None) -> StateSnapshot:
    """5 機器の状態を取得する。電灯を除く 4 機器を並行して SwitchBot へ問い合わせる。

    ある機器の取得に失敗しても他は続け、失敗した機器は error とする。キャッシュしない。
    """
    cfg = load_config()
    active = client if client is not None else build_client(cfg)

    devices: dict[str, DeviceState] = {CEILING_LIGHT: ceiling_light_state()}
    if active is None:
        write("ERR", "状態取得失敗 理由=SwitchBot の認証情報が未設定")
        for key in _QUERY_KEYS:
            devices[key] = error_state(key)
    else:
        with ThreadPoolExecutor(max_workers=len(_QUERY_KEYS)) as pool:
            futures = {key: pool.submit(read_device, active, cfg, key) for key in _QUERY_KEYS}
            for key in _QUERY_KEYS:
                devices[key] = futures[key].result()

    snapshot = StateSnapshot(
        fetched_at=now_jst(),
        devices={key: devices[key] for key in DEVICE_KEYS},
    )
    failed = [key for key in _QUERY_KEYS if snapshot.devices[key]["status"] == "error"]
    write("INF", f"状態取得 成功={len(_QUERY_KEYS) - len(failed)} 失敗={len(failed)}")
    return snapshot
