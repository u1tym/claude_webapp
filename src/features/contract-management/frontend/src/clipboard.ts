/** クリップボードへ文字列をコピーする。Clipboard API が使えないときは、一時的な入力欄で代用する。 */
export async function copyText(text: string): Promise<void> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const area = document.createElement("textarea");
  area.value = text;
  area.setAttribute("readonly", "");
  area.style.position = "fixed";
  area.style.opacity = "0";
  document.body.appendChild(area);
  area.select();
  try {
    if (!document.execCommand("copy")) {
      throw new Error("copy failed");
    }
  } finally {
    document.body.removeChild(area);
  }
}
