"""markdown-it-py を使って md 本文を Notion blocks JSON に変換する.

対応ブロック:
  - heading_1/2/3/4（h5/h6 は heading_4 に切り詰め）
  - heading toggle: ``## タイトル {toggle="true"}`` を ``is_toggleable=true`` の
    heading に変換し、次の同 level 以下 heading 直前までを children に集約
  - paragraph / bulleted_list_item / numbered_list_item（ネスト対応）
  - code / divider / image（file_upload or external）
  - md パイプテーブル → table + table_row
  - ``<details><summary>...</summary>...</details>`` → toggle ブロック（ネスト対応）
  - ``<columns><column>...</column>...</columns>`` → column_list + column
  - inline: bold / italic / inline_code / link / mention-user
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from markdown_it import MarkdownIt
from markdown_it.token import Token

from preprocess import _extract_leading_emoji

logger = logging.getLogger(__name__)

# 1 件の rich_text で Notion が許容する最大文字数
_NOTION_TEXT_LIMIT = 2000

# 変換中に発生した「内容が欠ける可能性のある事象」を CLI に返すための収集先。
# markdown_to_blocks() は再帰的に呼ばれるので、リセットは呼び出し元(CLI)が行う。
WARNINGS: list[str] = []


def reset_warnings() -> None:
    WARNINGS.clear()


def _warn(msg: str) -> None:
    logger.warning(msg)
    if msg not in WARNINGS:
        WARNINGS.append(msg)

_BULLET_LIST = "bulleted_list_item"
_NUMBERED_LIST = "numbered_list_item"


def _new_text(
    content: str,
    *,
    bold: bool = False,
    italic: bool = False,
    code: bool = False,
    strike: bool = False,
    link: str | None = None,
) -> dict:
    """Notion rich_text 配列の要素を 1 つ組み立てる."""
    annotations = {
        "bold": bold,
        "italic": italic,
        "strikethrough": strike,
        "underline": False,
        "code": code,
        "color": "default",
    }
    if len(content) > _NOTION_TEXT_LIMIT:
        _warn(
            f"rich_text 1 要素の上限 {_NOTION_TEXT_LIMIT} 字を超えたため切り捨てました"
            f"(先頭: {content[:30]!r})"
        )
    text: dict[str, Any] = {"content": content[:_NOTION_TEXT_LIMIT]}
    if link:
        text["link"] = {"url": link}
    return {"type": "text", "text": text, "annotations": annotations}


def _new_texts(content: str, **kwargs: Any) -> list[dict]:
    """2000 字を超える本文を複数の rich_text 要素に分割して返す(切り捨てない)."""
    if len(content) <= _NOTION_TEXT_LIMIT:
        return [_new_text(content, **kwargs)]
    return [
        _new_text(content[i : i + _NOTION_TEXT_LIMIT], **kwargs)
        for i in range(0, len(content), _NOTION_TEXT_LIMIT)
    ]


# `<mention-user url="user://UUID"/>` を Notion mention rich_text に変換する
_MENTION_USER_INLINE_PATTERN = re.compile(
    r'<mention-user\s+url="user://(?P<uuid>[0-9a-fA-F-]+)"\s*/?>',
    re.IGNORECASE,
)


def _new_mention_user(uuid: str) -> dict:
    """Notion API の mention rich_text (user 参照) を組み立てる."""
    return {
        "type": "mention",
        "mention": {"type": "user", "user": {"object": "user", "id": uuid}},
        "annotations": {
            "bold": False,
            "italic": False,
            "strikethrough": False,
            "underline": False,
            "code": False,
            "color": "default",
        },
    }


def _render_inline(
    token: Token,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> tuple[list[dict], list[dict]]:
    """``inline`` トークンを rich_text 配列と、分離抽出された image ブロックに変換."""
    rich_text: list[dict] = []
    extracted_images: list[dict] = []
    bold = italic = code = strike = False
    link_url: str | None = None

    for child in token.children or []:
        t = child.type
        if t == "text":
            if not child.content:
                # 空文字 text トークンは Notion 上で意味が無いのでスキップ
                continue
            rich_text.extend(
                _new_texts(
                    child.content,
                    bold=bold,
                    italic=italic,
                    code=code,
                    strike=strike,
                    link=link_url,
                )
            )
        elif t == "strong_open":
            bold = True
        elif t == "strong_close":
            bold = False
        elif t == "em_open":
            italic = True
        elif t == "em_close":
            italic = False
        elif t == "s_open":
            strike = True
        elif t == "s_close":
            strike = False
        elif t == "code_inline":
            rich_text.extend(
                _new_texts(
                    child.content,
                    bold=bold,
                    italic=italic,
                    code=True,
                    strike=strike,
                    link=link_url,
                )
            )
        elif t == "link_open":
            link_url = child.attrGet("href") or None
        elif t == "link_close":
            link_url = None
        elif t == "softbreak" or t == "hardbreak":
            rich_text.append(_new_text("\n"))
        elif t == "image":
            extracted_images.append(_build_image_block(child, image_id_map, base_dir))
        elif t == "html_inline":
            # `<br>` `<br/>` `<br />` は改行として扱う（rich_text の \n に統一）
            stripped = child.content.strip().lower()
            if stripped in ("<br>", "<br/>", "<br />"):
                rich_text.append(
                    _new_text("\n", bold=bold, italic=italic, code=code, link=link_url)
                )
                continue
            # `<mention-user url="user://UUID"/>` は Notion mention rich_text に変換
            mention_match = _MENTION_USER_INLINE_PATTERN.fullmatch(child.content.strip())
            if mention_match:
                rich_text.append(_new_mention_user(mention_match.group("uuid").lower()))
                continue
            rich_text.append(
                _new_text(
                    child.content,
                    bold=bold,
                    italic=italic,
                    code=code,
                    strike=strike,
                    link=link_url,
                )
            )
        else:
            logger.warning("インライン トークン未対応: %s", t)
    return _merge_rich_text(rich_text), extracted_images


# Notion API は 1 ブロックの rich_text 配列を最大 100 要素まで受け付ける
_NOTION_RICH_TEXT_LIMIT = 100


def _merge_rich_text(rich_text: list[dict]) -> list[dict]:
    """連続する同スタイル(annotations + link)の text 要素を 1 要素に統合する.

    `<br>` 由来の改行などで rich_text 要素が増えがちなため、Notion API の 100 要素上限
    を回避する目的で隣接統合する。1 要素の上限 (``_NOTION_TEXT_LIMIT``) を超えそうな
    ときは統合せず分離したままにする。最終的に 100 要素超の場合は警告のうえ切り捨て。
    """
    if not rich_text:
        return rich_text
    merged: list[dict] = []
    for rt in rich_text:
        # mention 等の text 以外は隣接統合しない
        if rt.get("type") != "text":
            merged.append(rt)
            continue
        if merged:
            last = merged[-1]
            if (
                last.get("type") == "text"
                and last.get("annotations") == rt.get("annotations")
                and last.get("text", {}).get("link")
                == rt.get("text", {}).get("link")
            ):
                combined = last["text"]["content"] + rt["text"]["content"]
                if len(combined) <= _NOTION_TEXT_LIMIT:
                    last["text"]["content"] = combined
                    continue
        merged.append(rt)
    if len(merged) > _NOTION_RICH_TEXT_LIMIT:
        _warn(
            f"rich_text 要素数が API 上限 {_NOTION_RICH_TEXT_LIMIT} を超えたため切り捨てました"
            f"({len(merged)} 要素)。段落を分けてください"
        )
        merged = merged[:_NOTION_RICH_TEXT_LIMIT]
    return merged


def _build_image_block(
    token: Token,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> dict:
    """md の image トークンを Notion image ブロックに変換する."""
    src = token.attrGet("src") or ""
    alt = token.content or token.attrGet("alt") or ""
    caption = [_new_text(alt)] if alt else []

    if src.startswith(("http://", "https://")):
        return {
            "type": "image",
            "image": {"type": "external", "external": {"url": src}, "caption": caption},
        }

    # md のパスは URL エンコードされている可能性があるためデコード
    abs_path = (base_dir / unquote(src)).resolve()
    file_upload_id = image_id_map.get(abs_path)
    if not file_upload_id:
        _warn(
            f"ローカル画像 {src} は MD 経由では添付できません。"
            "書込後に `upload <file> --block-id <id>` で添付してください(本文には目印の段落を入れました)"
        )
        return {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [_new_text(f"[画像: {src}{' — ' + alt if alt else ''}]", italic=True)],
            },
        }
    return {
        "type": "image",
        "image": {
            "type": "file_upload",
            "file_upload": {"id": file_upload_id},
            "caption": caption,
        },
    }


def _find_next_sibling_heading_token(
    tokens: list[Token], start: int, level: int
) -> int:
    """``tokens[start:]`` から次の同 level 以下 heading_open の index を返す.

    fenced code 内 / details 内 / column 内 の heading は他の token type で
    囲われるため heading_open として現れない。トップレベルの heading のみを対象とする。
    見つからない場合は ``len(tokens)``。
    """
    for i in range(start, len(tokens)):
        tk = tokens[i]
        if tk.type == "heading_open":
            tk_level = int(tk.tag[1])
            if tk_level <= level:
                return i
    return len(tokens)


def _detect_heading_toggle(rich_text: list[dict]) -> tuple[bool, list[dict]]:
    """heading の rich_text 末尾の ``{toggle="true"}`` 注釈を検出して取り除く.

    戻り値は ``(is_toggle, 注釈を除いた rich_text)``。
    """
    if not rich_text:
        return False, rich_text
    last = rich_text[-1]
    if last.get("type") != "text":
        return False, rich_text
    content = last.get("text", {}).get("content", "")
    m = re.match(r'^(?P<body>.*?)\s*\{toggle="true"\}\s*$', content, re.DOTALL)
    if not m:
        return False, rich_text
    cleaned = m.group("body").rstrip()
    if cleaned:
        last["text"]["content"] = cleaned
        return True, rich_text
    return True, rich_text[:-1]


def _heading_block(
    level: int,
    rich_text: list[dict],
    *,
    is_toggleable: bool = False,
    children: list[dict] | None = None,
) -> dict:
    """heading_1/2/3/4 ブロックを返す. h5/h6 は heading_4 に切り詰め (Notion spec).

    ``is_toggleable=True`` の場合は heading toggle として ``children`` を持つ
    Notion 公式仕様の heading toggle になる。
    """
    level = min(max(level, 1), 4)
    key = f"heading_{level}"
    payload: dict[str, Any] = {
        "rich_text": rich_text,
        "is_toggleable": is_toggleable,
    }
    if is_toggleable and children:
        payload["children"] = children
    return {"type": key, key: payload}


def _code_block(token: Token) -> dict:
    language = (
        (token.info or "plain text").strip().split()[0] if token.info else "plain text"
    )
    if language not in _NOTION_CODE_LANGUAGES:
        language = "plain text"
    return {
        "type": "code",
        "code": {
            "rich_text": _new_texts(token.content.rstrip("\n")),
            "language": language,
        },
    }


_NOTION_CODE_LANGUAGES = {
    "abap",
    "arduino",
    "bash",
    "basic",
    "c",
    "clojure",
    "coffeescript",
    "c++",
    "c#",
    "css",
    "dart",
    "diff",
    "docker",
    "elixir",
    "elm",
    "erlang",
    "flow",
    "fortran",
    "f#",
    "gherkin",
    "glsl",
    "go",
    "graphql",
    "groovy",
    "haskell",
    "html",
    "java",
    "javascript",
    "json",
    "julia",
    "kotlin",
    "latex",
    "less",
    "lisp",
    "livescript",
    "lua",
    "makefile",
    "markdown",
    "markup",
    "matlab",
    "mermaid",
    "nix",
    "objective-c",
    "ocaml",
    "pascal",
    "perl",
    "php",
    "plain text",
    "powershell",
    "prolog",
    "protobuf",
    "python",
    "r",
    "reason",
    "ruby",
    "rust",
    "sass",
    "scala",
    "scheme",
    "scss",
    "shell",
    "sql",
    "swift",
    "typescript",
    "vb.net",
    "verilog",
    "vhdl",
    "visual basic",
    "webassembly",
    "xml",
    "yaml",
}


# ---- &lt;details&gt; トグルブロック -----------------------------------------------

# `<details ...>` 開始タグ（属性は無視、行頭縛り）
_DETAILS_OPEN_PATTERN = re.compile(r"^\s*<details\b[^>]*>", re.IGNORECASE)
# `</details>` 閉じタグ（前後空白許容）
_DETAILS_CLOSE_PATTERN = re.compile(r"^\s*</details>\s*$", re.IGNORECASE)
# 文字列内の任意位置にある <details> 開始タグ（ネスト balance 計算用）
_DETAILS_OPEN_ANYWHERE = re.compile(r"<details\b[^>]*>", re.IGNORECASE)
# `<summary>...</summary>` 抽出（同一行内）
_SUMMARY_PATTERN = re.compile(r"<summary>(.*?)</summary>", re.IGNORECASE | re.DOTALL)


# `<callout emoji="...">` ブロック（preprocess が `> 💡 ...` から生成）。属性 emoji を拾う。
_CALLOUT_OPEN_PATTERN = re.compile(r"^\s*<callout\b[^>]*>", re.IGNORECASE)
_CALLOUT_CLOSE_PATTERN = re.compile(r"^\s*</callout>\s*$", re.IGNORECASE)
_CALLOUT_EMOJI_PATTERN = re.compile(
    r'<callout\b[^>]*\bemoji="(?P<emoji>[^"]*)"', re.IGNORECASE
)
# 開始タグ直後 〜 対応する </callout> 直前の本文を抽出（同一ブロック完結ケース）
_CALLOUT_INNER_PATTERN = re.compile(
    r"<callout\b[^>]*>(?P<inner>.*?)</callout>", re.IGNORECASE | re.DOTALL
)


def _is_details_open(content: str) -> bool:
    return bool(_DETAILS_OPEN_PATTERN.match(content))


def _is_callout_open(content: str) -> bool:
    return bool(_CALLOUT_OPEN_PATTERN.match(content))


def _parse_md_fragment(
    text: str,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> list[dict]:
    """md 断片を再 parse して blocks に変換する (callout/details の本文・末尾用)."""
    md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    return _tokens_to_blocks(md.parse(text), image_id_map, base_dir)


def _blockquote_blocks_to_block(inner_blocks: list[dict]) -> dict:
    """blockquote の中身 (blocks) を callout / toggle に振り分ける.

    preprocess.py の ``>`` 簡易記法判定と同じ規則を、トークン (=リスト項目内などで
    インデントされ preprocess が拾えなかった blockquote) に対して適用する:
      - 先頭が見出し → toggle（見出しを summary に）
      - 先頭段落が絵文字始まり → callout（絵文字を icon に、残りを本文に）
      - それ以外 → toggle（空 summary）
    """
    if not inner_blocks:
        return {"type": "toggle", "toggle": {"rich_text": [], "children": []}}

    first = inner_blocks[0]
    ftype = first["type"]

    # 見出し始まり → toggle（見出しテキストを summary に）
    if ftype.startswith("heading_"):
        summary_rt = first[ftype].get("rich_text", [])
        children = inner_blocks[1:]
        toggle: dict[str, Any] = {"rich_text": summary_rt}
        if children:
            toggle["children"] = children
        return {"type": "toggle", "toggle": toggle}

    # 絵文字始まりの段落 → callout
    if ftype == "paragraph":
        rts = first["paragraph"].get("rich_text", [])
        first_text = (
            rts[0].get("text", {}).get("content", "")
            if rts and rts[0].get("type") == "text"
            else ""
        )
        emoji, rest = _extract_leading_emoji(first_text)
        if emoji:
            body_rts = list(rts)
            if rest:
                head = body_rts[0]
                body_rts[0] = {
                    **head,
                    "text": {**head["text"], "content": rest},
                }
            else:
                body_rts = body_rts[1:]
            payload: dict[str, Any] = {
                "rich_text": body_rts,
                "icon": {"type": "emoji", "emoji": emoji},
            }
            children = inner_blocks[1:]
            if children:
                payload["children"] = children
            return {"type": "callout", "callout": payload}

    # それ以外 → 空 summary の toggle
    return {"type": "toggle", "toggle": {"rich_text": [], "children": inner_blocks}}


def _convert_blockquote(
    tokens: list[Token],
    start_idx: int,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> tuple[dict, int]:
    """``blockquote_open`` から対応する ``blockquote_close`` までを callout/toggle に変換.

    通常 preprocess が ``>`` を先に展開するため、ここに来るのはリスト項目内などで
    インデントされ preprocess が拾えなかった blockquote。markdown-it が構造を正しく
    トークン化するので、中身を再帰変換して :func:`_blockquote_blocks_to_block` で振り分ける。
    """
    i = start_idx + 1
    depth = 1
    inner: list[Token] = []
    while i < len(tokens):
        t = tokens[i].type
        if t == "blockquote_open":
            depth += 1
            inner.append(tokens[i])
        elif t == "blockquote_close":
            depth -= 1
            if depth == 0:
                i += 1
                break
            inner.append(tokens[i])
        else:
            inner.append(tokens[i])
        i += 1
    inner_blocks = _tokens_to_blocks(inner, image_id_map, base_dir)
    return _blockquote_blocks_to_block(inner_blocks), i


def _consume_callout(
    tokens: list[Token],
    start_idx: int,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> tuple[list[dict] | None, int]:
    """``<callout emoji="...">...</callout>`` を Notion callout ブロックに変換する.

    preprocess が本文の空行を圧縮するため、通常は開始〜閉じが同一 html_block 内に
    収まる（パターン a）。手書き等で空行を含み別 html_block に分かれた場合は
    depth カウンタで対応付ける（パターン b）。

    本文の先頭が段落ならその rich_text を callout 本体に、残りを children にする。
    先頭が段落でなければ rich_text は空にして全ブロックを children にする。

    戻り値は ``(blocks | None, next_index)``。``blocks`` は通常 callout 1 件だが、
    markdown-it が ``</callout>`` の後ろに続く本文（テーブル・箇条書き等）を同じ
    html_block に巻き込んだ場合、その末尾本文を再 parse した兄弟ブロックを後続に含める
    （巻き込みによるデータ欠落を防ぐ）。
    """
    open_tk = tokens[start_idx]
    if open_tk.type != "html_block" or not _is_callout_open(open_tk.content):
        return None, start_idx

    emoji_match = _CALLOUT_EMOJI_PATTERN.search(open_tk.content)
    emoji = emoji_match.group("emoji") if emoji_match else "💡"

    # ----- パターン a: 同一 html_block 内で完結 -----
    inner_match = _CALLOUT_INNER_PATTERN.search(open_tk.content)
    if inner_match:
        inner_text = inner_match.group("inner").strip("\n")
        children: list[dict] = []
        if inner_text.strip():
            children = _parse_md_fragment(inner_text, image_id_map, base_dir)
        blocks = [_assemble_callout(emoji, children)]
        # </callout> 以降に巻き込まれた本文を救済して兄弟ブロックにする
        trailing = open_tk.content[inner_match.end():]
        if trailing.strip():
            blocks.extend(_parse_md_fragment(trailing, image_id_map, base_dir))
        return blocks, start_idx + 1

    # ----- パターン b: 別 html_block に分かれている -----
    inner_tokens: list[Token] = []
    i = start_idx + 1
    depth = 1
    while i < len(tokens):
        tk = tokens[i]
        if tk.type == "html_block":
            if _is_callout_open(tk.content):
                depth += 1
                inner_tokens.append(tk)
                i += 1
                continue
            if _CALLOUT_CLOSE_PATTERN.match(tk.content.strip()):
                depth -= 1
                if depth == 0:
                    i += 1
                    break
                inner_tokens.append(tk)
                i += 1
                continue
        inner_tokens.append(tk)
        i += 1
    else:
        logger.warning("<callout> の対応する </callout> が見つかりません")

    children = _tokens_to_blocks_with_codeblock_reparse(
        inner_tokens, image_id_map, base_dir
    )
    return [_assemble_callout(emoji, children)], i


def _assemble_callout(emoji: str, children: list[dict]) -> dict:
    """callout ブロックを組み立てる。先頭段落を本体 rich_text に昇格する."""
    rich_text: list[dict] = []
    if children and children[0].get("type") == "paragraph":
        rich_text = children[0]["paragraph"]["rich_text"]
        children = children[1:]
    payload: dict[str, Any] = {
        "rich_text": rich_text,
        "icon": {"type": "emoji", "emoji": emoji},
    }
    if children:
        payload["children"] = children
    return {"type": "callout", "callout": payload}


def _is_details_close(content: str) -> bool:
    return bool(_DETAILS_CLOSE_PATTERN.match(content.strip()))


def _extract_summary(content: str) -> str:
    """``<details>`` 開始 html_block の中から ``<summary>`` の中身を抽出.

    ``<summary>`` は通常、開始タグと同じ html_block 内に書かれる
    （commonmark Type 6 HTML block では空行までが 1 ブロック扱い）。
    """
    match = _SUMMARY_PATTERN.search(content)
    return match.group(1).strip() if match else ""


def _consume_details(
    tokens: list[Token],
    start_idx: int,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> tuple[list[dict] | None, int]:
    """``tokens[start_idx]`` が ``<details>`` 開始 html_block の場合、対応する
    ``</details>`` までを消費して toggle ブロックを返す.

    パターン:
      a) ``<details>`` 開始と ``</details>`` 閉じが **同一 html_block** 内に
         まとまっている（途中に空行が無いケース）。中間の md を抽出して再 parse する。
      b) 別の html_block に分かれている（途中に空行があるケース）。depth カウンタで
         対応付ける。

    戻り値: ``(blocks | None, next_index)``。``blocks`` は通常 toggle 1 件だが、
    ``</details>`` の後ろに続く本文を markdown-it が同じ html_block に巻き込んだ場合は、
    その末尾本文を再 parse した兄弟ブロックを後続に含める（データ欠落防止）。
    """
    open_tk = tokens[start_idx]
    if open_tk.type != "html_block" or not _is_details_open(open_tk.content):
        return None, start_idx

    content = open_tk.content
    label = _extract_summary(content)

    # ----- パターン a: 同一 html_block 内で完結 -----
    close_match = re.search(r"</details>", content, re.IGNORECASE)
    matched_close: int | None = None
    if close_match:
        # ネスト対応: 開始タグと閉じタグを order で並べ、balance==0 になる閉じタグまでを範囲とする
        opens = [m.start() for m in _DETAILS_OPEN_ANYWHERE.finditer(content)]
        closes = [
            m.start() for m in re.finditer(r"</details>", content, re.IGNORECASE)
        ]
        events = sorted(
            [(p, "open") for p in opens] + [(p, "close") for p in closes]
        )
        balance = 0
        for pos, kind in events:
            if kind == "open":
                balance += 1
            else:
                balance -= 1
                if balance == 0:
                    matched_close = pos
                    break
    if close_match and matched_close is not None:
        # 中身: <summary>...</summary> 直後 〜 対応する </details> 直前
        summary_match = _SUMMARY_PATTERN.search(content)
        if summary_match:
            inner_start = summary_match.end()
        else:
            open_match = _DETAILS_OPEN_PATTERN.match(content)
            inner_start = open_match.end() if open_match else 0
        inner_text = content[inner_start:matched_close].strip("\n")

        children: list[dict] = []
        if inner_text.strip():
            children = _parse_md_fragment(inner_text, image_id_map, base_dir)
        blocks: list[dict] = [{
            "type": "toggle",
            "toggle": {
                "rich_text": [_new_text(label)] if label else [],
                "children": children,
            },
        }]
        # </details> 以降に巻き込まれた本文を救済して兄弟ブロックにする
        trailing = content[matched_close + len("</details>"):]
        if trailing.strip():
            blocks.extend(_parse_md_fragment(trailing, image_id_map, base_dir))
        return blocks, start_idx + 1

    # ----- パターン b: 別 html_block に分かれている -----
    inner_tokens: list[Token] = []
    i = start_idx + 1
    depth = 1
    while i < len(tokens):
        tk = tokens[i]
        if tk.type == "html_block":
            if _is_details_open(tk.content):
                depth += 1
                inner_tokens.append(tk)
                i += 1
                continue
            if _is_details_close(tk.content):
                depth -= 1
                if depth == 0:
                    i += 1
                    break
                inner_tokens.append(tk)
                i += 1
                continue
        inner_tokens.append(tk)
        i += 1
    else:
        logger.warning("<details> の対応する </details> が見つかりません: %s", label)

    children = _tokens_to_blocks_with_codeblock_reparse(
        inner_tokens, image_id_map, base_dir
    )
    return [{
        "type": "toggle",
        "toggle": {
            "rich_text": [_new_text(label)] if label else [],
            "children": children,
        },
    }], i


def _tokens_to_blocks_with_codeblock_reparse(
    tokens: list[Token],
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> list[dict]:
    """inner_tokens 内の ``code_block`` (インデントによる) を dedent して再 parse する.

    `<details>` 内のテーブル行が list item などのインデントで code_block 扱いに
    なっているケースを救済する。再 parse 後のトークンは既存の ``_tokens_to_blocks``
    に流し込む。
    """
    expanded: list[Token] = []
    for tk in tokens:
        if tk.type == "code_block":
            dedented = _normalize_and_dedent(tk.content)
            if dedented.strip():
                sub_md = MarkdownIt("commonmark", {"html": True}).enable(
                    ["table", "strikethrough"]
                )
                expanded.extend(sub_md.parse(dedented))
            continue
        expanded.append(tk)
    return _tokens_to_blocks(expanded, image_id_map, base_dir)


# ---- &lt;columns&gt; / &lt;column&gt; レイアウト -----------------------------------------
#
# ``<columns>`` / ``<column>`` は commonmark の標準 HTML block タグに含まれないため、
# markdown-it-py は html_block として認識しない。そのため md 本文の **前処理** で
# 該当範囲を切り出し、内部を別途 `markdown_to_blocks` で再帰変換する。

_COLUMNS_BLOCK_PATTERN = re.compile(
    r"<columns\b[^>]*>(?P<inner>.*?)</columns>",
    re.IGNORECASE | re.DOTALL,
)
_COLUMN_BLOCK_PATTERN = re.compile(
    r"<column\b[^>]*>(?P<inner>.*?)</column>",
    re.IGNORECASE | re.DOTALL,
)


def _split_by_columns(body: str) -> list[tuple[str, str | list[str]]]:
    """md 本文を ``<columns>...</columns>`` 境界で分割する.

    戻り値: ``[("plain", md_text) | ("columns", [col1_text, col2_text, ...])]``

    column 内容は後続の再帰パースに渡す前に :func:`_normalize_and_dedent` で
    タブ正規化 + 共通インデント剥がしを行う。
    """
    parts: list[tuple[str, str | list[str]]] = []
    last = 0
    for m in _COLUMNS_BLOCK_PATTERN.finditer(body):
        start, end = m.span()
        if start > last:
            parts.append(("plain", body[last:start]))
        inner = m.group("inner")
        cols = [
            _normalize_and_dedent(cm.group("inner"))
            for cm in _COLUMN_BLOCK_PATTERN.finditer(inner)
        ]
        parts.append(("columns", cols))
        last = end
    if last < len(body):
        parts.append(("plain", body[last:]))
    return parts


def _normalize_and_dedent(text: str) -> str:
    """4 スペース混在のインデントをタブに正規化し、共通インデント分を剥がす.

    columns/column タグ内の md を再帰パースする前に適用する。
    """
    lines = text.splitlines()
    normalized: list[str] = []
    for line in lines:
        i, level = 0, 0
        while i < len(line):
            if line[i] == "\t":
                level += 1
                i += 1
            elif line[i : i + 4] == "    ":
                level += 1
                i += 4
            else:
                break
        normalized.append("\t" * level + line[i:])

    non_empty = [line for line in normalized if line.strip()]
    if not non_empty:
        return "\n".join(normalized)
    min_tabs = min(len(line) - len(line.lstrip("\t")) for line in non_empty)
    if min_tabs == 0:
        return "\n".join(normalized)

    result: list[str] = []
    for line in normalized:
        if line.strip() and len(line) - len(line.lstrip("\t")) >= min_tabs:
            result.append(line[min_tabs:])
        else:
            result.append(line)
    return "\n".join(result)


# ---- &lt;table&gt; HTML ブロック（安全網。作成時はパイプ表を使う）------------------
#
# テーブルの作成は **パイプ形式（``| col |``）が正**で、それは従来どおり別経路
# （table_open）で処理する。本関数はあくまで安全網: Notion の ``GET /pages/:id/markdown``
# （read コマンド）が表を ``<table header-row="true" ...><tr><td>...</td></tr></table>``
# という HTML で返すため、その書き戻しや、誰かが HTML テーブルを書いてしまった場合に
# 生タグが漏れないよう、HTML テーブルも Notion table ブロックへ変換する。
# ※ この HTML 記法はエージェントへの推奨記法としては案内しない（ドキュメント非掲載）。

_TABLE_OPEN_PATTERN = re.compile(r"^\s*<table\b", re.IGNORECASE)
_TABLE_FULL_RE = re.compile(
    r"<table\b(?P<attrs>[^>]*)>(?P<inner>.*?)</table>", re.IGNORECASE | re.DOTALL
)
_TABLE_TR_RE = re.compile(r"<tr\b[^>]*>(?P<row>.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TABLE_CELL_RE = re.compile(
    r"<(?P<tag>t[dh])\b[^>]*>(?P<cell>.*?)</(?P=tag)>", re.IGNORECASE | re.DOTALL
)
_HEADER_ROW_RE = re.compile(r'header-row\s*=\s*"(?P<v>[^"]*)"', re.IGNORECASE)
_HEADER_COL_RE = re.compile(r'header-column\s*=\s*"(?P<v>[^"]*)"', re.IGNORECASE)


def _is_html_table_open(content: str) -> bool:
    return bool(_TABLE_OPEN_PATTERN.match(content))


def _unescape_html(text: str) -> str:
    """セル内の最小限の HTML エンティティを復号する（``&amp;`` は最後に処理）."""
    return (
        text.replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
        .replace("&amp;", "&")
    )


def _cell_rich_text(
    text: str, image_id_map: dict[Path, str], base_dir: Path
) -> list[dict]:
    """テーブルセルの中身（インライン md）を rich_text に変換する."""
    text = _unescape_html(text).strip()
    if not text:
        return [_new_text("")]
    md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    rich_text: list[dict] = []
    for tok in md.parseInline(text):
        if tok.type == "inline":
            rendered, _ = _render_inline(tok, image_id_map, base_dir)
            rich_text.extend(rendered)
    return rich_text or [_new_text("")]


def _consume_html_table(
    tokens: list[Token],
    start_idx: int,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> tuple[dict | None, int]:
    """``<table>...</table>`` HTML ブロックを Notion table ブロックに変換する.

    Notion read 形式・1 行詰め・複数行いずれも、``<table>`` 開始から ``</table>`` までに
    空行が無ければ単一 html_block に収まる。空行で別ブロックに分かれた場合のみ後続を連結する。
    """
    open_tk = tokens[start_idx]
    if open_tk.type != "html_block" or not _is_html_table_open(open_tk.content):
        return None, start_idx

    content = open_tk.content
    next_i = start_idx + 1
    if "</table>" not in content.lower():
        parts = [content]
        while next_i < len(tokens):
            tk = tokens[next_i]
            parts.append(getattr(tk, "content", "") or "")
            next_i += 1
            if "</table>" in (getattr(tk, "content", "") or "").lower():
                break
        content = "\n".join(parts)

    full = _TABLE_FULL_RE.search(content)
    inner = full.group("inner") if full else content
    attrs = full.group("attrs") if full else ""

    def _attr_true(pat: re.Pattern) -> bool:
        m = pat.search(attrs)
        return bool(m and m.group("v").lower() in ("true", "1"))

    has_col_header = _attr_true(_HEADER_ROW_RE)
    has_row_header = _attr_true(_HEADER_COL_RE)

    rows: list[list[list[dict]]] = []
    max_cols = 0
    for tr_match in _TABLE_TR_RE.finditer(inner):
        cells = [
            _cell_rich_text(cm.group("cell"), image_id_map, base_dir)
            for cm in _TABLE_CELL_RE.finditer(tr_match.group("row"))
        ]
        if cells:
            rows.append(cells)
            max_cols = max(max_cols, len(cells))

    if max_cols == 0:
        logger.warning("<table> に行/セルが見つからない。空 paragraph で代替")
        return {"type": "paragraph", "paragraph": {"rich_text": [_new_text("")]}}, next_i

    for cells in rows:
        if len(cells) < max_cols:
            cells.extend([[_new_text("")]] * (max_cols - len(cells)))
        elif len(cells) > max_cols:
            del cells[max_cols:]

    table_rows = [
        {"type": "table_row", "table_row": {"cells": cells}} for cells in rows
    ]
    return (
        {
            "type": "table",
            "table": {
                "table_width": max_cols,
                "has_column_header": has_col_header,
                "has_row_header": has_row_header,
                "children": table_rows,
            },
        },
        next_i,
    )


# ---- list / table 変換 ------------------------------------------------------


def _convert_list(
    tokens: list[Token],
    start_idx: int,
    image_id_map: dict[Path, str],
    base_dir: Path,
    *,
    list_kind: str,
) -> tuple[list[dict], int]:
    """bullet_list_open / ordered_list_open から始まる範囲を変換."""
    items: list[dict] = []
    i = start_idx + 1
    depth = 1
    while i < len(tokens) and depth > 0:
        tk = tokens[i]
        if tk.type == "list_item_open":
            block, next_i = _convert_list_item(
                tokens, i, image_id_map, base_dir, list_kind
            )
            items.append(block)
            i = next_i
            continue
        if tk.type in ("bullet_list_close", "ordered_list_close"):
            depth -= 1
            i += 1
            continue
        if tk.type in ("bullet_list_open", "ordered_list_open"):
            depth += 1
            i += 1
            continue
        i += 1
    return items, i


def _convert_list_item(
    tokens: list[Token],
    start_idx: int,
    image_id_map: dict[Path, str],
    base_dir: Path,
    list_kind: str,
) -> tuple[dict, int]:
    """list_item_open から list_item_close までを 1 項目ブロックに変換."""
    rich_text: list[dict] = []
    children: list[dict] = []
    i = start_idx + 1
    while i < len(tokens):
        tk = tokens[i]
        if tk.type == "list_item_close":
            i += 1
            break
        if tk.type == "paragraph_open":
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                inline_tk = tokens[i + 1]
                paragraph_rt, extracted_imgs = _render_inline(
                    inline_tk, image_id_map, base_dir
                )
                if not rich_text:
                    rich_text = paragraph_rt
                else:
                    children.append(
                        {"type": "paragraph", "paragraph": {"rich_text": paragraph_rt}}
                    )
                children.extend(extracted_imgs)
            while i < len(tokens) and tokens[i].type != "paragraph_close":
                i += 1
            i += 1
            continue
        if tk.type in ("bullet_list_open", "ordered_list_open"):
            nested_kind = (
                _BULLET_LIST if tk.type == "bullet_list_open" else _NUMBERED_LIST
            )
            nested_items, next_i = _convert_list(
                tokens, i, image_id_map, base_dir, list_kind=nested_kind
            )
            children.extend(nested_items)
            i = next_i
            continue
        if tk.type == "fence":
            children.append(_code_block(tk))
            i += 1
            continue
        if tk.type == "heading_open":
            # リスト項目内にインデントされた見出し (toggle 注釈対応)
            level = int(tk.tag[1])
            inline_tk = tokens[i + 1]
            h_rich, h_extracted = _render_inline(inline_tk, image_id_map, base_dir)
            is_toggle, h_rich = _detect_heading_toggle(h_rich)
            if is_toggle:
                # 子: 見出し直後 〜 (同 level 以下の見出し | この list_item 終端)
                j = i + 3
                d = 0
                while j < len(tokens):
                    tt = tokens[j].type
                    if tt in ("bullet_list_open", "ordered_list_open", "list_item_open"):
                        d += 1
                    elif tt in ("bullet_list_close", "ordered_list_close", "list_item_close"):
                        if d == 0:
                            break
                        d -= 1
                    elif tt == "heading_open" and d == 0 and int(tokens[j].tag[1]) <= level:
                        break
                    j += 1
                child_blocks = _tokens_to_blocks(
                    tokens[i + 3 : j], image_id_map, base_dir
                )
                children.append(
                    _heading_block(level, h_rich, is_toggleable=True, children=child_blocks)
                )
                children.extend(h_extracted)
                i = j
                continue
            children.append(_heading_block(level, h_rich))
            children.extend(h_extracted)
            i += 3
            continue
        if tk.type == "blockquote_open":
            bq_block, next_i = _convert_blockquote(tokens, i, image_id_map, base_dir)
            children.append(bq_block)
            i = next_i
            continue
        if tk.type == "table_open":
            table_block, next_i = _convert_table(tokens, i, image_id_map, base_dir)
            children.append(table_block)
            i = next_i
            continue
        if tk.type == "html_block" and _is_html_table_open(tk.content):
            table_block, next_i = _consume_html_table(tokens, i, image_id_map, base_dir)
            if table_block is not None:
                children.append(table_block)
                i = next_i
                continue
        if tk.type == "html_block" and _is_callout_open(tk.content):
            callout_blocks, next_i = _consume_callout(tokens, i, image_id_map, base_dir)
            if callout_blocks is not None:
                children.extend(callout_blocks)
                i = next_i
                continue
        if tk.type == "html_block" and _is_details_open(tk.content):
            toggle_blocks, next_i = _consume_details(tokens, i, image_id_map, base_dir)
            if toggle_blocks is not None:
                children.extend(toggle_blocks)
                i = next_i
                continue
        logger.debug("list_item 内の未処理トークン: %s", tk.type)
        i += 1

    payload: dict[str, Any] = {"rich_text": rich_text}
    if children:
        payload["children"] = children
    return {"type": list_kind, list_kind: payload}, i


def _convert_table(
    tokens: list[Token],
    start_idx: int,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> tuple[dict, int]:
    """``table_open`` から ``table_close`` までを Notion table ブロックに変換.

    md パイプテーブルのトークン列:
        table_open, thead_open, tr_open, th_open, inline, th_close, ..., tr_close,
        thead_close, tbody_open, tr_open, td_open, inline, td_close, ..., tr_close,
        ..., tbody_close, table_close
    """
    rows: list[dict] = []
    max_cols = 0
    current_row: list[list[dict]] | None = None
    i = start_idx + 1
    while i < len(tokens):
        tk = tokens[i]
        if tk.type == "table_close":
            i += 1
            break
        if tk.type == "tr_open":
            current_row = []
            i += 1
            continue
        if tk.type == "tr_close":
            if current_row is not None:
                rows.append({"type": "table_row", "table_row": {"cells": current_row}})
                max_cols = max(max_cols, len(current_row))
                current_row = None
            i += 1
            continue
        if tk.type in ("th_open", "td_open"):
            # 次の inline トークンがセル内容
            if i + 1 < len(tokens) and tokens[i + 1].type == "inline":
                cell_rt, _ = _render_inline(tokens[i + 1], image_id_map, base_dir)
                if current_row is not None:
                    current_row.append(cell_rt if cell_rt else [_new_text("")])
            # *_close まで進める
            close_types = ("th_close", "td_close")
            while i < len(tokens) and tokens[i].type not in close_types:
                i += 1
            i += 1
            continue
        i += 1

    if max_cols == 0:
        logger.warning("table に行が 1 つも無い。空 paragraph で代替")
        return (
            {
                "type": "paragraph",
                "paragraph": {"rich_text": [_new_text("")]},
            },
            i,
        )

    # 行ごとに列数を揃える（短い行は空セルで埋め、長い行は truncate）
    for row in rows:
        cells = row["table_row"]["cells"]
        if len(cells) < max_cols:
            cells.extend([[_new_text("")]] * (max_cols - len(cells)))
        elif len(cells) > max_cols:
            del cells[max_cols:]

    return (
        {
            "type": "table",
            "table": {
                "table_width": max_cols,
                "has_column_header": True,
                "has_row_header": False,
                "children": rows,
            },
        },
        i,
    )


# ---- トークン → blocks -----------------------------------------------------


def _tokens_to_blocks(
    tokens: list[Token],
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> list[dict]:
    """トップレベルトークン配列を Notion blocks のリストに変換."""
    blocks: list[dict] = []
    i = 0
    while i < len(tokens):
        tk = tokens[i]
        if tk.type == "heading_open":
            level = int(tk.tag[1])
            inline_tk = tokens[i + 1]
            rich_text, extracted = _render_inline(inline_tk, image_id_map, base_dir)

            # heading text 末尾の `{toggle="true"}` 注釈を検出
            is_toggle, rich_text = _detect_heading_toggle(rich_text)

            if is_toggle:
                # 次の同 level 以下 heading 直前までの token を children として再帰処理
                end_idx = _find_next_sibling_heading_token(tokens, i + 3, level)
                child_tokens = tokens[i + 3 : end_idx]
                children = _tokens_to_blocks(child_tokens, image_id_map, base_dir)
                blocks.append(
                    _heading_block(
                        level, rich_text, is_toggleable=True, children=children
                    )
                )
                blocks.extend(extracted)
                i = end_idx
                continue

            blocks.append(_heading_block(level, rich_text))
            blocks.extend(extracted)
            i += 3
            continue
        if tk.type == "paragraph_open":
            inline_tk = tokens[i + 1]
            rich_text, extracted = _render_inline(inline_tk, image_id_map, base_dir)
            if rich_text:
                non_empty = [
                    rt
                    for rt in rich_text
                    if rt.get("type") != "text"
                    or rt.get("text", {}).get("content", "").strip()
                ]
                if non_empty:
                    blocks.append(
                        {"type": "paragraph", "paragraph": {"rich_text": rich_text}}
                    )
            blocks.extend(extracted)
            i += 3
            continue
        if tk.type in ("bullet_list_open", "ordered_list_open"):
            kind = _BULLET_LIST if tk.type == "bullet_list_open" else _NUMBERED_LIST
            items, next_i = _convert_list(
                tokens, i, image_id_map, base_dir, list_kind=kind
            )
            blocks.extend(items)
            i = next_i
            continue
        if tk.type == "fence":
            blocks.append(_code_block(tk))
            i += 1
            continue
        if tk.type == "blockquote_open":
            # 通常 preprocess が `>` を展開済みだが、インデント等で残った blockquote を救済
            bq_block, next_i = _convert_blockquote(tokens, i, image_id_map, base_dir)
            blocks.append(bq_block)
            i = next_i
            continue
        if tk.type == "hr":
            blocks.append({"type": "divider", "divider": {}})
            i += 1
            continue
        if tk.type == "table_open":
            table_block, next_i = _convert_table(tokens, i, image_id_map, base_dir)
            blocks.append(table_block)
            i = next_i
            continue
        if tk.type == "html_block":
            # <table>...</table>（Notion read 形式 / 手書き HTML）は table ブロックに変換
            if _is_html_table_open(tk.content):
                table_block, next_i = _consume_html_table(
                    tokens, i, image_id_map, base_dir
                )
                if table_block is not None:
                    blocks.append(table_block)
                    i = next_i
                    continue
            # <callout emoji="...">...</callout> は callout ブロックに変換
            if _is_callout_open(tk.content):
                callout_blocks, next_i = _consume_callout(
                    tokens, i, image_id_map, base_dir
                )
                if callout_blocks is not None:
                    blocks.extend(callout_blocks)
                    i = next_i
                    continue
            # <details>...</details> は toggle ブロックに変換
            if _is_details_open(tk.content):
                toggle_blocks, next_i = _consume_details(
                    tokens, i, image_id_map, base_dir
                )
                if toggle_blocks is not None:
                    blocks.extend(toggle_blocks)
                    i = next_i
                    continue
            # <columns>...</columns> は column_list に変換
            if tk.content.lstrip().lower().startswith("<columns"):
                parts = _split_by_columns(tk.content)
                for kind, content in parts:
                    if kind != "columns":
                        # <columns> の前後に巻き込まれた本文を兄弟ブロックとして救済
                        assert isinstance(content, str)
                        if content.strip():
                            blocks.extend(_parse_md_fragment(content, image_id_map, base_dir))
                        continue
                    assert isinstance(content, list)
                    cols: list[dict] = []
                    for col_text in content:
                        col_children = markdown_to_blocks(
                            col_text, image_id_map, base_dir
                        )
                        cols.append(
                            {"type": "column", "column": {"children": col_children}}
                        )
                    if len(cols) >= 2:
                        blocks.append(
                            {"type": "column_list", "column_list": {"children": cols}}
                        )
                    else:
                        _warn(f"column_list は最低 2 つの column が必要です ({len(cols)} 件) -- スキップしました")
                i += 1
                continue
            # それ以外の html_block は paragraph 化
            _warn(f"未対応の HTML ブロックを段落として書き込みました: {tk.content[:60]!r}")
            blocks.append(
                {
                    "type": "paragraph",
                    "paragraph": {"rich_text": [_new_text(tk.content)]},
                }
            )
            i += 1
            continue
        logger.warning("トップレベル未対応トークン: %s", tk.type)
        i += 1
    return blocks


# ---- 公開 API --------------------------------------------------------------


def markdown_to_blocks(
    body: str,
    image_id_map: dict[Path, str],
    base_dir: Path,
) -> list[dict]:
    """md 本文を Notion blocks 配列に変換する.

    - ``<columns><column>...</column>...</columns>`` を Notion ``column_list`` +
      ``column`` ブロックに変換（各 column 内は再帰的に ``markdown_to_blocks``）
    - それ以外は ``markdown-it-py`` で素直にパースして対応 blocks に変換する
    - ``## タイトル {toggle="true"}`` は heading toggle(``is_toggleable``)に変換し、
      次の同 level 以下 heading 直前までを children にする
    - 内容が欠ける可能性のある事象は :data:`WARNINGS` に積む(呼び出し元が
      :func:`reset_warnings` でリセットして読む)
    """
    md = MarkdownIt("commonmark", {"html": True}).enable(["table", "strikethrough"])
    tokens = md.parse(body)
    return _tokens_to_blocks(tokens, image_id_map, base_dir)
