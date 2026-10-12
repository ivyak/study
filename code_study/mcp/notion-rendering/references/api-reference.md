<!-- FALLBACK: 通常は scripts/notion_cli.py を使用。CLI で対応できない操作のみこのリファレンスを参照 -->

# Notion API リファレンス

## トークン取得

```bash
NOTION_API_TOKEN="${NOTION_API_TOKEN:-$(grep '^NOTION_API_TOKEN=' .env 2>/dev/null | cut -d= -f2- | tr -d '"')}"
if [ -z "$NOTION_API_TOKEN" ]; then
  NOTION_API_TOKEN=$(python3 -c "
import json
for p in ['.mcp.json', '../.mcp.json', '../../.mcp.json']:
    try:
        d = json.load(open(p))
        h = json.loads(d['mcpServers']['notion']['env']['OPENAPI_MCP_HEADERS'])
        print(h['Authorization'].replace('Bearer ', ''))
        break
    except: pass
" 2>/dev/null)
fi
```

**重要**: トークンを curl 引数にベタ書きしない。`-K <(...)` で渡す。

---

## 読取: GET /v1/pages/{page_id}/markdown (Markdown API)

ページ全文を markdown で取得する。**読み取り専用で使用**。

```bash
curl -s "https://api.notion.com/v1/pages/${PAGE_ID}/markdown" \
  -H 'Notion-Version: 2026-03-11' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"")
```

レスポンス:
```json
{
  "object": "page_markdown",
  "id": "page-uuid",
  "markdown": "# Title\n\nContent...",
  "truncated": false,
  "unknown_block_ids": []
}
```

---

## 書込: PATCH /v1/blocks/{block_id}/children (Block API)

**書き込みは Block API をメインに使う。** ブロック JSON を組み立てて送信する。
JSON の組み立てルールは `md-to-blocks-rules.md` を、
テンプレートは `block-json-templates.md` を参照。

```bash
curl -s -X PATCH "https://api.notion.com/v1/blocks/${BLOCK_ID}/children" \
  -H 'Notion-Version: 2026-03-11' \
  -H 'Content-Type: application/json' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  -d '{"children": [BLOCKS_JSON]}'
```

### 挿入位置の指定

```json
{
  "children": [BLOCKS_JSON],
  "position": {
    "type": "after_block",
    "after_block": {"id": "TARGET_BLOCK_ID"}
  }
}
```

- `{"type": "end"}`: 末尾に追加 (デフォルト)
- `{"type": "start"}`: 先頭に挿入
- `{"type": "after_block", ...}`: 指定ブロック後に挿入

### 制約

- 1 リクエスト最大 **100 ブロック**
- ネスト深さ最大 **2** (子の子まで)。3 段目以降は別リクエストで追加

---

## ブロック読取: GET /v1/blocks/{block_id}/children

```bash
curl -s "https://api.notion.com/v1/blocks/${BLOCK_ID}/children?page_size=100" \
  -H 'Notion-Version: 2026-03-11' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"")
```

`has_more: true` の場合は `start_cursor` でページネーション。

---

## ブロック更新/削除

```bash
# 更新
curl -s -X PATCH "https://api.notion.com/v1/blocks/${BLOCK_ID}" \
  -H 'Notion-Version: 2026-03-11' \
  -H 'Content-Type: application/json' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  -d '{BLOCK_OBJECT}'

# 削除 (アーカイブ)
curl -s -X DELETE "https://api.notion.com/v1/blocks/${BLOCK_ID}" \
  -H 'Notion-Version: 2026-03-11' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"")
```

---

## ファイルアップロード (3 ステップ)

```bash
# Step 1: アップロードオブジェクト作成
UPLOAD_ID=$(curl -s -X POST 'https://api.notion.com/v1/file_uploads' \
  -H 'Notion-Version: 2026-03-11' \
  -H 'Content-Type: application/json' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  -d '{"mode": "single_part"}' | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")

# Step 2: ファイル送信
curl -s -X POST "https://api.notion.com/v1/file_uploads/${UPLOAD_ID}/send" \
  -H 'Notion-Version: 2026-03-11' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  -F "file=@/path/to/file.png;type=image/png"

# Step 3: image ブロックに埋め込み (block-json-templates.md 参照)
```

上限: 20MB (single_part)

---

## データベース操作

### DB プロパティ取得 (2 ステップ)

`Notion-Version: 2025-09-03` 以降、DB プロパティは `/v1/databases/{id}` から直接取れなくなった。
代わりに `data_sources` 経由で取得する。

```bash
# Step 1: data_source_id を取得
DS_ID=$(curl -s "https://api.notion.com/v1/databases/${DB_ID}" \
  -H 'Notion-Version: 2026-03-11' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['data_sources'][0]['id'])")

# Step 2: data_source からプロパティを取得
curl -s "https://api.notion.com/v1/data_sources/${DS_ID}" \
  -H 'Notion-Version: 2026-03-11' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"")
```

### DB クエリ

```bash
curl -s -X POST "https://api.notion.com/v1/databases/${DB_ID}/query" \
  -H 'Notion-Version: 2026-03-11' \
  -H 'Content-Type: application/json' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  -d '{"filter": {"property": "ステータス", "status": {"equals": "開発中"}}}'
```

### ページ作成 (DB 内)

```bash
curl -s -X POST 'https://api.notion.com/v1/pages' \
  -H 'Notion-Version: 2026-03-11' \
  -H 'Content-Type: application/json' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  -d '{
    "parent": {"database_id": "'"${DB_ID}"'"},
    "properties": {
      "名前": {"title": [{"text": {"content": "ページタイトル"}}]},
      "ステータス": {"status": {"name": "未着手"}}
    }
  }'
```

### ページプロパティ取得

```bash
curl -s "https://api.notion.com/v1/pages/${PAGE_ID}" \
  -H 'Notion-Version: 2026-03-11' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"")
```

---

## Markdown API 書込 (補助的ツール)

テキストレベルの部分更新やページ全体操作に限定して使用。

### search-and-replace

```bash
curl -s -X PATCH "https://api.notion.com/v1/pages/${PAGE_ID}/markdown" \
  -H 'Notion-Version: 2026-03-11' \
  -H 'Content-Type: application/json' \
  -K <(echo "-H \"Authorization: Bearer ${NOTION_API_TOKEN}\"") \
  -d '{"type":"update_content","update_content":{"content_updates":[{"old_str":"OLD","new_str":"NEW"}]}}'
```

---

## レート制限

- 3 リクエスト/秒。API コール間に `sleep 0.35`
- 429 → `Retry-After` ヘッダー秒数だけ待機
