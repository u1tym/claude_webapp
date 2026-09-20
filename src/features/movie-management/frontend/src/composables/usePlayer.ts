// 動画再生の共通の仕組み（単独再生・プレイリスト再生で共有する）。
//
// 動画要素に配信 URL を直接指定し、必要な範囲の取得と位置の移動はブラウザに任せる。
// この仕組みが担うのは、開始・再生位置の保存・次の動画（前の動画）への移動・終了時の遷移・失敗の表示。

import { onBeforeUnmount, ref, type Ref } from "vue";
import { errorMessage, streamUrl } from "../api";
import { HEVC_PLAYBACK_ERROR } from "../utils/mp4Codec";

export type PlayItem = {
  videoId: number;
  /** プレイリストの項目の識別子（単独再生では null） */
  itemId: number | null;
  title: string;
  durationMs: number;
  positionMs: number;
  /** 動画が再生できる状態か（登録中・エラーは false） */
  playable: boolean;
  hasNext: boolean;
  hasPrev: boolean;
};

/** 再生の対象（単独の動画、またはプレイリスト）ごとの、サーバとのやり取り。 */
export type PlayerBackend = {
  start(resume: boolean): Promise<PlayItem>;
  next(current: PlayItem): Promise<PlayItem | null>;
  prev(current: PlayItem): Promise<PlayItem | null>;
  save(current: PlayItem, positionMs: number, completed: boolean, keepalive: boolean): Promise<void>;
};

export type PlayerPhase = "idle" | "loading" | "ready" | "error" | "finished";

const SAVE_INTERVAL_MS = 10_000;
const LOAD_TIMEOUT_MS = 120_000;
export const SKIP_MS = 10_000;

function mediaErrorMessage(video: HTMLVideoElement): string {
  switch (video.error?.code) {
    case MediaError.MEDIA_ERR_NETWORK:
      return "動画の取得に失敗しました（ネットワークまたは認証）";
    case MediaError.MEDIA_ERR_DECODE:
    case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
      return `動画の形式が再生できません。${HEVC_PLAYBACK_ERROR}`;
    default:
      return "動画の読み込みに失敗しました";
  }
}

