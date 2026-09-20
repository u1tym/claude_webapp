import { onBeforeUnmount, onMounted, ref } from "vue";

type WebkitVideo = HTMLVideoElement & { webkitEnterFullscreen?: () => void };

/** ステージ（動画と操作部）を全画面にする。要素の全画面に対応しない端末（iPhone の Safari）は、動画の全画面にする。 */
export function useFullscreen() {
  const isFullscreen = ref(false);

  const onChange = (): void => {
    isFullscreen.value = document.fullscreenElement !== null;
  };

  onMounted(() => document.addEventListener("fullscreenchange", onChange));
  onBeforeUnmount(() => {
    document.removeEventListener("fullscreenchange", onChange);
    if (document.fullscreenElement) {
      void document.exitFullscreen().catch(() => undefined);
    }
  });

  async function toggle(stage: HTMLElement | null, video: HTMLVideoElement | null): Promise<void> {
    if (document.fullscreenElement) {
      await document.exitFullscreen().catch(() => undefined);
      return;
    }
    if (stage && stage.requestFullscreen) {
      await stage.requestFullscreen().catch(() => undefined);
      return;
    }
    (video as WebkitVideo | null)?.webkitEnterFullscreen?.();
  }

  return { isFullscreen, toggle };
}
