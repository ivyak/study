<!-- FALLBACK: 通常は scripts/notion_cli.py が MD → Block 変換を内部処理する。変換ルールの確認が必要な場合のみ参照 -->

# MD → Notion Block 変換ルール

`scripts/lib/md_to_blocks.py`(+ `preprocess.py`)が実装する変換マッピング。
Block JSON を組み立てる際はこのルールに従う。テンプレートは `block-json-templates.md` を参照。

---

## ブロック変換

| Markdown | Notion Block | 備考 |
|---------|-------------|------|
| `# H1` ~ `#### H4` | heading_1 ~ heading_4 | H5/H6 は heading_4 に丸める |
| `## Title {toggle="true"}` | heading_* (is_toggleable: true) + children | 次の同 level heading 直前までが children |
| `- item` | bulleted_list_item | ネスト対応 (children で表現) |
| `1. item` | numbered_list_item | ネスト対応 |
| 通常テキスト | paragraph | 空行の paragraph は生成しない |
| ` ```lang ``` ` | code | language を指定。未対応言語は "plain text" |
| `---` | divider | |
| `![alt](https://...)` | image (type: external) | 外部 URL |
| `![alt](local/path)` | paragraph(目印 `[画像: path]`)+ warnings | MD 経由では添付しない。書込後に `upload <file> --block-id <id>` で添付 |
| パイプテーブル `\| col \|` | table + table_row | table_width = 最大列数、短い行はパディング。**テーブルはこのパイプ形式で書く** |
| `<details><summary>Title</summary>...</details>` | toggle + children | ネスト対応 |
| `<callout emoji="💡">...</callout>` | callout (icon=emoji) + children | 先頭段落を本体 rich_text に昇格、残りは children。`preprocess.py` が `> 💡 ...` から生成 |
| `<columns><column>...</column>...</columns>` | column_list + column | 各 column 内は再帰変換。最低 2 列必要 |

## インライン (rich_text) 変換

| Markdown | rich_text の形式 |
|---------|-----------------|
| `**text**` | `annotations.bold: true` |
| `*text*` | `annotations.italic: true` |
| `` `text` `` | `annotations.code: true` |
| `~~text~~` | `annotations.strikethrough: true` |
| `[text](url)` | `text.link.url` |
| `<br>` / `<br/>` | `"\n"` を content に追加 |
| `<mention-user url="user://UUID"/>` | `type: "mention"`, `mention.type: "user"`, `mention.user.id: UUID` |
| softbreak | 改行 `"\n"`(Notion 上で改行として表示) |
| hardbreak | 改行 `"\n"` |

### rich_text の制約

- **1 要素の文字数上限**: 2,000 文字。本文・コードは自動で複数要素に分割する(切り捨てない)。見出し等の短い要素で超過した場合のみ切り捨て + `warnings`
- **配列要素数上限**: 100 要素 (超過分は切り捨て + `warnings` に報告)
- **隣接する同スタイルの要素はマージ**: bold 同士、link 同士などが連続する場合は 1 要素に結合

---

## 独自拡張構文

`scripts/lib/preprocess.py` が Markdown パース前に処理する拡張構文。

### Heading Toggle

```markdown
## セクションタイトル {toggle="true"}

この内容は heading_2 の children になる。
段落やリストなど何でも入る。

## 次のセクション
← ここで children 終了 (同 level の heading が境界)
```

→ heading_2 に `is_toggleable: true` + children

### Blockquote → Toggle / Callout (preprocess.py の前処理)

`>` 引用は、最初の中身の行の形によって **toggle** か **callout** に振り分けられる。

```markdown
> ## トグルタイトル        ← 見出し始まり → toggle (見出しが summary)
> 内容テキスト
> - リスト項目

> **💡 重要な結論**         ← 絵文字始まり → callout (絵文字がアイコン)

> 見出しも絵文字も無い本文   ← その他 → toggle (空 summary)
```

判定ルール（単層 `>` 引用が対象。ネスト `> >` は toggle 扱い）:

| 最初の中身の行 | 変換先 |
|---|---|
| 見出し (`## ...`) | toggle（見出しを `<summary>` に） |
| 絵文字始まり (`💡` / `**💡 ...**`) | callout（先頭絵文字を icon に、残りを本文に） |
| 上記以外 | toggle（空 summary） |

**連続する絵文字 callout は分割される**: `> 💡 a` と `> ⚠️ b` のように絵文字始まりの行が連続する
場合、行ごとに別の callout になる。絵文字で始まらない後続行は直前の callout の本文に連結される
（多行 callout は維持される）。

**リスト項目内の入れ子**: リスト項目の中にインデントして `> 💡 ...`（callout）、`> ## ...`（toggle）、
`### 見出し {toggle="true"}`（heading toggle）を書いても、リスト項目の子ブロックとして正しく入れ子になる
（旧版では見出しが消えたり `>` が素の段落になったりしていた）。

**注意**: この構文では `>` は標準 Markdown の blockquote ではなく、`preprocess.py` 独自の前処理で
toggle / callout に変換される。SubAgent が自力で Block JSON を組む場合は、toggle は `<details>` 形式
または `{toggle="true"}` 形式、callout は `block-json-templates.md` の callout テンプレートを使うこと。

**callout / toggle の直後の本文**: callout (`> 💡 ...`) や toggle (`> ## ...`) の直後に、空行を空けずに
テーブルや箇条書きを書いても**欠落しない**。markdown-it が生成 HTML ブロックに後続行を巻き込んでも、
`md_to_blocks` が閉じタグ以降の本文を再 parse して兄弟ブロックとして復元する（旧版ではここで巻き込まれた
テーブル・箇条書きが黙って消えていた）。

### Columns ショートハンド (preprocess.py の前処理)

```markdown
{[
左カラムの内容
],[
右カラムの内容
]}
```

→ `<columns><column>...</column><column>...</column></columns>` に展開

---

## depth=2 制約の対応

Block API は children の深さが 2 まで。3 段目以降は別リクエストで追加する。

**戦略**:
1. まず深い children を剥がしてフラットなブロックを送信
2. 作成されたブロックの ID をレスポンスから取得
3. 剥がした children を対象ブロック ID に対して再帰的に append

**children が必須のブロック** (剥がせない): table, column_list, column
→ 内部の grandchildren だけフラット化する

**children が任意のブロック** (剥がせる): toggle, heading (toggleable), bulleted_list_item, numbered_list_item
→ children を一旦剥がし、後から追加

---

## テーブル変換の詳細

1. `has_column_header: true` (常に最初の行がヘッダー)
2. `table_width`: 全行の最大列数に合わせる
3. 列数不足の行: 空セル `[{"type":"text","text":{"content":""}}]` でパディング
4. 列数超過の行: 超過分を切り捨て
5. 各セルは rich_text 配列 (インライン書式対応)
6. 行が 0 件のテーブル: 空 paragraph にフォールバック

## コードブロックの language

対応言語 (一部抜粋): bash, python, javascript, typescript, java, go, rust, c, c++, c#, ruby, php, sql, json, yaml, html, css, markdown, mermaid, latex, plain text

未対応言語は `"plain text"` にフォールバック。
