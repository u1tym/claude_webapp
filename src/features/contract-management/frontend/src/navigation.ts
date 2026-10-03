/** 他の画面（ログイン画面、メニュー画面）へ移る。テストで差し替えられるよう、ここに集める。 */
export function navigateTo(url: string): void {
  window.location.href = url;
}
