import { mount } from "@vue/test-utils";
import { describe, expect, it } from "vitest";
import ConfirmDialog from "../src/components/ConfirmDialog.vue";

function open() {
  return mount(ConfirmDialog, {
    props: { title: "削除の確認", message: "「Netflix」を削除しますか？", note: "元に戻せません" },
    attachTo: document.body,
  });
}

describe("確認ダイアログ", () => {
  it("文言とボタンの aria-label を表示し、最初のフォーカスはキャンセルに置く", async () => {
    const wrapper = open();
    await wrapper.vm.$nextTick();
    expect(wrapper.text()).toContain("「Netflix」を削除しますか？");
    expect(wrapper.text()).toContain("元に戻せません");
    expect(wrapper.find('[role="dialog"]').attributes("aria-label")).toBe("削除の確認");
    expect(wrapper.find('[aria-label="キャンセル"]').exists()).toBe(true);
    expect(wrapper.find('[aria-label="確定"]').exists()).toBe(true);
    expect(document.activeElement).toBe(wrapper.find('[aria-label="キャンセル"]').element);
    wrapper.unmount();
  });

  it("背景（オーバーレイ）を押しても閉じない。閉じるのはボタンと Esc だけ", async () => {
    const wrapper = open();
    await wrapper.find(".dialog-overlay").trigger("click");
    expect(wrapper.emitted("cancel")).toBeUndefined();
    expect(wrapper.emitted("confirm")).toBeUndefined();
    await wrapper.find('[aria-label="確定"]').trigger("click");
    expect(wrapper.emitted("confirm")).toHaveLength(1);
    await wrapper.find('[aria-label="キャンセル"]').trigger("click");
    expect(wrapper.emitted("cancel")).toHaveLength(1);
    await wrapper.find('[role="dialog"]').trigger("keydown", { key: "Escape" });
    expect(wrapper.emitted("cancel")).toHaveLength(2);
    wrapper.unmount();
  });
});
