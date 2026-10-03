import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, AuthError } from "../src/api/client";
import type { Category, CategoryInput } from "../src/api/types";
import CategoriesView from "../src/views/CategoriesView.vue";

const listCategories = vi.fn<() => Promise<Category[]>>();
const createCategory = vi.fn<(input: CategoryInput) => Promise<Category>>();
const updateCategory = vi.fn<(id: number, input: CategoryInput) => Promise<Category>>();
const deleteCategory = vi.fn<(id: number) => Promise<void>>();

vi.mock("../src/api/categories", () => ({
  listCategories: () => listCategories(),
  createCategory: (input: CategoryInput) => createCategory(input),
  updateCategory: (id: number, input: CategoryInput) => updateCategory(id, input),
  deleteCategory: (id: number) => deleteCategory(id),
}));

const OTHER: Category = { id: 1, name: "その他", is_default: true, is_financial: false };
const VIDEO: Category = { id: 2, name: "動画配信", is_default: false, is_financial: false };
const BANK: Category = { id: 3, name: "銀行", is_default: false, is_financial: true };

async function mountView(items: Category[] = [OTHER, VIDEO, BANK]) {
  listCategories.mockResolvedValue(items);
  const wrapper = mount(CategoriesView, { attachTo: document.body });
  await flushPromises();
  return wrapper;
}

function rowOf(wrapper: VueWrapper, name: string) {
  const row = wrapper.findAll(".category-row").find((r) => r.text().includes(name));
  if (!row) {
    throw new Error(`row not found: ${name}`);
  }
  return row;
}

beforeEach(() => {
  listCategories.mockReset();
  createCategory.mockReset();
  updateCategory.mockReset();
  deleteCategory.mockReset();
});

afterEach(() => {
  vi.useRealTimers();
  document.body.innerHTML = "";
});

