// Markdown・TeX・URL の描画。本文中の生の HTML は許可せず、リンクは http / https のものだけにする。

import katex from "katex";
import MarkdownIt from "markdown-it";

const md = new MarkdownIt({ html: false, linkify: true, breaks: true });

const HTTP_URL = /^https?:\/\//i;

/** http / https のリンクだけを許す（javascript: などは、リンクにしない）。 */
md.validateLink = (url: string): boolean => HTTP_URL.test(url.trim());

const defaultLinkOpen =
  md.renderer.rules.link_open ?? ((tokens, idx, options, _env, self) => self.renderToken(tokens, idx, options));

md.renderer.rules.link_open = (tokens, idx, options, env, self) => {
  tokens[idx].attrSet("target", "_blank");
  tokens[idx].attrSet("rel", "noopener noreferrer");
  return defaultLinkOpen(tokens, idx, options, env, self);
};

export function renderMarkdown(source: string): string {
  return md.render(source);
}

function escapeHtml(text: string): string {
  return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
}

/** TeX の数式を組版する。組版に失敗したときは、ソースをそのまま（エスケープして）返す。 */
export function renderTex(source: string): string {
  try {
    return katex.renderToString(source, { displayMode: true, throwOnError: true });
  } catch {
    return `<pre class="tex-source">${escapeHtml(source)}</pre>`;
  }
}

/** URL パーツの文字列が、開ける http / https の URL なら、その（前後の空白を除いた）文字列。そうでなければ null。 */
export function safeHttpUrl(text: string): string | null {
  const trimmed = text.trim();
  return HTTP_URL.test(trimmed) ? trimmed : null;
}
