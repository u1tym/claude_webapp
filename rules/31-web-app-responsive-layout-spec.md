# Webアプリケーション 画面レイアウト設計指針

> 対象: Claude Code を用いた Spec 駆動開発
> 適用範囲: PCブラウザ / スマートフォンブラウザ

## 1. 目的

本仕様は、PCとスマートフォンで一貫したデザインシステムを維持しつつ、画面幅・入力方法・利用状況に応じて情報量、配置、操作方法を最適化するための実装指針を定義する。

基本原則は **Responsive Layout ではなく Responsive UX** とする。PC画面を単純縮小してスマートフォンへ表示してはならない。

## 2. 規範用語

- **MUST**: 必須。満たさなければ仕様違反。
- **SHOULD**: 原則として実施。合理的理由がある場合のみ例外可。
- **MAY**: 任意。

## 3. 設計原則

### UI-PRINCIPLE-001: 共通デザインシステム

PCとスマートフォンは、色、タイポグラフィ、余白、角丸、ボーダー、状態色、基本コンポーネントを共通化しなければならない（MUST）。

### UI-PRINCIPLE-002: 情報優先度

画面幅が狭くなった場合、要素を単純縮小してはならない（MUST）。以下の順序で適応する。

1. レイアウトを再配置する
2. 補助情報を折りたたむ、または詳細画面へ移動する
3. 二次操作をメニューへ統合する
4. 主要操作と主要情報は維持する

### UI-PRINCIPLE-003: Calm UI

- 1画面内のPrimary Actionは原則1つとする（SHOULD）。
- 装飾より情報階層を優先する（MUST）。
- アニメーションは状態変化や操作結果の通知に使用し、注意を引くことだけを目的に使用しない（SHOULD）。

### UI-PRINCIPLE-004: アクセシビリティ

- キーボード操作可能な機能はフォーカス状態を視覚表示する（MUST）。
- 色だけで状態やエラーを表現しない（MUST）。
- タッチ操作の主要コントロールは十分な押下領域を確保する（MUST）。
- ズームや文字拡大で主要機能が利用不能にならないこと（MUST）。

## 4. Responsive UXモデル

### 4.1 ブレークポイント

ブレークポイントは実装上の初期値とし、特定機種名の判定には使用しない。

- Compact: `0px - 767px`。主にスマートフォン想定。
- Medium: `768px - 1023px`。主にタブレット想定。
- Wide: `1024px以上`。主にPC想定。

コンテンツが破綻する場合は、機種ではなくコンテンツを基準としてブレークポイントを調整してよい（MAY）。

### 4.2 入力方式

画面幅だけでマウス利用を推測してはならない（MUST NOT）。

- Hover専用機能を作らない（MUST）。
- Hoverは補助的フィードバックとして利用してよい（MAY）。
- 主要機能はクリック、タップ、キーボードの適切な方式から到達可能にする（MUST）。

## 5. PCレイアウト仕様

### PC-LAYOUT-001: 基本構成

Wideでは次の構成を標準とする。

```text
+----------+------------------------------------------+
| Sidebar  | Header / Page title                      |
|          +------------------------------------------+
| Home     | Main content                             |
| Apps     |                                          |
| Logs     | Bento / Grid / Detail                    |
|          |                                          |
+----------+------------------------------------------+
```

- Primary Navigationは左Sidebarを推奨する（SHOULD）。
- Main Contentには最大幅を設定し、超ワイド画面で情報が過度に拡散しないようにする（SHOULD）。
- 重要な情報ほど広いカード領域を与える（SHOULD）。

### PC-LAYOUT-002: Grid

- 主要コンテンツは2から4カラムを許可する。
- Bento Gridを使用する場合、カードサイズによって情報優先度を表現する。
- 同一重要度のカードは視覚的な一貫性を維持する。
- 一覧と詳細を同時表示すると作業効率が上がる場合、Master-Detail構成を使用してよい。