describe("区分", () => {
  it("取得中は「読み込み中…」を出す", async () => {
    listCategories.mockReturnValue(new Promise(() => undefined));
    const wrapper = mount(CategoriesView);
    expect(wrapper.text()).toContain("読み込み中…");
  });

  it("区分を一覧し、金融機関には「金融機関」のバッジを付ける。「その他」には編集・削除のボタンを出さない", async () => {
    const wrapper = await mountView();
    const rows = wrapper.findAll(".category-row");
    expect(rows.map((r) => r.find(".cell-title").text())).toEqual(["その他", "動画配信", "銀行"]);
    expect(rowOf(wrapper, "銀行").find(".badge").text()).toBe("金融機関");
    expect(rowOf(wrapper, "動画配信").find(".badge").exists()).toBe(false);
    expect(rowOf(wrapper, "その他").findAll("button")).toHaveLength(0);
    expect(rowOf(wrapper, "動画配信").find('[aria-label="動画配信を編集"]').exists()).toBe(true);
    expect(rowOf(wrapper, "動画配信").find('[aria-label="動画配信を削除"]').exists()).toBe(true);
  });

  it("「その他」以外の区分が無いときも、「その他」の行を表示する", async () => {
    const wrapper = await mountView([OTHER]);
    expect(wrapper.findAll(".category-row")).toHaveLength(1);
    expect(wrapper.text()).toContain("その他");
  });

  it("区分を追加する（名称は前後の空白を除く。金融機関のチェックを送る）。追加後に、欄を空にして再取得する", async () => {
    vi.useFakeTimers();
    const wrapper = await mountView([OTHER]);
    createCategory.mockResolvedValue({ id: 9, name: "保険", is_default: false, is_financial: true });
    listCategories.mockResolvedValue([OTHER, { id: 9, name: "保険", is_default: false, is_financial: true }]);
    await wrapper.get('input[aria-label="区分名"]').setValue("  保険  ");
    await wrapper.get('input[type="checkbox"]').setValue(true);
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await flushPromises();
    expect(createCategory).toHaveBeenCalledWith({ name: "保険", is_financial: true });
    expect((wrapper.get('input[aria-label="区分名"]').element as HTMLInputElement).value).toBe("");
    expect((wrapper.get('input[type="checkbox"]').element as HTMLInputElement).checked).toBe(false);
    expect(wrapper.findAll(".category-row")).toHaveLength(2);
    expect(wrapper.get('[role="status"]').text()).toBe("追加しました");
    await vi.advanceTimersByTimeAsync(3100); // 成功メッセージは数秒で消える
    expect(wrapper.find('[role="status"]').exists()).toBe(false);
  });

  it("追加で、空白のみ・長すぎる名称は送らず、入力欄の近くに示す。重複（409）も入力欄の近くに示す", async () => {
    const wrapper = await mountView([OTHER]);
    await wrapper.get('input[aria-label="区分名"]').setValue("   ");
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    expect(wrapper.get(".field-error").text()).toBe("名称を入力してください");
    await wrapper.get('input[aria-label="区分名"]').setValue("あ".repeat(101));
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    expect(wrapper.get(".field-error").text()).toContain("100 文字以内");
    expect(createCategory).not.toHaveBeenCalled();
    createCategory.mockRejectedValue(new ApiError(409, "保存できませんでした"));
    await wrapper.get('input[aria-label="区分名"]').setValue("動画配信");
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await flushPromises();
    expect(wrapper.get(".field-error").text()).toBe("同じ名称の区分があります");
    expect((wrapper.get('input[aria-label="区分名"]').element as HTMLInputElement).value).toBe("動画配信"); // 入力は残す
  });

  it("編集: 名称と金融機関の指定を変えて保存する。キャンセルで、変更を捨てる", async () => {
    const wrapper = await mountView();
    await rowOf(wrapper, "動画配信").get('[aria-label="動画配信を編集"]').trigger("click");
    const nameInput = wrapper.get('input[aria-label="区分名の編集"]');
    expect((nameInput.element as HTMLInputElement).value).toBe("動画配信");
    await nameInput.setValue("配信");
    await wrapper.get(".category-row input[type='checkbox']").setValue(true);
    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    expect(wrapper.find('input[aria-label="区分名の編集"]').exists()).toBe(false);
    expect(updateCategory).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("動画配信");

    await rowOf(wrapper, "動画配信").get('[aria-label="動画配信を編集"]').trigger("click");
    await wrapper.get('input[aria-label="区分名の編集"]').setValue(" 配信 ");
    await wrapper.get(".category-row input[type='checkbox']").setValue(true);
    updateCategory.mockResolvedValue({ ...VIDEO, name: "配信", is_financial: true });
    listCategories.mockResolvedValue([OTHER, { ...VIDEO, name: "配信", is_financial: true }, BANK]);
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(updateCategory).toHaveBeenCalledWith(2, { name: "配信", is_financial: true });
    expect(wrapper.find('input[aria-label="区分名の編集"]').exists()).toBe(false);
    expect(wrapper.get('[role="status"]').text()).toBe("更新しました");
    expect(rowOf(wrapper, "配信").find(".badge").exists()).toBe(true);
  });

  it("編集の入力検査と、名称の重複（409）", async () => {
    const wrapper = await mountView();
    await rowOf(wrapper, "動画配信").get('[aria-label="動画配信を編集"]').trigger("click");
    await wrapper.get('input[aria-label="区分名の編集"]').setValue("  ");
    await wrapper.get('[aria-label="保存"]').trigger("click");
    expect(wrapper.get(".field-error").text()).toBe("名称を入力してください");
    expect(updateCategory).not.toHaveBeenCalled();
    updateCategory.mockRejectedValue(new ApiError(409, "保存できませんでした"));
    await wrapper.get('input[aria-label="区分名の編集"]').setValue("銀行");
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(wrapper.get(".field-error").text()).toBe("同じ名称の区分があります");
    expect(wrapper.find('input[aria-label="区分名の編集"]').exists()).toBe(true); // 編集は続けられる
  });

  it("金融機関の指定を外せないとき（支払方法として使われている）は、一覧の先頭にメッセージを出す", async () => {
    const wrapper = await mountView();
    await rowOf(wrapper, "銀行").get('[aria-label="銀行を編集"]').trigger("click");
    await wrapper.get(".category-row input[type='checkbox']").setValue(false);
    updateCategory.mockRejectedValue(new ApiError(409, "保存できませんでした"));
    await wrapper.get('[aria-label="保存"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("支払方法として使われているため、金融機関の指定を外せません");
    expect(wrapper.find(".field-error").exists()).toBe(false);
  });

  it("削除: 確認ダイアログで確定すると削除し、再取得する。キャンセルでは何もしない", async () => {
    const wrapper = await mountView();
    await rowOf(wrapper, "動画配信").get('[aria-label="動画配信を削除"]').trigger("click");
    expect(wrapper.get('[role="dialog"]').text()).toContain("区分「動画配信」を削除しますか？");
    await wrapper.get('[aria-label="キャンセル"]').trigger("click");
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    expect(deleteCategory).not.toHaveBeenCalled();

    await rowOf(wrapper, "動画配信").get('[aria-label="動画配信を削除"]').trigger("click");
    deleteCategory.mockResolvedValue(undefined);
    listCategories.mockResolvedValue([OTHER, BANK]);
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(deleteCategory).toHaveBeenCalledWith(2);
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false);
    expect(wrapper.get('[role="status"]').text()).toBe("削除しました");
    expect(wrapper.findAll(".category-row")).toHaveLength(2);
  });

  it("使用中の区分の削除（409）は、一覧の先頭に「使用中のため削除できません」を出す", async () => {
    const wrapper = await mountView();
    await rowOf(wrapper, "動画配信").get('[aria-label="動画配信を削除"]').trigger("click");
    deleteCategory.mockRejectedValue(new ApiError(409, "保存できませんでした"));
    await wrapper.get('[aria-label="確定"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("使用中のため削除できません");
    expect(wrapper.findAll(".category-row")).toHaveLength(3); // 一覧は変わらない
  });

  it("取得・操作の失敗は、内部理由を含まないメッセージ。401 / 403 は、メッセージを出さずに殻へ通知する", async () => {
    listCategories.mockRejectedValue(new Error("boom: internal"));
    const failed = mount(CategoriesView);
    await flushPromises();
    expect(failed.get('[role="alert"]').text()).toBe("読み込みに失敗しました");
    expect(failed.text()).not.toContain("internal");

    listCategories.mockRejectedValue(new AuthError(401));
    const unauth = mount(CategoriesView);
    await flushPromises();
    expect(unauth.find('[role="alert"]').exists()).toBe(false);
    expect((unauth.emitted("auth-error")?.[0]?.[0] as AuthError).status).toBe(401);

    const wrapper = await mountView();
    createCategory.mockRejectedValue(new AuthError(403));
    await wrapper.get('input[aria-label="区分名"]').setValue("x");
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await flushPromises();
    expect(wrapper.emitted("auth-error")).toHaveLength(1);
    expect(wrapper.find('[role="alert"]').exists()).toBe(false);
    createCategory.mockRejectedValue(new ApiError(500, "サーバエラーです"));
    await wrapper.get('button[aria-label="新規"]').trigger("click");
    await flushPromises();
    expect(wrapper.get('[role="alert"]').text()).toBe("追加に失敗しました");
  });
});
