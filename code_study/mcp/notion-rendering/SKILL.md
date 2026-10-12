---
name: notion-rendering
description: |
    Notion ページの読み書きを行う際に必ず参照するガイド。Notion MCP は使用せず、
    scripts/notion_cli.py で Notion API を叩く。コンテンツは Markdown で記述し、CLI が Block JSON 変換・
    100 件分割・ネスト整形・API 呼び出しを内部処理する。Notion に触れる作業では軽微な確認でも
    まずこのスキルを参照すること。
when_to_use: |
    Notion ページに書き込む、Notion に記録する、Notion ページを読む、
    Notion に追記する、タスクページに書く、報告を Notion に書く、
    検証結果を Notion に記録、進捗を Notion に残す、
    Notion ページの内容を確認、Notion ブロックを操作する、
    Notion API を叩く、Notion のテーブルを作成する
user-invocable: false
---

# Notion Rendering ガイド

Notion の読み書きは `scripts/notion_cli.py` で行う。コンテンツは **Markdown** で記述する。
Notion MCP は使用しない。

**掟(違反すると内容が欠ける/二重投稿になる)**:

- **`warnings` を必ず読む**。変換で内容が欠け得る事象(2000 字超の切り捨て・rich_text 100 要素超・
  未対応 HTML・ローカル画像)は成功応答の `warnings` に載る。空でなければユーザーに伝える。
- **書き込みは再実行しない**(append は非冪等)。失敗したら `blocks` で状態を確認してから続きだけ書く。
  CLI も書き込み系はリトライしない。
- `read` はプレーンテキスト出力。長いページは途中で切れることがあり、その場合 stderr に
  `{"warnings": [...]}` が出る(`blocks --recursive` で補完)。
- 画像・ファイルは Markdown の `![]()` では添付されない(目印の段落 + warning になる)。
  書込後に `upload` で添付する。
- センシティブ情報を書き込まない。

## やりたいこと → 参照先

| やりたいこと | 読む reference |
|---|---|
| 通常の読み書き(MD で書く) | このファイルだけで足りる |
| callout / toggle / 列 / 表 / メンションの書き方を確かめる | [references/md-to-blocks-rules.md](references/md-to-blocks-rules.md) |
| `--json-stdin` で Block JSON を直接組む(MD で表現できない書式) | [references/block-json-templates.md](references/block-json-templates.md) |
| CLI に無い API を curl で叩く | [references/api-reference.md](references/api-reference.md) |
| API エラー(400/404/409/429)の切り分け | [references/error-handling-appendix.md](references/error-handling-appendix.md) |

## CLI コマンド

CLI パス: `~/.claude/skills/notion-rendering/scripts/notion_cli.py`(`python3 $CLI <command>` で実行)

| コマンド | 用途 | 例 |
|---------|------|-----|
| `read <page_id>` | ページを MD で取得(**プレーンテキスト出力**) | `python3 $CLI read abc123` |
| `write <block_id> --md-stdin` | MD → ブロック書込 | `echo "## Title" \| python3 $CLI write abc123 --md-stdin` |
| `write <block_id> --md <file>` | MD ファイルを書込 | `python3 $CLI write abc123 --md /tmp/report.md` |
| `write <block_id> --json-stdin` | Block JSON を直接送信 | `echo '[{...}]' \| python3 $CLI write abc123 --json-stdin` |
| `update <page_id> --old X --new Y [--replace-all]` | テキスト部分更新(リンク化不可) | `python3 $CLI update abc123 --old "旧" --new "新"` |
| `append-md <page_id> --content "MD"` | ページ末尾に MD 追記(`-` で stdin) | `python3 $CLI append-md abc123 --content "追記"` |
| `delete <block_id>` | ブロック削除 | `python3 $CLI delete abc123` |
| `update-block <block_id>` | 既存ブロック更新(stdin から Block JSON) | `echo '{...}' \| python3 $CLI update-block abc123` |
| `blocks <block_id> [--recursive] [--format summary\|json]` | 子ブロック一覧。summary は**プレーンテキスト**。json は `{"results":[...]}`(`--recursive` 時は独自キー `_children` を含む) | `python3 $CLI blocks abc123 --recursive` |
| `search [query] [--type page\|database]` | 共有されているページ/DB を検索(page ID 探索・接続確認) | `python3 $CLI search 要件定義 --type page` |
| `get-page <page_id>` | ページプロパティ取得 | |
| `update-page <page_id> --props '{...}'` | プロパティ更新 | `python3 $CLI update-page abc123 --props '{"ステータス":{"status":{"name":"完了"}}}'` |
| `query <db_id> [--filter '{...}']` | DB クエリ | `python3 $CLI query abc123 --filter '{"property":"ステータス","status":{"equals":"開発中"}}'` |
| `create-page --parent-db <db_id> --props '{...}'` | DB 内ページ作成 | |
| `db-schema <db_id>` | DB プロパティ取得 | |
| `upload <file> [--block-id <id>] [--caption "..."]` | ファイルアップロード(20MB まで)。拡張子で image / file ブロックを自動判定 | `python3 $CLI upload 図.png --block-id abc123` |
| `comment <page_id> --text "..."` | コメント追加(`-` で stdin) | |