export function usePlayer(backend: PlayerBackend, onItemChange?: (item: PlayItem) => void) {
  const videoEl: Ref<HTMLVideoElement | null> = ref(null);
  const stageEl: Ref<HTMLElement | null> = ref(null);

  const item = ref<PlayItem | null>(null);
  const phase = ref<PlayerPhase>("idle");
  const error = ref("");
  const playing = ref(false);
  const buffering = ref(false);
  const currentMs = ref(0);

  let session = 0;
  let saveTimer: number | null = null;
  let listening: HTMLVideoElement | null = null;

  // ---- 位置の保存 ----------------------------------------------------------

  async function saveNow(completed: boolean, keepalive = false): Promise<void> {
    const current = item.value;
    const video = videoEl.value;
    if (!current || !video || !current.playable || phase.value === "loading" || phase.value === "error") {
      return;
    }
    const raw = completed ? current.durationMs : Math.round(video.currentTime * 1000);
    const positionMs = Math.min(Math.max(0, raw), current.durationMs);
    try {
      await backend.save(current, positionMs, completed, keepalive);
    } catch {
      // 保存に失敗しても再生は止めない
    }
  }

  function stopTimer(): void {
    if (saveTimer !== null) {
      window.clearInterval(saveTimer);
      saveTimer = null;
    }
  }

  function startTimer(): void {
    stopTimer();
    saveTimer = window.setInterval(() => {
      if (playing.value) {
        void saveNow(false);
      }
    }, SAVE_INTERVAL_MS);
  }

  // ---- 読み込み ------------------------------------------------------------

  function waitForMetadata(video: HTMLVideoElement): Promise<void> {
    return new Promise((resolve, reject) => {
      if (video.readyState >= HTMLMediaElement.HAVE_METADATA) {
        resolve();
        return;
      }
      const timer = window.setTimeout(() => {
        cleanup();
        reject(new Error("動画の読み込みがタイムアウトしました"));
      }, LOAD_TIMEOUT_MS);
      const onLoaded = (): void => {
        cleanup();
        resolve();
      };
      const onFail = (): void => {
        cleanup();
        reject(new Error(mediaErrorMessage(video)));
      };
      const cleanup = (): void => {
        window.clearTimeout(timer);
        video.removeEventListener("loadedmetadata", onLoaded);
        video.removeEventListener("error", onFail);
      };
      video.addEventListener("loadedmetadata", onLoaded);
      video.addEventListener("error", onFail);
    });
  }

  function detachSource(): void {
    const video = videoEl.value;
    if (video) {
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
    playing.value = false;
    buffering.value = false;
  }

  function fail(message: string): void {
    stopTimer();
    phase.value = "error";
    error.value = message;
    buffering.value = false;
  }

  async function load(next: PlayItem): Promise<void> {
    const mine = ++session;
    stopTimer();
    item.value = next;
    onItemChange?.(next);
    error.value = "";
    currentMs.value = next.positionMs;
    if (!next.playable) {
      detachSource();
      fail("再生できない動画です（登録中またはエラーの動画は再生できません）");
      return;
    }
    const video = videoEl.value;
    if (!video) {
      return;
    }
    phase.value = "loading";
    video.src = streamUrl(next.videoId);
    video.load();
    try {
      await waitForMetadata(video);
    } catch (e) {
      if (mine === session) {
        fail(e instanceof Error ? e.message : "動画の読み込みに失敗しました");
      }
      return;
    }
    if (mine !== session) {
      return;
    }
    if (next.positionMs > 0) {
      video.currentTime = next.positionMs / 1000;
    }
    phase.value = "ready";
    try {
      await video.play();
    } catch {
      // 自動再生が許可されない環境では、一時停止のまま表示する（操作部から再生できる）
    }
    if (mine === session) {
      startTimer();
    }
  }

  /** 再生を開始する。resume が true なら前回の位置から。 */
  async function begin(resume: boolean): Promise<void> {
    const mine = ++session;
    stopTimer();
    phase.value = "loading";
    error.value = "";
    try {
      const first = await backend.start(resume);
      if (mine !== session) {
        return; // 開始の応答を待つ間に、別の操作（画面の切り替えなど）があった
      }
      await load(first);
    } catch (e) {
      fail(errorMessage(e, "再生を開始できませんでした"));
    }
  }

  /** 前後の動画へ移る。saveFirst: 移る前に、今の位置を保存する（再生終了後は保存済みのため false）。 */
  async function move(direction: "next" | "prev", saveFirst = true): Promise<void> {
    const current = item.value;
    if (!current || (direction === "next" ? !current.hasNext : !current.hasPrev)) {
      return;
    }
    if (saveFirst) {
      await saveNow(false);
    }
    try {
      const target = direction === "next" ? await backend.next(current) : await backend.prev(current);
      if (target) {
        await load(target);
      } else if (direction === "next") {
        finish();
      }
    } catch (e) {
      fail(errorMessage(e, "移動できませんでした"));
    }
  }

  function finish(): void {
    stopTimer();
    phase.value = "finished";
    playing.value = false;
  }

  async function onEnded(): Promise<void> {
    await saveNow(true);
    const current = item.value;
    if (current?.hasNext) {
      await move("next", false);
    } else {
      finish();
    }
  }

  // ---- 操作 ----------------------------------------------------------------

  function togglePlay(): void {
    const video = videoEl.value;
    if (!video || phase.value !== "ready") {
      return;
    }
    if (video.paused) {
      void video.play().catch(() => undefined);
    } else {
      video.pause();
    }
  }

  function seekTo(ms: number): void {
    const video = videoEl.value;
    const current = item.value;
    if (!video || !current) {
      return;
    }
    const clamped = Math.min(Math.max(0, ms), current.durationMs);
    video.currentTime = clamped / 1000;
    currentMs.value = clamped;
  }

  const skip = (deltaMs: number): void => seekTo((videoEl.value?.currentTime ?? 0) * 1000 + deltaMs);

  // ---- 動画要素との結び付け -----------------------------------------------------

  const listeners: [string, () => void][] = [];

  function attach(video: HTMLVideoElement): void {
    detach();
    videoEl.value = video;
    listening = video;
    const on = (name: string, handler: () => void): void => {
      video.addEventListener(name, handler);
      listeners.push([name, handler]);
    };
    on("timeupdate", () => {
      currentMs.value = Math.round(video.currentTime * 1000);
    });
    on("play", () => {
      playing.value = true;
    });
    on("pause", () => {
      playing.value = false;
      if (!video.ended && phase.value === "ready") {
        void saveNow(false);
      }
    });
    on("waiting", () => {
      buffering.value = true;
    });
    on("playing", () => {
      buffering.value = false;
    });
    on("canplay", () => {
      buffering.value = false;
    });
    on("seeked", () => {
      if (phase.value === "ready") {
        void saveNow(false);
      }
    });
    on("ended", () => {
      void onEnded();
    });
    on("error", () => {
      if (phase.value !== "loading" && video.getAttribute("src")) {
        fail(mediaErrorMessage(video));
      }
    });
  }

  function detach(): void {
    if (listening) {
      for (const [name, handler] of listeners) {
        listening.removeEventListener(name, handler);
      }
    }
    listeners.length = 0;
    listening = null;
  }

  const onPageHide = (): void => {
    if (playing.value) {
      void saveNow(false, true);
    }
  };
  window.addEventListener("pagehide", onPageHide);

  /** 画面を離れるとき: 位置を保存して、動画の取得を止める。 */
  function dispose(): void {
    window.removeEventListener("pagehide", onPageHide);
    session += 1;
    stopTimer();
    void saveNow(false, true);
    detachSource();
    detach();
  }

  onBeforeUnmount(dispose);

  return {
    videoEl,
    stageEl,
    item,
    phase,
    error,
    playing,
    buffering,
    currentMs,
    attach,
    begin,
    load,
    togglePlay,
    seekTo,
    skip,
    next: () => move("next"),
    prev: () => move("prev"),
    restart: () => begin(false),
  };
}

export type Player = ReturnType<typeof usePlayer>;
