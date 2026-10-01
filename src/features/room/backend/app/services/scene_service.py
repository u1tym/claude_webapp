from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any

from app.errors import DeviceOperationError, NotFoundError
from app.logger import write
from app.services import device_service
from app.services.device_service import (
    BEDSIDE_SPEAKER,
    CEILING_LIGHT,
    INDIRECT_LIGHT,
    INDOOR_SPEAKER,
    StateSnapshot,
)
from app.switchbot.client import SwitchBotApi
from app.timeutil import iso_seconds

# 一括切替の定義: 一括切替 → (機器, 目標の状態) の並び。玄関ドアはどの一括切替にも含めない
SCENES: dict[str, tuple[tuple[str, str], ...]] = {
    "indoor_speaker": ((INDOOR_SPEAKER, "on"), (BEDSIDE_SPEAKER, "off")),
    "bedside_speaker": ((INDOOR_SPEAKER, "off"), (BEDSIDE_SPEAKER, "on")),
    "ceiling_light": ((CEILING_LIGHT, "on"), (INDIRECT_LIGHT, "off")),
    "indirect_light": ((CEILING_LIGHT, "off"), (INDIRECT_LIGHT, "on")),
    "out": (
        (CEILING_LIGHT, "off"),
        (INDIRECT_LIGHT, "off"),
        (INDOOR_SPEAKER, "off"),
        (BEDSIDE_SPEAKER, "off"),
    ),
}

SUCCESS = "success"
FAILURE = "failure"
SKIPPED = "skipped"
PARTIAL = "partial"


@dataclass(frozen=True)
class DeviceOutcome:
    device: str
    target: str
    outcome: str  # success / failure / skipped

    def to_dict(self) -> dict[str, str]:
        return {"device": self.device, "target": self.target, "outcome": self.outcome}


@dataclass(frozen=True)
class SceneResult:
    scene: str
    outcome: str  # success / partial / failure
    results: tuple[DeviceOutcome, ...]
    snapshot: StateSnapshot | None  # 再取得しない（定期実行）ときは None

    def to_dict(self) -> dict[str, Any]:
        assert self.snapshot is not None
        return {
            "scene": self.scene,
            "outcome": self.outcome,
            "results": [r.to_dict() for r in self.results],
            "fetched_at": iso_seconds(self.snapshot.fetched_at),
            "devices": self.snapshot.devices,
        }


def overall_outcome(results: tuple[DeviceOutcome, ...]) -> str:
    """指示した機器（skipped を除く）の成否から、全体の結果を決める。"""
    executed = [r.outcome for r in results if r.outcome != SKIPPED]
    if all(o == SUCCESS for o in executed):
        return SUCCESS
    if all(o == FAILURE for o in executed):
        return FAILURE
    return PARTIAL


def run_scene(
    scene: str,
    actor: str,
    username: str = "",
    client: SwitchBotApi | None = None,
    refetch: bool = True,
) -> SceneResult:
    """一括切替を実行する。

    対象の機器へ個別の指示を並行して行い、機器ごとの成否を集める。成功した機器は元に戻さない。
    電灯は未実装のため指示せず skipped とする。玄関ドアは変えない。
    実行のあとに、全機器の状態を取得し直して返す（refetch=False なら取得し直さない）。
    指示は 1 回だけで、再試行しない。
    """
    write("INF", f"一括切替要求 scene={scene} 主体={actor} username={username}")
    targets = SCENES.get(scene)
    if targets is None:
        write("WRN", f"一括切替失敗 scene={scene} 理由=一括切替が存在しない")
        raise NotFoundError()

    cfg = device_service.load_config()
    active = client if client is not None else device_service.build_client(cfg)

    def run_one(device: str, target: str) -> DeviceOutcome:
        if device == CEILING_LIGHT:
            write("INF", f"一括切替 scene={scene} device={device} target={target} 判断=未実装のため何も指示しない")
            return DeviceOutcome(device, target, SKIPPED)
        command = device_service.command_for(device, target)
        assert command is not None  # 定義の目標は、その機器で取り得る値だけ
        try:
            device_service.send_switch(active, cfg, device, target, command, actor)
        except DeviceOperationError:
            # 失敗の理由は send_switch がログに残している
            write("WRN", f"一括切替 scene={scene} device={device} target={target} 主体={actor} 結果=failure")
            return DeviceOutcome(device, target, FAILURE)
        write("INF", f"一括切替 scene={scene} device={device} target={target} 主体={actor} 結果=success")
        return DeviceOutcome(device, target, SUCCESS)

    with ThreadPoolExecutor(max_workers=len(targets)) as pool:
        futures = [pool.submit(run_one, device, target) for device, target in targets]
        results = tuple(f.result() for f in futures)

    outcome = overall_outcome(results)
    detail = " ".join(f"{r.device}={r.outcome}" for r in results)
    level = "INF" if outcome == SUCCESS else "WRN"
    write(level, f"一括切替結果 scene={scene} 主体={actor} 全体={outcome} {detail}")

    snapshot = device_service.fetch_states(active) if refetch else None
    return SceneResult(scene=scene, outcome=outcome, results=results, snapshot=snapshot)