`write` の挿入位置: `--after <block_id>`(指定ブロック後)/ `--position start`(先頭)。既定は末尾。
`--after` は対象ブロックの**実際の親を自動解決**するので、第 1 引数にはページ ID を渡してよい。
どの位置でも 100 件分割・ネスト整形は同じ経路を通る。書込件数は**今回新規作成した分のみ**を報告する。

### 出力スキーマ

```
成功: {"ok": true, "data": ..., "warnings": [...], ...extra}   ← stdout
失敗: {"ok": false, "error": "<code>", "hint": "<次の一手>", "status_code": n}   ← stderr, exit 1
write / append-md → {"ok": true, "block_ids": [...], "message": "N blocks written (end|start|after <id>)", "warnings": [...]}
search           → {"ok": true, "data": [{"id","object","title","url"}], "count": n}
upload           → {"ok": true, "upload_id": "...", "message": "..."}
例外(プレーンテキスト): read / blocks --format summary / blocks --format json
```

`error` の例: `token_unresolved` / `notion_api_error_404` / `after_block_not_found` / `empty_content` / `invalid_json`。

## Markdown → Notion ブロックの対応(CLI が変換する記法)

見出し・段落・箇条書き・コードは通常の Markdown。Notion 固有のブロックは以下の記法で書く。
ページ全体の構成・文体はプロジェクトの CLAUDE.md に従う(このスキルでは規定しない)。

| 入力内容 | Markdown での書き方 |
|---------|-------------------|
| 定量データ (3+項目) | パイプテーブル `\| col1 \| col2 \|` |
| 重要結論 | callout: 行頭が絵文字の引用 `> **💡 テキスト**`(または `> 💡 テキスト`)。先頭の絵文字がアイコンになる |
| 長い詳細 | `<details><summary>タイトル</summary>内容</details>`、または見出し始まりの引用 `> ## タイトル` + 中身(toggle になる) |
| 見出しごと折りたたみ | `## タイトル {toggle="true"}`(次の同レベル見出しまでが children) |
| 手順 | `1. ステップ` (番号付きリスト) |
| カラムレイアウト | `<columns><column>左</column><column>右</column></columns>`(各タグは**行頭に単独**で置く) |
| 画像・ファイル添付 | (md 記法ではなく) `upload <file> --block-id <id>` コマンドで添付 |

## 認証(プロジェクトごと)

トークンは **環境変数 `NOTION_API_TOKEN` → カレント上方の `.env`(全階層) → `.mcp.json`** の順に解決する。
新しいプロジェクトではプロジェクト直下 `.env` に `NOTION_API_TOKEN=` を書けば動く(`.gitignore` 済みか確認)。
インテグレーションを対象ページに「接続」していないと 404 になる(`search` で見えるか確認)。

## 書き込み時の注意

- `update` はプレーンテキスト置換でリンク化できない。リンクを入れるときは `write --after <block_id>` で
  新ブロックを書いてから旧ブロックを `delete` する。
- 実 API に対する回帰検証は `scripts/notion_selftest.py`(`.env` の `NOTION_API_TOKEN_PRIVATE` で
  検証用インテグレーションを使う。`--parent <page_id>` 配下にスクラッチページを作り、終了時に archive)。
  変換器だけの検証は `~/.claude/skills/tests/` の pytest(API 不要)。

## フォールバック

CLI で対応できない操作は [references/api-reference.md](references/api-reference.md) を読んで curl で実行する。