### PC-LAYOUT-003: 操作

- 頻繁に使用する操作は常時表示する（SHOULD）。
- 二次操作はOverflow Menuへ格納してよい。
- Keyboard Shortcutを提供する場合、GUIからも同じ機能へ到達可能にする（MUST）。
- Command Paletteを採用してよい（MAY）。

## 6. スマートフォンレイアウト仕様

### MOBILE-LAYOUT-001: 基本構成

Compactでは縦方向の情報フローを標準とする。

```text
+------------------------+
| Header                 |
+------------------------+
| Primary content        |
+------------------------+
| Secondary content      |
+------------------------+
| Actions / Detail       |
+------------------------+
| Bottom Navigation      |
+------------------------+
```

### MOBILE-LAYOUT-002: Navigation

- 主要な遷移先が少数の場合、Bottom Navigationを優先する（SHOULD）。
- PC Sidebarを幅だけ縮小して表示してはならない（MUST NOT）。
- 階層の深い補助NavigationはMenuや別画面へ移動してよい（MAY）。

### MOBILE-LAYOUT-003: Grid

- 原則1カラムとする。
- 短い指標カードなど、可読性と操作性を損なわない場合のみ2カラムを許可する。
- 3カラム以上を前提とした主要情報表示は使用しない（SHOULD NOT）。
- PCで横並びのカードは情報優先度順に縦へ再配置する。

### MOBILE-LAYOUT-004: 操作

PC:

```text
[Edit] [Duplicate] [Export] [Delete]
```

Mobile:

```text
[Edit] [...]
```

`...` からSecondary ActionsをBottom SheetまたはMenuとして表示する。

- Primary Actionは到達しやすい位置へ配置する（SHOULD）。
- 破壊的操作はPrimary Actionと視覚的・空間的に区別する（MUST）。
- Hoverを操作条件にしない（MUST）。
- Swipe Gestureだけを唯一の操作方法にしない（MUST）。

## 7. PCからスマートフォンへの変換規則

| PC | Smartphone |
|---|---|
| Sidebar | Bottom Navigation / Menu |
| 2-4 column Grid | 1 column、必要時のみ2 column |
| 横並びAction | Primary Action + Overflow |
| Modal | DialogまたはBottom Sheet |
| Master-Detail | List → Detail遷移 |
| Hover tooltip | Tap可能な情報提示手段 |
| Keyboard Shortcut | GUI / Touch Action |
| Dense Table | 重要列を優先したCard/Listまたは横スクロールを慎重に使用 |

## 8. コンポーネント設計

レスポンシブ対応をページ固有CSSへ散在させず、可能な限りコンポーネントの責務として定義する（SHOULD）。

推奨構造:

```text
Design Tokens
  ↓
Primitive Components
  Button / Input / Card / Dialog
  ↓
Composite Components
  Navigation / DataCard / ActionMenu
  ↓
Responsive Layout
  AppShell / Grid / MasterDetail
  ↓
Pages
```

同じ意味を持つPC用・スマートフォン用コンポーネントを無計画に別実装してはならない。同一コンポーネントのVariantまたは構造化されたResponsive Componentとして扱う（SHOULD）。

## 9. AI機能がある場合

- AI入力欄は通常UIを置き換える唯一の操作方法にしない（MUST）。
- AIが実行予定の重要操作をユーザーが理解できるようにする（MUST）。
- 破壊的・不可逆な操作は実行前確認を行う（MUST）。
- PCではPrompt領域やCommand Paletteを利用してよい。
- スマートフォンでは入力領域が画面を圧迫しないよう、展開式UIやBottom Sheetを検討する。

## 10. 状態設計

各主要画面について次の状態を設計・実装する（MUST）。

- Loading
- Empty
- Success / Normal
- Error
- Permission denied（該当する場合）
- Offline / Network failure（ネットワーク依存機能で必要な場合）

