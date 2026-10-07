#!/usr/bin/env python3
"""Notion CLI - Block API / Markdown API を簡単に叩くための CLI ツール.

使い方:
  notion_cli.py read <page_id>                      # Markdown をプレーンテキストで stdout に出す
  notion_cli.py write <block_id> --md <file> [--after <id>] [--position start|end]
  notion_cli.py write <block_id> --md-stdin [--after <id>] [--position start|end]
  notion_cli.py write <block_id> --json-stdin
  notion_cli.py update <page_id> --old "X" --new "Y" [--replace-all]
  notion_cli.py append-md <page_id> --content "MD文字列" (- で stdin)
  notion_cli.py delete <block_id>
  notion_cli.py update-block <block_id>              # stdin から Block JSON
  notion_cli.py blocks <block_id> [--recursive] [--format summary|json]
  notion_cli.py search [query] [--type page|database]
  notion_cli.py get-page <page_id>
  notion_cli.py update-page <page_id> --props '{...}'
  notion_cli.py query <db_id> [--filter '{...}']
  notion_cli.py create-page --parent-db <db_id> --props '{...}'
  notion_cli.py db-schema <db_id>
  notion_cli.py upload <file_path> [--block-id <id>] [--caption "..."]
  notion_cli.py comment <page_id> --text "..." (- で stdin)

出力は JSON(read / blocks --format summary はプレーンテキスト)。
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from common import _ok, _fail, ensure_deps, mount_warnings, run_cli  # noqa: E402
from skillenv import resolve_token  # noqa: E402

ensure_deps(["requests", "markdown_it"])

TOKEN_KEYS = ("NOTION_API_TOKEN",)


def _notion_mcp_extract(env: dict) -> str | None:
    """旧 Notion MCP 設定(OPENAPI_MCP_HEADERS の Authorization)からトークンを取り出す."""
    try:
        headers = json.loads(env.get("OPENAPI_MCP_HEADERS", "{}"))
        auth = headers.get("Authorization", "")
        return auth.replace("Bearer ", "") or None
    except (json.JSONDecodeError, AttributeError):
        return None


def _libs():
    """依存ライブラリを持つ lib は遅延 import(--help を依存無しでも出せるようにする)."""
    from notion_client import NotionClient, NotionAPIError
    return NotionClient, NotionAPIError


def _get_client(*, retries: int = 0):
    """トークンを解決して NotionClient を返す.

    書き込み(append 等)は非冪等なので既定はリトライ無し。読み取り系は ``retries=3`` で呼ぶ。
    """
    NotionClient, _ = _libs()
    token = resolve_token(TOKEN_KEYS, mcp_server="notion", mcp_extract=_notion_mcp_extract)
    return NotionClient(token, max_retries=retries)


def _md_to_blocks(md_text: str) -> tuple[list[dict], list[str]]:
    """Markdown テキストを Notion Block JSON に変換し、(blocks, warnings) を返す."""
    from preprocess import preprocess
    import md_to_blocks

    md_to_blocks.reset_warnings()
    blocks = md_to_blocks.markdown_to_blocks(
        preprocess(md_text), image_id_map={}, base_dir=Path.cwd(),
    )
    return blocks, list(md_to_blocks.WARNINGS)


def _parent_id_of(block: dict) -> str | None:
    """ブロックの ``parent`` から実際の親 ID (page_id / block_id / database_id) を取り出す."""
    parent = block.get("parent", {})
    ptype = parent.get("type")
    if ptype in ("page_id", "block_id", "database_id"):
        return parent.get(ptype)
    return None


def _title_of(obj: dict) -> str:
    """page / database オブジェクトからタイトル文字列を抽出する (search 表示用)."""
    if obj.get("object") == "database":
        return "".join(t.get("plain_text", "") for t in obj.get("title", []))
    for prop in obj.get("properties", {}).values():
        if prop.get("type") == "title":
            return "".join(t.get("plain_text", "") for t in prop.get("title", []))
    return ""


def _format_block_summary(
    blocks: list[dict], *, indent: int = 0, recursive_fetcher=None,
) -> list[str]:
    """ブロックリストをトークン効率の高い要約形式に変換."""
    lines: list[str] = []
    prefix = "  " * indent
    for block in blocks:
        btype = block.get("type", "unknown")
        block_id = block.get("id", "???")
        body = block.get(btype, {})
        label = btype
        if btype.startswith("heading_") and body.get("is_toggleable"):
            label = f"{btype}:toggle"
        text = ""
        rich_text = body.get("rich_text", [])
        if rich_text:
            text = "".join(
                rt.get("text", {}).get("content", "") or rt.get("plain_text", "")
                for rt in rich_text[:3]
            )
            if len(text) > 60:
                text = text[:57] + "..."
        children: list[dict] | None = None
        if block.get("has_children") and recursive_fetcher:
            children = recursive_fetcher(block["id"])
        if btype == "table":
            width = body.get("table_width", "?")
            if children is not None:
                n_rows = sum(1 for c in children if c.get("type") == "table_row")
                text = f"{width}cols x {n_rows}rows"
            else:
                text = f"{width}cols (行数は --recursive で表示)"
        line = f"{prefix}[{label}] {block_id}: {text}" if text else f"{prefix}[{label}] {block_id}"
        lines.append(line)
        if children:
            lines.extend(
                _format_block_summary(
                    children, indent=indent + 1, recursive_fetcher=recursive_fetcher,
                )
            )
    return lines


# ── サブコマンド実装 ────────────────────────────────────────────

def cmd_read(args: argparse.Namespace) -> None:
    client = _get_client(retries=3)
    result = client.read_page_markdown(args.page_id)
    md = result.get("markdown", "")
    # プレーンテキスト出力(SKILL.md に明記した例外)。欠落の可能性は stderr に警告する
    notes: list[str] = []
    if result.get("truncated"):
        notes.append("truncated=true: ページが長いため Markdown が途中で切れています。blocks --recursive で補完してください")
    unknown = result.get("unknown_block_ids") or []
    if unknown:
        notes.append(f"unknown_block_ids: Markdown 化できないブロックが {len(unknown)} 件あります(blocks で確認)")
    if notes:
        print(json.dumps({"warnings": notes}, ensure_ascii=False), file=sys.stderr)
    print(md)


def _read_children_input(args: argparse.Namespace) -> tuple[list[dict], list[str]]:
    if args.json_stdin:
        raw = sys.stdin.read()
        try:
            children = json.loads(raw)
            if isinstance(children, dict):
                children = children.get("children", [children])
        except json.JSONDecodeError as e:
            _fail("invalid_json", hint=f"有効な Block JSON を stdin に渡してください: {e}")
        return children, []
    if args.md_stdin:
        md_text = sys.stdin.read()
        warnings: list[str] = []
    elif args.md:
        warnings = mount_warnings(args.md)
        md_text = Path(args.md).read_text()
    else:
        _fail("content_missing", hint="--md, --md-stdin, --json-stdin のいずれかを指定してください。")
    blocks, conv_warnings = _md_to_blocks(md_text)
    return blocks, warnings + conv_warnings


def cmd_write(args: argparse.Namespace) -> None:
    _, NotionAPIError = _libs()
    client = _get_client()
    children, warnings = _read_children_input(args)
    if not children:
        _fail("empty_content", hint="変換結果が空です。Markdown の内容を確認してください。")

    if args.after:
        # --after のブロックは「親の直接の子」でなければ API が 400 になる。
        # 第 1 引数に関わらず after ブロックの実際の親を解決して投入先にする。
        try:
            after_block = client.get_block(args.after)
        except NotionAPIError as e:
            _fail("after_block_not_found", status_code=e.status_code,
                  hint=f"--after に渡したブロック ID を確認してください: {e}")
        target = _parent_id_of(after_block) or args.block_id
        results = client.append_children(target, children, after=args.after)
        where = f"after {args.after}"
    elif args.position == "start":
        results = client.append_children(args.block_id, children, position_start=True)
        where = "start"
    else:
        results = client.append_children(args.block_id, children)
        where = "end"
    block_ids = [r["id"] for r in results]
    _ok(block_ids=block_ids, message=f"{len(block_ids)} blocks written ({where})", warnings=warnings)


def cmd_update(args: argparse.Namespace) -> None:
    client = _get_client()
    result = client.update_content(
        args.page_id, old_str=args.old, new_str=args.new, replace_all=args.replace_all,
    )
    _ok(result)


def cmd_append_md(args: argparse.Namespace) -> None:
    client = _get_client()
    content = sys.stdin.read() if args.content == "-" else args.content
    children, warnings = _md_to_blocks(content)
    if not children:
        _fail("empty_content", hint="変換結果が空です。Markdown の内容を確認してください。")
    results = client.append_children(args.page_id, children)
    block_ids = [r["id"] for r in results]
    _ok(block_ids=block_ids, message=f"{len(block_ids)} blocks appended", warnings=warnings)


def cmd_delete(args: argparse.Namespace) -> None:
    client = _get_client()
    client.delete_block(args.block_id)
    _ok(message=f"Block {args.block_id} deleted")


def cmd_update_block(args: argparse.Namespace) -> None:
    client = _get_client()
    raw = sys.stdin.read()
    try:
        block_data = json.loads(raw)
    except json.JSONDecodeError as e:
        _fail("invalid_json", hint=f"有効な Block JSON を stdin に渡してください: {e}")
    _ok(client.update_block(args.block_id, block_data=block_data))


def cmd_blocks(args: argparse.Namespace) -> None:
    client = _get_client(retries=3)
    blocks = client.get_block_children(args.block_id)
    if args.format == "summary":
        fetcher = client.get_block_children if args.recursive else None
        print("\n".join(_format_block_summary(blocks, recursive_fetcher=fetcher)))
        return
    if args.recursive:
        def _enrich(block_list: list[dict]) -> list[dict]:
            for b in block_list:
                if b.get("has_children"):
                    b["_children"] = _enrich(client.get_block_children(b["id"]))
            return block_list
        blocks = _enrich(blocks)
    # Notion API と同形 ({"results": [...]})。--recursive 時は独自キー _children を足す
    print(json.dumps({"results": blocks}, ensure_ascii=False, indent=2))


def cmd_search(args: argparse.Namespace) -> None:
    client = _get_client(retries=3)
    results = client.search(query=args.query, filter_type=args.type)
    items = [
        {"id": r.get("id"), "object": r.get("object"), "title": _title_of(r), "url": r.get("url")}
        for r in results
    ]
    _ok(items, count=len(items))


def cmd_get_page(args: argparse.Namespace) -> None:
    _ok(_get_client(retries=3).get_page(args.page_id))


def _parse_json_arg(raw: str, what: str) -> dict:
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        _fail("invalid_json", hint=f"{what} が JSON として読めません: {e}")
        raise  # unreachable


def cmd_update_page(args: argparse.Namespace) -> None:
    props = _parse_json_arg(args.props, "--props")
    _ok(_get_client().update_page(args.page_id, properties=props))


def cmd_query(args: argparse.Namespace) -> None:
    filter_obj = _parse_json_arg(args.filter, "--filter") if args.filter else None
    _ok(_get_client(retries=3).query_database(args.db_id, filter=filter_obj))


def cmd_create_page(args: argparse.Namespace) -> None:
    props = _parse_json_arg(args.props, "--props")
    result = _get_client().create_database_page(args.parent_db, properties=props)
    _ok(result, page_id=result.get("id", ""))


def cmd_db_schema(args: argparse.Namespace) -> None:
    _ok(_get_client(retries=3).get_db_schema(args.db_id))


# 画像として埋め込む拡張子。これ以外(xlsx/pdf/docx/csv 等)は file ブロックにする。
_IMAGE_EXTENSIONS = frozenset(
    {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".bmp", ".tif", ".tiff", ".ico", ".heic"}
)
_UPLOAD_LIMIT_BYTES = 20 * 1024 * 1024  # Notion single_part 上限


def cmd_upload(args: argparse.Namespace) -> None:
    path = Path(args.file_path)
    if not path.is_file():
        _fail("file_not_found", hint=f"ファイルがありません: {path}")
    if path.stat().st_size > _UPLOAD_LIMIT_BYTES:
        _fail("file_too_large", hint="single_part アップロードの上限 20MB を超えています。圧縮するか分割してください。")
    warnings = mount_warnings(path)
    client = _get_client()
    upload_id = client.upload_file(str(path))
    if args.block_id:
        ext = path.suffix.lower()
        block_type = "image" if ext in _IMAGE_EXTENSIONS else "file"
        body: dict = {"type": "file_upload", "file_upload": {"id": upload_id}}
        if args.caption:
            body["caption"] = [{"type": "text", "text": {"content": args.caption}}]
        client.append_children(args.block_id, [{"type": block_type, block_type: body}])
        _ok(upload_id=upload_id, message=f"File uploaded and {block_type} block appended", warnings=warnings)
    else:
        _ok(upload_id=upload_id, message="File uploaded (no block created)", warnings=warnings)


def cmd_comment(args: argparse.Namespace) -> None:
    text = sys.stdin.read().strip() if args.text == "-" else args.text
    _ok(_get_client().add_comment(args.page_id, text=text))


# ── argparse 構築 ──────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="notion_cli", description="Notion API CLI - Block/Markdown API を簡単に叩く",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("read", help="ページを Markdown で取得(プレーンテキスト出力)")
    p.add_argument("page_id")
    p.set_defaults(func=cmd_read)

    p = sub.add_parser("write", help="MD/JSON をブロックに書き込み")
    p.add_argument("block_id")
    p.add_argument("--md", help="Markdown ファイルパス")
    p.add_argument("--md-stdin", action="store_true", help="stdin から Markdown を読む")
    p.add_argument("--json-stdin", action="store_true", help="stdin から Block JSON を読む")
    p.add_argument("--after", help="指定ブロック ID の後に挿入(親は自動解決)")
    p.add_argument("--position", choices=["start", "end"], default="end")
    p.set_defaults(func=cmd_write)

    p = sub.add_parser("update", help="テキスト部分置換 (Markdown API)")
    p.add_argument("page_id")
    p.add_argument("--old", required=True, help="置換元テキスト")
    p.add_argument("--new", required=True, help="置換先テキスト")
    p.add_argument("--replace-all", action="store_true", help="全箇所を置換")
    p.set_defaults(func=cmd_update)

    p = sub.add_parser("append-md", help="ページ末尾に Markdown テキスト追記")
    p.add_argument("page_id")
    p.add_argument("--content", required=True, help="追記する Markdown (- で stdin)")
    p.set_defaults(func=cmd_append_md)

    p = sub.add_parser("delete", help="ブロック削除")
    p.add_argument("block_id")
    p.set_defaults(func=cmd_delete)

    p = sub.add_parser("update-block", help="既存ブロックを更新(stdin から Block JSON)")
    p.add_argument("block_id")
    p.set_defaults(func=cmd_update_block)

    p = sub.add_parser("blocks", help="子ブロック一覧")
    p.add_argument("block_id")
    p.add_argument("--recursive", action="store_true", help="再帰的に取得")
    p.add_argument("--format", choices=["summary", "json"], default="summary")
    p.set_defaults(func=cmd_blocks)

    p = sub.add_parser("search", help="共有されているページ/DB を検索")
    p.add_argument("query", nargs="?", default=None, help="検索クエリ (省略で全件)")
    p.add_argument("--type", choices=["page", "database"], help="object 種別で絞り込み")
    p.set_defaults(func=cmd_search)

    p = sub.add_parser("get-page", help="ページプロパティ取得")
    p.add_argument("page_id")
    p.set_defaults(func=cmd_get_page)

    p = sub.add_parser("update-page", help="ページプロパティ更新")
    p.add_argument("page_id")
    p.add_argument("--props", required=True, help="プロパティ JSON")
    p.set_defaults(func=cmd_update_page)

    p = sub.add_parser("query", help="DB クエリ")
    p.add_argument("db_id")
    p.add_argument("--filter", help="フィルタ JSON")
    p.set_defaults(func=cmd_query)

    p = sub.add_parser("create-page", help="DB 内にページ作成")
    p.add_argument("--parent-db", required=True, help="DB ID")
    p.add_argument("--props", required=True, help="プロパティ JSON")
    p.set_defaults(func=cmd_create_page)

    p = sub.add_parser("db-schema", help="DB プロパティ取得")
    p.add_argument("db_id")
    p.set_defaults(func=cmd_db_schema)

    p = sub.add_parser("upload", help="ファイルアップロード(拡張子で image/file を自動判定)")
    p.add_argument("file_path")
    p.add_argument("--block-id", help="ブロックを追加する親ブロック ID(省略時はアップロードのみ)")
    p.add_argument("--caption", help="キャプション(画像・ファイル共通)")
    p.set_defaults(func=cmd_upload)

    p = sub.add_parser("comment", help="ページコメント追加")
    p.add_argument("page_id")
    p.add_argument("--text", required=True, help="コメントテキスト (- で stdin)")
    p.set_defaults(func=cmd_comment)

    return parser


_STATUS_HINTS = {
    401: "トークンが無効です。.env の NOTION_API_TOKEN を確認してください。",
    403: "権限がありません。インテグレーションを対象ページに「接続」してください。",
    404: "ID が見つかりません。ID の誤りか、インテグレーションが未接続です(search で見えるか確認)。",
    409: "競合しました。少し待って再試行してください。",
    429: "レート制限です。少し待ってから再試行してください。",
}


def main() -> None:
    args = build_parser().parse_args()
    _, NotionAPIError = _libs()
    try:
        args.func(args)
    except NotionAPIError as e:
        _fail(
            f"notion_api_error_{e.status_code}",
            status_code=e.status_code,
            hint=_STATUS_HINTS.get(e.status_code, f"{e}: {e.body}"),
            body=e.body,
        )
    except RuntimeError as e:
        _fail("token_unresolved", hint=str(e))


if __name__ == "__main__":
    run_cli(main)
