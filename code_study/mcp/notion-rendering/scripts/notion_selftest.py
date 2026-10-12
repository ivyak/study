#!/usr/bin/env python3
"""notion-rendering 投入層のラウンドトリップ検証ハーネス.

`NOTION_API_TOKEN_PRIVATE` のインテグレーションが共有しているページ配下に
一時スクラッチページを作り、`append_children` で「壊れやすい」ブロックツリーを
投入 → `get_block_children` で再帰読み戻し → 期待構造と突き合わせて PASS/FAIL を出す。

不具合 1 (toggle 内 table が 0 行) / 不具合 2 (深いネスト toggle で先頭 callout 以外ロスト)
の再現 + 修正後の回帰ガードを兼ねる。

使い方:
    python3 notion_selftest.py [--parent <page_id>] [--keep]

    --parent  スクラッチページを作る親ページ ID。省略時は search で 1 件目を採用。
    --keep    実行後にスクラッチページを archive せず残す。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "_shared"))
sys.path.insert(0, str(Path(__file__).parent / "lib"))

from common import ensure_deps  # noqa: E402
from skillenv import resolve_token  # noqa: E402

ensure_deps(["requests", "markdown_it"])

from notion_client import NotionClient, NotionAPIError  # noqa: E402
from preprocess import preprocess  # noqa: E402
from md_to_blocks import markdown_to_blocks  # noqa: E402

TOKEN_VAR = "NOTION_API_TOKEN_PRIVATE"


def md_to_blocks(md: str) -> list[dict]:
    """CLI と同じ経路 (preprocess → markdown_to_blocks) で MD を blocks に変換."""
    return markdown_to_blocks(preprocess(md), image_id_map={}, base_dir=Path.cwd())


# ── ブロックビルダ (md_to_blocks の出力と同形を手で組む) ──────────────────────

def rt(text: str) -> list[dict]:
    return [{
        "type": "text",
        "text": {"content": text},
        "annotations": {
            "bold": False, "italic": False, "strikethrough": False,
            "underline": False, "code": False, "color": "default",
        },
    }]


def paragraph(text: str) -> dict:
    return {"type": "paragraph", "paragraph": {"rich_text": rt(text)}}


def bullet(text: str, children: list[dict] | None = None) -> dict:
    body: dict = {"rich_text": rt(text)}
    if children:
        body["children"] = children
    return {"type": "bulleted_list_item", "bulleted_list_item": body}


def heading_toggle(level: int, text: str, children: list[dict]) -> dict:
    key = f"heading_{level}"
    return {"type": key, key: {
        "rich_text": rt(text), "is_toggleable": True, "children": children,
    }}


def toggle(text: str, children: list[dict]) -> dict:
    return {"type": "toggle", "toggle": {"rich_text": rt(text), "children": children}}


def callout(text: str, emoji: str = "💡", children: list[dict] | None = None) -> dict:
    body: dict = {"rich_text": rt(text), "icon": {"type": "emoji", "emoji": emoji}}
    if children:
        body["children"] = children
    return {"type": "callout", "callout": body}


def table(header: list[str], data_rows: list[list[str]]) -> dict:
    width = len(header)
    rows = [{"type": "table_row", "table_row": {"cells": [rt(c) for c in header]}}]
    for r in data_rows:
        rows.append({"type": "table_row", "table_row": {"cells": [rt(c) for c in r]}})
    return {"type": "table", "table": {
        "table_width": width, "has_column_header": True,
        "has_row_header": False, "children": rows,
    }}


def columns(*cols: list[dict]) -> dict:
    return {"type": "column_list", "column_list": {"children": [
        {"type": "column", "column": {"children": list(c)}} for c in cols
    ]}}


# ── 読み戻し → shape 抽出 ────────────────────────────────────────────────────

def read_tree(client: NotionClient, block_id: str) -> list[dict]:
    """block_id 直下を再帰取得して [{type,is_toggleable,text,table_rows,children}] を返す."""
    out: list[dict] = []
    for b in client.get_block_children(block_id):
        t = b["type"]
        body = b.get(t, {})
        node: dict = {"type": t}
        if body.get("is_toggleable"):
            node["is_toggleable"] = True
        richt = body.get("rich_text")
        if richt:
            node["text"] = "".join(
                x.get("text", {}).get("content", "") or x.get("plain_text", "")
                for x in richt
            )
        if t == "table":
            node["table_width"] = body.get("table_width")
        if b.get("has_children"):
            node["children"] = read_tree(client, b["id"])
        out.append(node)
    return out


def find(nodes: list[dict], type_: str) -> dict | None:
    for n in nodes:
        if n["type"] == type_:
            return n
    return None


# ── テストケース ────────────────────────────────────────────────────────────

class Result:
    def __init__(self) -> None:
        self.passed: list[str] = []
        self.failed: list[tuple[str, str]] = []

    def check(self, name: str, cond: bool, detail: str = "") -> None:
        if cond:
            self.passed.append(name)
            print(f"  PASS  {name}")
        else:
            self.failed.append((name, detail))
            print(f"  FAIL  {name}  -- {detail}")


def case_table_in_toggle(client: NotionClient, page_id: str, res: Result) -> None:
    """不具合 1: page 直下 heading-toggle 内の table が全行揃うか."""
    print("\n[case1] heading-toggle 直下の table")
    tree = [heading_toggle(3, "結果(case1)", [table(["区分", "値", "備考"], [["a", "1", "x"], ["b", "2", "y"]])])]
    client.append_children(page_id, tree)
    got = read_tree(client, page_id)
    h = next((n for n in got if n.get("text", "").startswith("結果(case1)")), None)
    res.check("case1: heading-toggle 生成", h is not None and h.get("is_toggleable") is True, repr(h))
    if not h:
        return
    tb = find(h.get("children", []), "table")
    res.check("case1: table 生成", tb is not None, repr(h.get("children")))
    if tb:
        rows = tb.get("children", [])
        res.check("case1: table 行数=3 (ヘッダ+2)", len(rows) == 3, f"rows={len(rows)} width={tb.get('table_width')}")
        res.check("case1: table_width=3", tb.get("table_width") == 3, f"width={tb.get('table_width')}")


def case_nested_toggle_callout_first(client: NotionClient, page_id: str, res: Result) -> None:
    """不具合 2: bullet > heading-toggle で先頭 callout の後続が揃うか."""
    print("\n[case2] bullet > heading-toggle, 先頭 callout + 箇条書き*3 + callout")
    children = [
        callout("注意事項です", emoji="⚠️"),
        bullet("箇条書き1"),
        bullet("箇条書き2"),
        bullet("箇条書き3"),
        callout("まとめのコールアウト", emoji="💡"),
    ]
    tree = [bullet("親項目(case2)", [heading_toggle(3, "リスク(case2)", children)])]
    client.append_children(page_id, tree)
    got = read_tree(client, page_id)
    parent = next((n for n in got if n.get("text", "").startswith("親項目(case2)")), None)
    res.check("case2: 親 bullet 生成", parent is not None, repr(parent))
    if not parent:
        return
    h = find(parent.get("children", []), "heading_3")
    res.check("case2: ネスト heading-toggle 生成", h is not None, repr(parent.get("children")))
    if not h:
        return
    kids = h.get("children", [])
    types = [k["type"] for k in kids]
    res.check(
        "case2: トグル直下に 5 ブロック (callout, bullet*3, callout)",
        types == ["callout", "bulleted_list_item", "bulleted_list_item", "bulleted_list_item", "callout"],
        f"types={types}",
    )


def case_bullet_first_control(client: NotionClient, page_id: str, res: Result) -> None:
    """不具合 2 対照: 先頭が箇条書きなら揃う (既知)."""
    print("\n[case2b] 対照: bullet > heading-toggle, 先頭 箇条書き*3")
    children = [bullet("項目A"), bullet("項目B"), bullet("項目C")]
    tree = [bullet("親項目(case2b)", [heading_toggle(3, "対照(case2b)", children)])]
    client.append_children(page_id, tree)
    got = read_tree(client, page_id)
    parent = next((n for n in got if n.get("text", "").startswith("親項目(case2b)")), None)
    if not parent:
        res.check("case2b: 親 bullet 生成", False, "親 bullet 無し")
        return
    h = find(parent.get("children", []), "heading_3")
    kids = h.get("children", []) if h else []
    res.check("case2b: トグル直下に 3 箇条書き", len(kids) == 3 and all(k["type"] == "bulleted_list_item" for k in kids), f"kids={[k['type'] for k in kids]}")


def case_table_in_column(client: NotionClient, page_id: str, res: Result) -> None:
    """境界: column 内 table (column_list>column>table>row = 深さ 4)."""
    print("\n[case3] column 内 table (深さ超過の境界)")
    tree = [columns(
        [paragraph("左カラム"), table(["k", "v"], [["a", "1"]])],
        [paragraph("右カラム")],
    )]
    client.append_children(page_id, tree)
    got = read_tree(client, page_id)
    cl = find(got, "column_list")
    res.check("case3: column_list 生成", cl is not None, repr([n["type"] for n in got]))
    if not cl:
        return
    cols = cl.get("children", [])
    res.check("case3: column 2 つ", len(cols) == 2, f"cols={len(cols)}")
    if cols:
        tb = find(cols[0].get("children", []), "table")
        res.check("case3: 左カラムに table", tb is not None, repr(cols[0].get("children")))
        if tb:
            res.check("case3: column 内 table 行数=2", len(tb.get("children", [])) == 2, f"rows={len(tb.get('children', []))}")


def case_callout_with_children(client: NotionClient, page_id: str, res: Result) -> None:
    """境界: callout が children を持つ (toggle>callout>bullets = 深さ 3)."""
    print("\n[case4] toggle > callout(children=bullets)")
    tree = [toggle("まとめ(case4)", [callout("結論です", emoji="💡", children=[bullet("根拠1"), bullet("根拠2")])])]
    client.append_children(page_id, tree)
    got = read_tree(client, page_id)
    tg = next((n for n in got if n.get("text", "").startswith("まとめ(case4)")), None)
    co = find(tg.get("children", []), "callout") if tg else None
    res.check("case4: toggle > callout", co is not None, repr(tg))
    if co:
        kids = co.get("children", [])
        res.check("case4: callout 直下に 2 箇条書き", len(kids) == 2 and all(k["type"] == "bulleted_list_item" for k in kids), f"kids={[k['type'] for k in kids]}")


def case_md_callout_then_table(client: NotionClient, page_id: str, res: Result) -> None:
    """不具合 1 (MD 経路): callout の直後 (空行なし) の table が巻き込まれず残るか."""
    print("\n[md1] MD: callout の直後に table (空行なし)")
    md = (
        '## 結果md1 {toggle="true"}\n'
        "> 💡 結論です\n"
        "| 区分 | 値 |\n|---|---|\n| a | 1 |\n"
    )
    client.append_children(page_id, md_to_blocks(md))
    got = read_tree(client, page_id)
    h = next((n for n in got if n.get("text", "").startswith("結果md1")), None)
    kids = h.get("children", []) if h else []
    types = [k["type"] for k in kids]
    res.check("md1: トグル直下に callout + table", types == ["callout", "table"], f"types={types}")
    tb = find(kids, "table")
    if tb:
        res.check("md1: table 行数=2", len(tb.get("children", [])) == 2, f"rows={len(tb.get('children', []))}")


def case_md_callout_bullets_table(client: NotionClient, page_id: str, res: Result) -> None:
    """不具合 2 (MD 経路): callout 先頭 + 箇条書き + table が全て残るか."""
    print("\n[md2] MD: callout + 箇条書き*3 + table (空行なし混在)")
    md = (
        '## 結果md2 {toggle="true"}\n'
        "> ⚠️ 重要な注意です\n"
        "- 箇条書き1\n- 箇条書き2\n- 箇条書き3\n\n"
        "| 区分 | 値 |\n|---|---|\n| a | 1 |\n| b | 2 |\n"
    )
    client.append_children(page_id, md_to_blocks(md))
    got = read_tree(client, page_id)
    h = next((n for n in got if n.get("text", "").startswith("結果md2")), None)
    kids = h.get("children", []) if h else []
    types = [k["type"] for k in kids]
    res.check(
        "md2: callout + bullet*3 + table が全て残る",
        types == ["callout", "bulleted_list_item", "bulleted_list_item", "bulleted_list_item", "table"],
        f"types={types}",
    )


def case_md_nested_shorthand_in_list(client: NotionClient, page_id: str, res: Result) -> None:
    """インデントされた ###{toggle} / > callout がリスト項目内で正しく入れ子になるか."""
    print("\n[md3] MD: bullet 配下にインデント ###{toggle} + > callout + 箇条書き")
    md = (
        "- 親項目md3\n"
        '  ### リスクmd3 {toggle="true"}\n'
        "  > ⚠️ 注意事項です\n"
        "  - 箇条書き1\n"
        "  - 箇条書き2\n"
        "  > 💡 まとめ\n"
    )
    client.append_children(page_id, md_to_blocks(md))
    got = read_tree(client, page_id)
    parent = next((n for n in got if n.get("text", "").startswith("親項目md3")), None)
    res.check("md3: 親 bullet 生成", parent is not None, repr(parent))
    if not parent:
        return
    h = find(parent.get("children", []), "heading_3")
    res.check("md3: インデント見出しがトグル化", h is not None and h.get("is_toggleable") is True, repr(parent.get("children")))
    if not h:
        return
    types = [k["type"] for k in h.get("children", [])]
    res.check(
        "md3: トグル直下に callout + bullet*2 + callout",
        types == ["callout", "bulleted_list_item", "bulleted_list_item", "callout"],
        f"types={types}",
    )