Loading時にレイアウトが大きく移動しないよう、Skeleton等で領域を予約することを推奨する（SHOULD）。

## 11. Acceptance Criteria

### AC-RESP-001

**Given** Wide viewportで画面を表示している  
**When** Compact viewportへ変更する  
**Then** 横スクロールを主要ナビゲーション手段として要求せず、主要情報とPrimary Actionが利用可能であること。

### AC-RESP-002

**Given** PCでSidebarが表示されている  
**When** Compact viewportで表示する  
**Then** Sidebarはモバイル向けNavigationへ変換され、単純縮小表示されないこと。

### AC-RESP-003

**Given** PCで複数のActionが横並びになっている  
**When** Compact viewportで表示する  
**Then** Primary Actionを維持し、Secondary ActionはMenu等へ整理されること。

### AC-INPUT-001

**Given** マウスを利用できない  
**When** タッチ操作のみでアプリを操作する  
**Then** Hoverを必要とせず全主要機能へ到達できること。

### AC-KEYBOARD-001

**Given** PCブラウザをキーボードで操作する  
**When** フォーカスを移動する  
**Then** Interactive Elementのフォーカス位置を視覚的に識別できること。

### AC-CONTENT-001

**Given** 同一データをPCとスマートフォンで表示する  
**When** Smartphone Layoutへ変換する  
**Then** 最重要情報の意味、状態、Primary Actionが失われないこと。

## 12. Claude Codeへの実装指示

実装時は以下を遵守すること。

1. 既存のDesign System、component library、CSS方針を最初に調査する。
2. 既存コンポーネントを再利用できる場合、新規の類似コンポーネントを作成しない。
3. PCとスマートフォンでBusiness Logicを重複実装しない。
4. viewport幅だけでなく、keyboard、pointer、touchの利用可能性を考慮する。
5. レスポンシブ変更でDOM順序と視覚順序が著しく乖離しないようにする。
6. 各画面についてWideとCompactの両方を検証する。
7. Overflow、長い文字列、0件、大量データ、エラー状態を検証する。
8. 仕様にない装飾的UIを独断で追加しない。
9. 判断に迷った場合、見た目の華やかさより可読性、操作性、アクセシビリティを優先する。

## 13. PR / Review Checklist

- [ ] PC版を単純縮小しただけのMobile UIになっていない
- [ ] Primary Actionが端末間で維持されている
- [ ] Mobileで重要情報が先に表示される
- [ ] Hover専用機能がない
- [ ] Keyboard Focusが確認できる
- [ ] Navigationが端末特性に適応している
- [ ] GridがCompactで適切に再配置される
- [ ] 長いテキストでレイアウトが破綻しない
- [ ] Loading / Empty / Error状態がある
- [ ] Design Tokensと既存Componentsを再利用している
- [ ] 破壊的操作が誤操作しにくい
- [ ] Wide / Compact双方のテストが存在する

## 14. Spec作成時のテンプレート

各画面SPECには最低限、次の項目を記載する。

```markdown
# <画面名>

## Purpose
<ユーザーがこの画面で達成する目的>

## Information Priority
1. <最重要情報>
2. <次に重要な情報>
3. <補助情報>

## Primary Action
- <主要操作>

## Secondary Actions
- <副次操作>

## Wide Layout
- Navigation:
- Columns:
- Main content:
- Secondary content:
- Actions:

## Compact Layout
- Navigation:
- Content order:
- Primary action position:
- Secondary action treatment:
- Hidden/collapsed information:

## States
- Loading:
- Empty:
- Error:
- Normal:

## Accessibility
- Keyboard:
- Focus:
- Labels:
- Touch:

## Acceptance Criteria
### AC-001
Given ...
When ...
Then ...
```

---

この仕様の優先順位は **ユーザーの目的 > 情報優先度 > 操作性 > 一貫性 > 装飾** とする。
