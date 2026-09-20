import { onBeforeUnmount, ref, type Ref } from "vue";

const IDLE_MS = 3000;

/**
 * 再生中に一定時間（3 秒）操作がないと、操作部を隠す。
 * 一時停止中、および操作部を操作している間は隠さない。ホバーに依存しない（タップでも再表示できる）。
 */
export function useControlsAutoHide(playing: Ref<boolean>) {
  const visible = ref(true);
  let timer: number | null = null;
  let pinned = false;

  function clear(): void {
    if (timer !== null) {
      window.clearTimeout(timer);
      timer = null;
    }
  }

  function schedule(): void {
    clear();
    if (!playing.value || pinned) {
      return;
    }
    timer = window.setTimeout(() => {
      if (playing.value && !pinned) {
        visible.value = false;
      }
    }, IDLE_MS);
  }

  /** ステージの操作（移動・タップ・キー入力）で呼ぶ。 */
  function poke(): void {
    visible.value = true;
    schedule();
  }

  /** 操作部を操作している間は隠さない。 */
  function pin(on: boolean): void {
    pinned = on;
    if (on) {
      visible.value = true;
      clear();
    } else {
      schedule();
    }
  }

  /** 再生・一時停止が切り替わったとき。 */
  function playingChanged(): void {
    if (playing.value) {
      schedule();
    } else {
      clear();
      visible.value = true;
    }
  }

  onBeforeUnmount(clear);

  return { visible, poke, pin, playingChanged };
}
