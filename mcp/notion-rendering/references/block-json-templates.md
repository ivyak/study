<!-- FALLBACK: 通常は scripts/notion_cli.py の --md-stdin で Markdown を渡す。手動で Block JSON を組む場合のみ参照 -->

# Block JSON テンプレート集

Block API (`PATCH /v1/blocks/{id}/children`) で使用する全ブロックタイプの JSON テンプレート。
変換ルールは `md-to-blocks-rules.md` を参照。

---

## Heading (heading_1 / heading_2 / heading_3 / heading_4)

```json
{
  "type": "heading_2",
  "heading_2": {
    "rich_text": [{"type": "text", "text": {"content": "セクションタイトル"}}],
    "is_toggleable": false
  }
}
```

### Toggleable Heading (折りたたみ見出し)

```json
{
  "type": "heading_2",
  "heading_2": {
    "rich_text": [{"type": "text", "text": {"content": "セクションタイトル"}}],
    "is_toggleable": true,
    "children": [
      {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "折りたたまれた内容"}}]}}
    ]
  }
}
```

**注意**: `is_toggleable: false` の heading に `children` を渡すとエラー。

---

## Paragraph

```json
{
  "type": "paragraph",
  "paragraph": {
    "rich_text": [{"type": "text", "text": {"content": "段落テキスト"}}]
  }
}
```

---

## Bulleted List Item

```json
{
  "type": "bulleted_list_item",
  "bulleted_list_item": {
    "rich_text": [{"type": "text", "text": {"content": "項目テキスト"}}],
    "children": [
      {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "ネスト項目"}}]}}
    ]
  }
}
```

`children` はネスト時のみ。

---

## Numbered List Item

```json
{
  "type": "numbered_list_item",
  "numbered_list_item": {
    "rich_text": [{"type": "text", "text": {"content": "番号付き項目"}}]
  }
}
```

---

## To-Do

```json
{
  "type": "to_do",
  "to_do": {
    "rich_text": [{"type": "text", "text": {"content": "タスク内容"}}],
    "checked": false
  }
}
```

---

## Toggle

```json
{
  "type": "toggle",
  "toggle": {
    "rich_text": [{"type": "text", "text": {"content": "クリックして展開"}}],
    "children": [
      {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "折りたたまれた内容"}}]}}
    ]
  }
}
```

---

## Code

```json
{
  "type": "code",
  "code": {
    "rich_text": [{"type": "text", "text": {"content": "def hello():\n    print('Hello')"}}],
    "language": "python"
  }
}
```

---

## Divider

```json
{"type": "divider", "divider": {}}
```

---

## Table

```json
{
  "type": "table",
  "table": {
    "table_width": 3,
    "has_column_header": true,
    "has_row_header": false,
    "children": [
      {"type": "table_row", "table_row": {"cells": [
        [{"type": "text", "text": {"content": "ヘッダ1"}}],
        [{"type": "text", "text": {"content": "ヘッダ2"}}],
        [{"type": "text", "text": {"content": "ヘッダ3"}}]
      ]}},
      {"type": "table_row", "table_row": {"cells": [
        [{"type": "text", "text": {"content": "値1"}}],
        [{"type": "text", "text": {"content": "値2"}}],
        [{"type": "text", "text": {"content": "値3"}}]
      ]}}
    ]
  }
}
```

**重要**: `table_width` と各行の `cells` 数を一致させること。`children` は `table` オブジェクト内に配置 (ブロックルートではない)。

---

## Callout

```json
{
  "type": "callout",
  "callout": {
    "rich_text": [{"type": "text", "text": {"content": "重要な情報"}}],
    "icon": {"type": "emoji", "emoji": "💡"}
  }
}
```

---

## Image (外部 URL)

```json
{
  "type": "image",
  "image": {
    "type": "external",
    "external": {"url": "https://example.com/image.png"},
    "caption": [{"type": "text", "text": {"content": "キャプション"}}]
  }
}
```

## Image (ファイルアップロード後)

```json
{
  "type": "image",
  "image": {
    "type": "file_upload",
    "file_upload": {"id": "FILE_UPLOAD_ID"},
    "caption": [{"type": "text", "text": {"content": "キャプション"}}]
  }
}
```

---

## Column List + Column

```json
{
  "type": "column_list",
  "column_list": {
    "children": [
      {"type": "column", "column": {"children": [
        {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "左カラム"}}]}}
      ]}},
      {"type": "column", "column": {"children": [
        {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "右カラム"}}]}}
      ]}}
    ]
  }
}
```

最低 2 列必要。

---

## Bookmark

```json
{
  "type": "bookmark",
  "bookmark": {
    "url": "https://example.com",
    "caption": [{"type": "text", "text": {"content": "サイト名"}}]
  }
}
```

---

## Embed

```json
{
  "type": "embed",
  "embed": {
    "url": "https://drive.google.com/file/d/XXXXX/preview"
  }
}
```

---

## rich_text テンプレート

### 基本テキスト

```json
{"type": "text", "text": {"content": "テキスト"}}
```

### 装飾付き

```json
{
  "type": "text",
  "text": {"content": "太字テキスト"},
  "annotations": {"bold": true, "italic": false, "strikethrough": false, "underline": false, "code": false, "color": "default"}
}
```

### リンク付き

```json
{
  "type": "text",
  "text": {"content": "リンクテキスト", "link": {"url": "https://example.com"}},
  "annotations": {"bold": false, "italic": false, "strikethrough": false, "underline": false, "code": false, "color": "default"}
}
```

### Mention (ユーザー)

```json
{
  "type": "mention",
  "mention": {"type": "user", "user": {"object": "user", "id": "USER_UUID"}},
  "annotations": {"bold": false, "italic": false, "strikethrough": false, "underline": false, "code": false, "color": "default"}
}
```

---

## コメント API

```bash
# 取得
curl -s "https://api.notion.com/v1/comments?block_id=${PAGE_ID}&page_size=100" \
  -H 'Notion-Version: 2026-03-11' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"")

# 追加
curl -s -X POST 'https://api.notion.com/v1/comments' \
  -H 'Notion-Version: 2026-03-11' \
  -H 'Content-Type: application/json' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  -d '{"parent":{"page_id":"'"${PAGE_ID}"'"},"rich_text":[{"type":"text","text":{"content":"コメント"}}]}'
```

ページレベルのみ。インラインコメントは API 非対応。
