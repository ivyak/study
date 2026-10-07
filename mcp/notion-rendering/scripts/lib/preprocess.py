"""ローカル md の簡易記法を Notion 拡張記法に展開する.

ユーザーが書きやすい簡易記法（``>`` toggle / callout、``{[...]、[...]、}`` columns）を、
``md_to_blocks`` が解釈する標準記法（``<details>`` / ``<callout>`` / ``<columns>``）に変換する。

- ``>``: blockquote を toggle または callout に変換。
  - 先頭が絵文字（例 ``> **💡 ...**`` / ``> 💡 ...``）→ ``<callout>``（絵文字をアイコン化）
  - 先頭が見出し（``> ## タイトル``）→ ``<details>`` toggle（見出しを summary に）
  - それ以外 → ``<details>`` toggle（空 summary）
- ``{[...]、[...]、}``: 単独行マーカーを ``<columns>`` / ``<column>`` に展開。

記法の一覧は SKILL.md / references/md-to-blocks-rules.md を参照。
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

# 行頭の `>` 連続をマッチ。`>` 直後の空白の有無を許容する。
_BQ_LINE_PATTERN = re.compile(r"^(?P<prefix>(?:>\s?)+)(?P<body>.*)$")
# 行頭からの heading 行（インデントなし）。簡易記法後の中身パース時に使用
_HEADING_PATTERN = re.compile(r"^(?P<marker>#{1,6})\s+(?P<title>.+?)\s*$")

# callout 判定用の絵文字検出（codepoint レンジで判定。ソースに生の絵文字を置かない）。
# callout アイコンに使われる主要レンジをカバーする。
_EMOJI_RANGES = (
    (0x1F300, 0x1FAFF),  # 記号・絵文字 / 補助記号 / 拡張A
    (0x2600, 0x27BF),    # その他記号 + Dingbats（⚠ ✅ ✨ 等）
    (0x2B00, 0x2BFF),    # その他記号・矢印
    (0x1F000, 0x1F2FF),  # 麻雀牌〜囲み英数補助
    (0x2300, 0x23FF),    # 技術記号（⌚ ⏰ 等）
    (0x2100, 0x214F),    # 文字様記号（ℹ ™ 等）
    (0x2190, 0x21FF),    # 矢印
)
# 異体字セレクタ(VS15/16) / keycap / 肌色修飾子。
_VARIATION_SELECTORS = (0xFE0E, 0xFE0F, 0x20E3)
_ZWJ = 0x200D


def _is_emoji_char(ch: str) -> bool:
    cp = ord(ch)
    return any(lo <= cp <= hi for lo, hi in _EMOJI_RANGES)


def _is_emoji_modifier(ch: str) -> bool:
    cp = ord(ch)
    return cp in _VARIATION_SELECTORS or 0x1F3FB <= cp <= 0x1F3FF


def _extract_leading_emoji(text: str) -> tuple[str | None, str]:
    """行頭の emphasis マーカー/空白を読み飛ばし、先頭の絵文字を 1 つ抽出する.

    ``> **💡 ...**`` のように絵文字が強調記号で囲まれていても検出する。
    戻り値は ``(emoji | None, 絵文字を取り除いた残りテキスト)``。
    絵文字が無ければ ``(None, 元テキスト)`` を返す。
    """
    i, n = 0, len(text)
    while i < n and (text[i].isspace() or text[i] in "*_~`"):
        i += 1
    if i >= n or not _is_emoji_char(text[i]):
        return None, text
    start = i
    i += 1
    while i < n and _is_emoji_modifier(text[i]):
        i += 1
    # ZWJ 連結シーケンス: (ZWJ + 絵文字 + 修飾子*) の繰り返し
    while i + 1 < n and ord(text[i]) == _ZWJ and _is_emoji_char(text[i + 1]):
        i += 2
        while i < n and _is_emoji_modifier(text[i]):
            i += 1
    emoji = text[start:i]
    rest = text[i:]
    if rest[:1] in (" ", "\t"):  # 絵文字直後の空白 1 つを詰める
        rest = rest[1:]
    return emoji, text[:start] + rest

# columns 簡易記法のマーカー（単独行）
_COLUMNS_OPEN_LINE = re.compile(r"^\s*\{\s*$")
_COLUMN_OPEN_LINE = re.compile(r"^\s*\[\s*$")
_COLUMN_CLOSE_LINE = re.compile(r"^\s*\]\s*$")
_COLUMNS_CLOSE_LINE = re.compile(r"^\s*\}\s*$")


def expand_toggle_blockquotes(text: str) -> str:
    """``>`` 始まりの blockquote ネストを ``<details>`` ブロックに展開する.

    変換規則:
    - 連続する ``>`` 行をひとまとまりの blockquote ブロックとして抽出
    - 各ブロック内で ``> >`` のネストを再帰的に処理（深い depth ほど内側 toggle）
    - ブロックの最初の ``> ## X`` を ``<summary>X</summary>`` として使う
    - heading が無い場合は空 summary（``<summary></summary>``）の toggle にする
    - 中身（heading 以外と、より深い blockquote）を ``<details>`` 内に展開

    blockquote 外の行はそのまま返す。
    """
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if not _BQ_LINE_PATTERN.match(line):
            out.append(line)
            i += 1
            continue

        # 連続する blockquote 行を集める（途中の空行は終端）
        block_start = i
        while i < len(lines) and _BQ_LINE_PATTERN.match(lines[i]):
            i += 1
        block_lines = lines[block_start:i]

        # 先頭が絵文字の単層 blockquote は callout に、それ以外は <details> toggle に変換
        expanded = _maybe_build_callout(block_lines)
        if expanded is None:
            expanded = _expand_blockquote_block(block_lines, depth=1)
        out.append(expanded)

    return "\n".join(out)


def _maybe_build_callout(block_lines: list[str]) -> str | None:
    """単層 blockquote の先頭が絵文字なら ``<callout>`` に展開する（でなければ None）.

    - ネスト blockquote(``> >``) を含む場合は toggle 構造とみなし callout 化しない
    - 最初の非空行が見出し(``> ## ...``)の場合は toggle（summary）扱いとし callout 化しない
    - 最初の非空行の先頭が絵文字なら callout 化する。さらに、**絵文字始まりの行が複数**
      ある場合は行ごとに別 callout に分割する（``> 💡 a`` / ``> ⚠️ b`` → callout 2 つ）。
      絵文字始まりでない後続行は直前 callout の本文に連結する。

    本文中の空行は ``<details>`` と同様に 1 改行へ圧縮し、各 callout を単一の HTML
    ブロックとして ``md_to_blocks`` 側で安定して解釈できるようにする。
    """
    inner = _strip_one_quote_level(block_lines)
    if any(_BQ_LINE_PATTERN.match(line) for line in inner):
        return None  # ネスト blockquote → toggle に委ねる

    first_idx = next((idx for idx, line in enumerate(inner) if line.strip()), None)
    if first_idx is None:
        return None
    if _HEADING_PATTERN.match(inner[first_idx]):
        return None  # 見出し先頭 → toggle（summary）

    emoji, _stripped = _extract_leading_emoji(inner[first_idx])
    if not emoji:
        return None

    # 絵文字始まりの行ごとに segment 分割（segment = (emoji, 本文行リスト)）
    segments: list[tuple[str, list[str]]] = []
    for line in inner[first_idx:]:
        line_emoji, rest = (
            _extract_leading_emoji(line) if line.strip() else (None, line)
        )
        if line_emoji:
            segments.append((line_emoji, [rest]))
        elif segments:
            segments[-1][1].append(line)

    parts: list[str] = []
    for seg_emoji, body_lines in segments:
        body_clean = "\n".join(body_lines).strip("\n")
        body_clean = re.sub(r"\n\s*\n+", "\n", body_clean)
        if body_clean:
            parts.append(f'<callout emoji="{seg_emoji}">\n{body_clean}\n</callout>')
        else:
            parts.append(f'<callout emoji="{seg_emoji}"></callout>')
    # callout 同士は空行で区切り、別 HTML ブロックとして解釈させる
    return "\n\n".join(parts)


def _strip_one_quote_level(block: list[str]) -> list[str]:
    """各行の先頭から `>` を 1 段剥がす（blockquote ネスト 1 段下がる）."""
    stripped: list[str] = []
    for line in block:
        m = _BQ_LINE_PATTERN.match(line)
        if not m:
            stripped.append(line)
            continue
        prefix = m.group("prefix")
        body = m.group("body")
        # `> ` 1 個を削除（残りはそのまま）。`>` のみ・空白なしも対応
        # 先頭の `>` と後続の最大 1 個の空白を削除
        new_prefix = re.sub(r"^>\s?", "", prefix, count=1)
        stripped.append(new_prefix + body)
    return stripped


def _split_inner_groups(inner: list[str]) -> list[tuple[str, list[str]]]:
    """``inner`` (1 段剥がし済み) を「通常パート」と「ネスト blockquote パート」に分割する.

    戻り値は ``[(kind, lines)]`` の連続。``kind`` は ``"plain"`` か ``"bq"``。
    """
    groups: list[tuple[str, list[str]]] = []
    cur_kind: str | None = None
    cur_lines: list[str] = []
    for line in inner:
        is_bq = bool(_BQ_LINE_PATTERN.match(line))
        kind = "bq" if is_bq else "plain"
        if cur_kind is None:
            cur_kind = kind
            cur_lines = [line]
        elif kind == cur_kind:
            cur_lines.append(line)
        else:
            groups.append((cur_kind, cur_lines))
            cur_kind = kind
            cur_lines = [line]
    if cur_kind is not None:
        groups.append((cur_kind, cur_lines))
    return groups


def _expand_blockquote_block(block_lines: list[str], *, depth: int) -> str:
    """1 つの連続 blockquote ブロックを ``<details>`` に変換する.

    展開ルール:
    - blockquote 1 段を剥がして中身を取り出す
    - 中身のネスト blockquote 部分は再帰展開（さらに ``<details>`` でラップ）
    - 中身の最初の heading を ``<summary>`` に、残りを本文として ``<details>`` 内に展開
    - heading が無ければ空 ``<summary>``

    出力は CommonMark の HTML block type 7 規則（空行で終端）に対応するため、
    `<details>` ブロック内の段落区切り空行を改行 1 つに圧縮する。
    （Notion 上のトグル内段落区切りは消えるが、本文の論理構造は heading・list・
    code 等で表現されるためほとんどの用途で支障なし）
    """
    inner_lines = _strip_one_quote_level(block_lines)

    # ネスト blockquote を先に再帰展開
    groups = _split_inner_groups(inner_lines)
    rendered_body: list[str] = []
    for kind, group in groups:
        if kind == "plain":
            rendered_body.extend(group)
        else:
            rendered_body.append(_expand_blockquote_block(group, depth=depth + 1))

    body_text = "\n".join(rendered_body)
    body_lines = body_text.split("\n")

    # 中身の最初の heading を summary として抽出
    heading_idx = _find_first_heading_index(body_lines)
    if heading_idx is not None:
        m = _HEADING_PATTERN.match(body_lines[heading_idx])
        title = m.group("title").strip()
        body_remainder = body_lines[:heading_idx] + body_lines[heading_idx + 1 :]
    else:
        title = ""
        body_remainder = body_lines

    # 前後の空行を削除し、内部の連続空行を 1 つの改行に圧縮
    body_clean = "\n".join(body_remainder).strip("\n")
    body_clean = re.sub(r"\n\s*\n+", "\n", body_clean)
    summary_html = f"<summary>{title}</summary>"
    if body_clean:
        return f"<details>\n{summary_html}\n{body_clean}\n</details>"
    return f"<details>\n{summary_html}\n</details>"


def _find_first_heading_index(lines: list[str]) -> int | None:
    """``lines`` のうち、行頭から始まる heading の最初の行 index を返す."""
    for idx, line in enumerate(lines):
        if _HEADING_PATTERN.match(line):
            return idx
    return None


def expand_columns_shortcut(text: str) -> str:
    """``{[...]、[...]、}`` 簡易記法を ``<columns>``/``<column>`` に展開する.

    マーカー行は単独行（前後空白のみ）に限定。行中の ``[xxx]`` などは無視する。

    例::

        {
        [
        # カラム 1
        ]
        [
        # カラム 2
        ]
        }

    → ::

        <columns>
        <column>
        # カラム 1
        </column>
        <column>
        # カラム 2
        </column>
        </columns>
    """
    lines = text.split("\n")
    out: list[str] = []
    in_columns = False
    in_column = False
    for line in lines:
        if not in_columns and _COLUMNS_OPEN_LINE.match(line):
            out.append("<columns>")
            in_columns = True
            continue
        if in_columns and _COLUMN_OPEN_LINE.match(line) and not in_column:
            out.append("<column>")
            in_column = True
            continue
        if in_column and _COLUMN_CLOSE_LINE.match(line):
            out.append("</column>")
            in_column = False
            continue
        if in_columns and _COLUMNS_CLOSE_LINE.match(line) and not in_column:
            out.append("</columns>")
            in_columns = False
            continue
        out.append(line)
    if in_column:
        logger.warning("`{[ ]}` 記法: column が閉じられていません。`]` を追加して閉じます")
        out.append("</column>")
    if in_columns:
        logger.warning("`{[ ]}` 記法: columns が閉じられていません。`}` を追加して閉じます")
        out.append("</columns>")
    return "\n".join(out)


def preprocess(text: str) -> str:
    """簡易記法(``>`` toggle、``{[]}`` columns)を標準記法に展開する.

    順序:
    1. ``{[]}`` 簡易記法 → ``<columns>``/``<column>`` 展開
    2. ``>`` 簡易記法 → ``<details>`` 展開
       (columns 内に toggle が入る場合に対応するため columns を先に解決)
    """
    text = expand_columns_shortcut(text)
    text = expand_toggle_blockquotes(text)
    return text
