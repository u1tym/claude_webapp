// 選んだ動画ファイルから、再生時間の取得とサムネイル画像の生成をする（ブラウザ内で完結する）。

export const MAX_DURATION_MS = 14_400_000; // 約 4 時間

const LOAD_TIMEOUT_MS = 20_000;

function openVideo(file: File): { video: HTMLVideoElement; release: () => void } {
  const url = URL.createObjectURL(file);
  const video = document.createElement("video");
  video.preload = "auto";
  video.muted = true;
  video.playsInline = true;
  video.src = url;
  return {
    video,
    release: () => {
      video.removeAttribute("src");
      video.load();
      URL.revokeObjectURL(url);
    },
  };
}

function waitFor(video: HTMLVideoElement, eventName: "loadedmetadata" | "loadeddata" | "seeked"): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = window.setTimeout(() => {
      cleanup();
      reject(new Error("動画の読み込みがタイムアウトしました"));
    }, LOAD_TIMEOUT_MS);
    const onDone = (): void => {
      cleanup();
      resolve();
    };
    const onError = (): void => {
      cleanup();
      reject(new Error("動画を読み込めませんでした"));
    };
    const cleanup = (): void => {
      window.clearTimeout(timer);
      video.removeEventListener(eventName, onDone);
      video.removeEventListener("error", onError);
    };
    video.addEventListener(eventName, onDone);
    video.addEventListener("error", onError);
  });
}

/** 動画ファイルの再生時間（ミリ秒）。 */
export async function readDurationMs(file: File): Promise<number> {
  const { video, release } = openVideo(file);
  try {
    await waitFor(video, "loadedmetadata");
    const seconds = video.duration;
    if (!Number.isFinite(seconds) || seconds <= 0) {
      throw new Error("動画の長さを取得できませんでした");
    }
    return Math.max(1, Math.round(seconds * 1000));
  } finally {
    release();
  }
}

export type GeneratedThumbnail = { blob: Blob; width: number; height: number };

const THUMBNAIL_WIDTH = 320;

/** 5 秒地点（5 秒未満の動画は先頭のフレーム）からサムネイル画像を作る。 */
export async function generateThumbnail(file: File, durationMs: number): Promise<GeneratedThumbnail> {
  const { video, release } = openVideo(file);
  try {
    await waitFor(video, "loadeddata");
    const target = durationMs >= 5000 ? 5 : 0;
    if (target > 0) {
      const seeked = waitFor(video, "seeked");
      video.currentTime = target;
      await seeked;
    }
    const sourceWidth = video.videoWidth || THUMBNAIL_WIDTH;
    const sourceHeight = video.videoHeight || Math.round((THUMBNAIL_WIDTH * 9) / 16);
    const width = Math.min(THUMBNAIL_WIDTH, sourceWidth);
    const height = Math.max(1, Math.round((sourceHeight * width) / sourceWidth));
    const canvas = document.createElement("canvas");
    canvas.width = width;
    canvas.height = height;
    const context = canvas.getContext("2d");
    if (!context) {
      throw new Error("サムネイルを作れませんでした");
    }
    context.drawImage(video, 0, 0, width, height);
    const blob = await new Promise<Blob | null>((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.8));
    if (!blob) {
      throw new Error("サムネイルを作れませんでした");
    }
    return { blob, width, height };
  } finally {
    release();
  }
}