def case_md_consecutive_callouts(client: NotionClient, page_id: str, res: Result) -> None:
    """連続する絵文字始まり `>` 行が別々の callout に分割されるか."""
    print("\n[md4] MD: 連続する絵文字 callout は別ブロックに分割")
    md = (
        '## 結果md4 {toggle="true"}\n'
        "> 💡 結論1\n"
        "> ⚠️ 結論2\n"
        "通常段落\n"
    )
    client.append_children(page_id, md_to_blocks(md))
    got = read_tree(client, page_id)
    h = next((n for n in got if n.get("text", "").startswith("結果md4")), None)
    kids = h.get("children", []) if h else []
    types = [k["type"] for k in kids]
    res.check(
        "md4: callout 2 つ + paragraph",
        types == ["callout", "callout", "paragraph"],
        f"types={types}",
    )


CASES = [
    case_table_in_toggle,
    case_nested_toggle_callout_first,
    case_bullet_first_control,
    case_table_in_column,
    case_callout_with_children,
    case_md_callout_then_table,
    case_md_callout_bullets_table,
    case_md_nested_shorthand_in_list,
    case_md_consecutive_callouts,
]


# ── ドライバ ────────────────────────────────────────────────────────────────

def pick_parent(client: NotionClient) -> str | None:
    pages = client.search(filter_type="page")
    if not pages:
        return None
    return pages[0]["id"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--parent", help="スクラッチページの親 page_id")
    ap.add_argument("--keep", action="store_true", help="実行後にスクラッチページを残す")
    args = ap.parse_args()

    token = resolve_token((TOKEN_VAR,))
    client = NotionClient(token, max_retries=3)

    parent = args.parent or pick_parent(client)
    if not parent:
        print(
            "ERROR: アクセス可能なページがありません。Notion でこのインテグレーション"
            "(トークン1) にページを Connection 追加するか、--parent <page_id> を渡してください。",
            file=sys.stderr,
        )
        return 2

    print(f"親ページ: {parent}")
    scratch = client.create_page(parent_page_id=parent, title="[selftest] notion-rendering 検証")
    scratch_id = scratch["id"]
    print(f"スクラッチページ作成: {scratch_id}")

    res = Result()
    try:
        for case in CASES:
            try:
                case(client, scratch_id, res)
            except NotionAPIError as e:
                res.check(case.__name__, False, f"APIError {e.status_code}: {e.body[:200]}")
            except Exception as e:  # noqa: BLE001
                res.check(case.__name__, False, f"{type(e).__name__}: {e}")
    finally:
        if args.keep:
            print(f"\n--keep 指定: スクラッチページを残します -> {scratch_id}")
        else:
            try:
                client.delete_block(scratch_id)
                print(f"\nスクラッチページを archive: {scratch_id}")
            except NotionAPIError as e:
                print(f"\n後始末失敗 (手動削除してください {scratch_id}): {e}", file=sys.stderr)

    print(f"\n==== 結果: PASS {len(res.passed)} / FAIL {len(res.failed)} ====")
    for name, detail in res.failed:
        print(f"  FAIL {name}: {detail}")
    return 1 if res.failed else 0


if __name__ == "__main__":
    sys.exit(main())
