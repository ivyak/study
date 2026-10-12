<!-- FALLBACK: notion_cli.py がエラーハンドリング・リトライを内部処理する。CLI で解決できないエラーの場合のみ参照 -->

# エラーハンドリングガイド

Notion API のエラーパターンと対処法。

---

## HTTP ステータスコード

| コード | 意味 | 対処 |
|--------|------|------|
| 400 | バリデーションエラー | リクエスト内容を修正 |
| 401 | 認証エラー (トークン無効) | トークンを確認・再取得 |
| 403 | 権限不足 | ページの共有設定を確認 |
| 404 | ページ/ブロック不存在 | ID を確認、アクセス権も疑う |
| 409 | 競合 (同時編集) | 再読取して再試行 |
| 429 | レート制限 | `Retry-After` ヘッダーの秒数だけ待機して再試行 |
| 500/502/503 | サーバーエラー | 指数バックオフで再試行 (最大 3 回) |

---

## Block API 固有エラー (メイン)

### table_width 不一致

```json
{"code": "validation_error", "message": "table_width does not match ..."}
```

対処: `table_width` と各 `table_row` の `cells` 配列長を一致させる。

### children の配置ミス

```json
{"code": "validation_error", "message": "children is not allowed ..."}
```

対処:
- `is_toggleable: false` の heading に `children` を指定していないか確認
- table の `children` は `table` オブジェクト内に配置 (ブロックルートではない)

### depth 超過

```json
{"code": "validation_error", "message": "Maximum nesting depth ..."}
```

対処: 深さ 2 まで。3 段目以降は別リクエストで追加。

### 100 ブロック超過

対処: children 配列を 100 以下のチャンクに分割して送信。

---

## Markdown API 固有エラー (補助ツール用)

### old_str が見つからない

```json
{"code": "validation_error", "message": "Could not find the text ..."}
```

原因:
- テキストの一部が異なる (空白、改行、特殊文字)
- ページが他のユーザーに更新された

対処:
1. `GET /v1/pages/{id}/markdown` で最新内容を取得
2. 正確なテキストを確認して再試行

### old_str が複数箇所にマッチ

```json
{"code": "validation_error", "message": "Found multiple matches ..."}
```

対処:
- より長い/ユニークな `old_str` を使用
- または `"replace_all_matches": true` を追加

### 子ページ/DB の削除拒否

```json
{"code": "validation_error", "message": "Cannot delete child pages ..."}
```

対処:
- `"allow_deleting_content": true` をコマンドに追加

### 対象がデータベースまたは synced page

```json
{"code": "validation_error", "message": "Target is a database ..."}
```

対処:
- データベースページの場合はページ内コンテンツ部分のみ操作可能
- synced page の場合はオリジナルを操作

---

## リトライ戦略

```bash
# 429 レスポンスのリトライ例
retry_after=$(echo "$response_headers" | grep -i 'retry-after' | awk '{print $2}')
if [ -n "$retry_after" ]; then
  sleep "$retry_after"
else
  sleep 1
fi
```

指数バックオフ (500 系エラー):
- 1 回目: 1 秒待機
- 2 回目: 2 秒待機
- 3 回目: 4 秒待機
- 最大 3 回で打ち切り

---

## よくある落とし穴

1. **トークンのコマンド引数露出**: `ps` や shell history に残る。必ず `-K <(...)` を使う
2. **Notion-Version の不一致**: Markdown API は `2026-03-11`、Block API は `2022-06-28` でも可
3. **JSON の改行**: `\n` を使う。シェルのリテラル改行ではなく JSON エスケープ
4. **ページネーション忘れ**: `has_more: true` を見逃すと後半のブロックを取りこぼす
5. **Pre-signed URL の期限切れ**: 読取で得たファイル URL はすぐ使う (短時間で失効)
6. **空テキスト**: `rich_text` に空文字列の要素を入れるとエラーになる場合がある
7. **同時編集**: 他ユーザーの編集と競合すると `update_content` の `old_str` マッチが失敗する
