#!/usr/bin/env python3
"""git_study の md を、図・表・色つきの HTML に変換し、ポータル index.html も作る。

使い方: python3 build_html.py
対象は PAGES に書いたものだけ（増やすときは PAGES と ALL を編集する）。
"""
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent

# (md の stem, 短い題, 目安分)
ALL = [
    ('01_0_Git_全体像と読む順番', '全体像と読む順番', 5),
    ('01_1_Gitの世界観_4種類のオブジェクト', '4種類のオブジェクト', 11),
    ('01_2_git-init_空のgitを1行ずつ', 'git init 前編', 11),
    ('01_3_git-init_hooksとbareと例外', 'git init 後編', 8),
    ('01_4_add-commit_indexとオブジェクトの増え方', 'git add / commit', 12),
    ('01_5_git-branch_refsはただのテキスト', 'git branch', 12),
    ('01_6_git-remote-add_originという別名', 'git remote add', 12),
    ('01_7_git-fetch_取ってくるだけ', 'git fetch', 11),
    ('01_8_git-pull_fetchとmergeの合わせ技', 'git pull', 15),
    ('01_9_困ったときの早見表', '困ったときの早見表', 10),
]
PAGES = [a[0] for a in ALL[:3]]  # 変換済みのページ
INTRO = '00_はじめに-読む順番'


def esc(s):
    return html.escape(s, quote=False)


# ---------------------------------------------------------------- 図（手書き HTML）
D_FOUR = '''<div class="four">
<div class="card c-obj"><small>① 中身</small><b>objects/</b><em>不変・追記のみ</em><code>ce/013625…</code><p>ファイル名＝中身の SHA-1。blob / tree / commit / tag が入る</p></div>
<div class="card c-ref"><small>② 名札</small><b>refs/</b><em>可変・41 バイト</em><code>refs/heads/main</code><p>40 桁のハッシュ + 改行。ブランチを切る＝このファイルを 1 個作る</p></div>
<div class="card c-head"><small>③ 今どこ</small><b>HEAD</b><em>21 バイト・1 行</em><code>ref: refs/heads/main</code><p>② のどれを指すかを書いた転送指示</p></div>
<div class="card c-idx"><small>④ 下書き</small><b>index</b><em>バイナリ・1 個だけ</em><code>(binary)</code><p>作業ツリーと objects の間に挟まる中間状態</p></div>
</div>'''

D_FMT = '''<figure class="fmt"><div class="seg">
<div class="b k">blob<i>種類</i></div><div class="b s">␣<i>空白</i></div><div class="b n">6<i>バイト数</i></div><div class="b z">NUL<i>\\0</i></div><div class="b d">hello⏎<i>中身</i></div></div>
<figcaption>この全体を <b>zlib 圧縮</b>して保存。<b>ファイル名 ＝ この全体の SHA-1</b>。先頭の種類名だけが blob / tree / commit / tag に変わる。</figcaption></figure>'''

D_CHANGE = '''<div class="change">
<div class="card c-old"><small>元のまま残る</small><b>ce013625…</b><code>"hello\\n"</code></div>
<div class="arrow">hello → bye に直すと<br>▶</div>
<div class="card c-new"><small>新しく増える</small><b>b023018…</b><code>"bye\\n"</code></div>
</div>'''

D_LAYERS = '''<div class="layers">
<div class="layer l-logic"><b>論理モデル</b><span>スナップショットの連なり（<u>不変・単純</u>）</span><p>履歴の正しさ・マージ・ハッシュ検証はここで完結</p></div>
<div class="layer l-phys"><b>物理モデル</b><span>zlib 圧縮 + delta 圧縮 + パック（<u>可変・最適化</u>）</span><p>容量と速度の都合。論理モデルには一切影響しない</p></div>
</div>'''

D_TREEUPD = '''<figure class="treeupd"><div class="cap">src/api/main.py を 1 文字直したとき</div>
<ul class="tr"><li><span class="nd c-commit new">commit<em>新</em></span> → <span class="nd c-tree new">tree 根<em>新</em></span>
<ul><li><span class="nd c-blob old">blob bobfile.txt<em>そのまま</em></span></li>
<li><span class="nd c-tree new">tree src<em>新</em></span>
<ul><li><span class="nd c-tree new">tree api<em>新</em></span>
<ul><li><span class="nd c-blob new">blob main.py<em>新</em></span></li></ul></li></ul></li></ul></li></ul>
<figcaption>新しくできるのは <b>blob 1 + tree 3（api・src・根）+ commit 1 ＝ 5 個</b>。</figcaption></figure>'''

D_FILES = '''<div class="four files">
<div class="card c-core"><small>本体（Git の全部）</small><b>HEAD</b><b>objects/</b><b>refs/heads・refs/tags</b><p>今どこにいるか／データ本体／名札置き場。最初は objects と refs が空</p></div>
<div class="card c-conf"><small>設定</small><b>config</b><b>info/exclude</b><p>このリポジトリ限定の設定と、共有しない .gitignore</p></div>
<div class="card c-hook"><small>拡張ポイント</small><b>hooks/*.sample</b><p>全部サンプル。.sample を外さない限り動かない</p></div>
<div class="card c-misc"><small>ほぼ使わない</small><b>description</b><p>GitWeb 用の 1 行説明</p></div>
</div>'''

D_CFG = '''<div class="cfg">
<div class="lv lv1"><b>system</b><span>Git が入っている場所。全ユーザー共通</span></div>
<div class="lv lv2"><b>global</b><span>~/.gitconfig。あなた個人</span></div>
<div class="lv lv3 here"><b>local</b><span>.git/config。このリポジトリだけ</span><em>← git init が作るのはここ</em></div>
<div class="lv lv4"><b>worktree</b><span>.git/config.worktree。使うことは稀</span></div>
<div class="win">下の段ほど強い（上書きする）</div>
</div>'''

D_UNBORN = '''<figure class="unborn">
<div class="row"><div class="card c-head"><small>.git/HEAD</small><code>ref: refs/heads/main</code></div>
<div class="arrow">▶ 指す</div>
<div class="card c-ghost"><small>.git/refs/heads/main</small><code>まだ存在しない</code></div></div>
<div class="row two">
<div class="reader ok"><b>git status</b>は HEAD の<u>テキスト</u>を読む<br>→ <code>On branch main</code></div>
<div class="reader ng"><b>git branch</b>は refs/heads/ の<u>ファイル</u>を列挙<br>→ 何も出ない</div></div>
<figcaption>どちらも正しい。見ている場所が違うだけ。最初の <code>git commit</code> で refs/heads/main ができる。</figcaption></figure>'''

# 変換前の fence 内に含まれる文字列 → 置き換える図
FENCE_DIAGRAMS = [
    ('① 中身（不変・追記のみ）', D_FOUR),
    ('種類 + 空白 + バイト数 + NUL + 中身', D_FMT),
    ('hello → bye に直すと', D_CHANGE),
    ('論理モデル：', D_LAYERS),
    ('本体（この3つが Git の全部）', D_FILES),
    ('system   （git が入っている場所', D_CFG),
]
# 段落・見出しの原文にこの文字列が含まれていたら、その直後に図を足す
AFTER_DIAGRAMS = [
    ('**`"blob" + 空白 + バイト数 + NUL + 中身`**', D_FMT),
    ('1 ファイル直しただけでも', D_TREEUPD),
    ('壊れたリンク', D_UNBORN),
]

OBJ_COLORS = {
    'commit': ('#22586B', '#E3EEF2'), 'blob': ('#2F7D55', '#E4F2EA'),
    'tree': ('#A86A12', '#FAF0DC'), 'tag': ('#7A4B94', '#F0E8F5'),
    'work': ('#5B6770', '#EEF0F2'), 'idx': ('#B24A5E', '#F8E6EA'),
    'obj': ('#22586B', '#E3EEF2'), 'ref': ('#3B6FB0', '#E6EEF8'),
    'remote': ('#4A5568', '#E9ECF0'),
}


def classify(label):
    t = re.sub(r'<br/?>', ' ', label).strip()
    for k in ('commit', 'blob', 'tree', 'tag'):
        if t.startswith(k):
            return k
    if '作業ツリー' in t:
        return 'work'
    if 'index' in t:
        return 'idx'
    if 'objects' in t:
        return 'obj'
    if 'refs' in t or 'HEAD' in t:
        return 'ref'
    if 'リモート' in t or 'server' in t:
        return 'remote'
    return None


def mermaid_src(code):
    found = {}
    for m in re.finditer(r'\b(\w+)\["([^"]*)"\]', code):
        c = classify(m.group(2))
        if c:
            found.setdefault(c, []).append(m.group(1))
    extra = []
    for c, ids in found.items():
        stroke, fill = OBJ_COLORS[c]
        extra.append(f'classDef k_{c} fill:{fill},stroke:{stroke},stroke-width:2px,color:#111')
        extra.append(f'class {",".join(dict.fromkeys(ids))} k_{c}')
    return code + '\n' + '\n'.join(extra)


# ---------------------------------------------------------------- インライン
def link(text, href):
    if href.startswith('#'):
        return f'<a href="#s0.2">{text}</a>' if href.startswith('#02-') else f'<a href="{href}">{text}</a>'
    stem = Path(href.split('#')[0]).name
    stem = stem[:-3] if stem.endswith('.md') else stem
    if stem == INTRO:
        return f'<a href="index.html">{text}</a>'
    if stem in PAGES:
        return f'<a href="{stem}.html">{text}</a>'
    return f'<span class="soon" title="準備中">{text}</span>'


def inline(s):
    codes = []

    def keep(m):
        codes.append(m.group(1))
        return f'\x00{len(codes) - 1}\x00'

    s = re.sub(r'`([^`]+)`', keep, s)
    s = esc(s)
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', lambda m: link(m.group(1), m.group(2)), s)
    s = re.sub(r'\x00(\d+)\x00', lambda m: '<code>' + esc(codes[int(m.group(1))]) + '</code>', s)
    s = re.sub(r'<strong>(blob|tree|commit|tag)</strong>', r'<span class="obj \1">\1</span>', s)
    return s


# ---------------------------------------------------------------- コードブロック
HASH = re.compile(r'\b([0-9a-f]{40})\b')


def note(line):
    left, sep, right = line.partition('←')
    out = esc(left)
    if sep:
        out += '<span class="note">←' + esc(right) + '</span>'
    return HASH.sub(r'<span class="hash">\1</span>', out)


def hl_console(code):
    out, inq = [], False
    for line in code.split('\n'):
        if line.startswith('$ ') or inq:
            pre = ''
            body = line
            if line.startswith('$ '):
                pre, body = '<span class="ps">$</span> ', line[2:]
            if body.count('"') % 2:
                inq = not inq
            out.append(pre + '<span class="cmd">' + note(body) + '</span>')
        else:
            out.append(note(line))
    return '\n'.join(out)


def fence(lang, code):
    for key, d in FENCE_DIAGRAMS:
        if key in code:
            return d
    if lang == 'mermaid':
        return f'<figure class="mm"><pre class="mermaid">{esc(mermaid_src(code))}</pre></figure>'
    cap = ''
    lines = code.split('\n')
    if lang != 'console' and lines[0].startswith('# '):
        cap = f'<div class="cap">{esc(lines[0][2:])}</div>'
        code = '\n'.join(lines[1:])
    if lang == 'console':
        body = hl_console(code)
        return f'<div class="code term">{cap}<pre><code>{body}</code></pre></div>'
    body = '\n'.join(note(l) for l in code.split('\n'))
    return f'<div class="code plain">{cap}<pre><code>{body}</code></pre></div>'


# ---------------------------------------------------------------- ブロック
class Ctx:
    def __init__(self):
        self.title = ''
        self.toc = []
        self.warn = False
        self.n = 0


def table(rows):
    cells = [[c.strip() for c in re.split(r'(?<!\\)\|', r.strip().strip('|'))] for r in rows]
    head, body = cells[0], cells[2:]
    matrix = head[0] == 'コマンド' and any('objects' in h for h in head)
    neg = [i for i, h in enumerate(head) if '持っていない' in h]
    for r in cells:
        if len(r) != len(head):
            print('  警告: 列数が合わない行', r[:2])
    t = '<div class="tw"><table' + (' class="matrix"' if matrix else '') + '><thead><tr>'
    t += ''.join(f'<th>{inline(h)}</th>' for h in head) + '</tr></thead><tbody>'
    for r in body:
        t += '<tr>'
        for i, c in enumerate(r):
            cls = ''
            if matrix and i > 0:
                if '書き足す' in c:
                    cls = 'add'
                elif '書き換える' in c or '進める' in c or '増やす' in c:
                    cls = 'mod'
                elif '合わせる' in c or '以下だけ' in c:
                    cls = 'sync'
                elif c in ('—', '-'):
                    cls = 'none'
            if i in neg:
                cls = 'neg'
            t += f'<td class="{cls}">{inline(c)}</td>' if cls else f'<td>{inline(c)}</td>'
        t += '</tr>'
    return t + '</tbody></table></div>'


LIST = re.compile(r'^(\s*)([-*]|\d+\.) +(.*)')
STOP = re.compile(r'^(#{1,4} |```|>|\||<details|---)')


def join_text(parts):
    out = parts[0]
    for p in parts[1:]:
        if out and p and (ord(out[-1]) > 127 or ord(p[0]) > 127):
            out += p
        else:
            out += ' ' + p
    return out


def extras(src):
    return ''.join(d for key, d in AFTER_DIAGRAMS if key in src)


def blocks(lines, ctx):
    out, i, n = [], 0, len(lines)

    def close():
        if ctx.warn:
            out.append('</section>')
            ctx.warn = False

    while i < n:
        l = lines[i]
        s = l.strip()
        if not s:
            i += 1
            continue
        if s == '---':
            close()
            i += 1
            continue
        if l.startswith(('←', '次 →')):
            i += 1
            continue
        m = re.match(r'^```(\w*)', l)
        if m:
            j = i + 1
            while not lines[j].startswith('```'):
                j += 1
            out.append(fence(m.group(1), '\n'.join(lines[i + 1:j])))
            i = j + 1
            continue
        m = re.match(r'^(#{1,4}) (.*)', l)
        if m:
            lv, text = len(m.group(1)), m.group(2)
            close()
            if lv == 1:
                ctx.title = text
                i += 1
                continue
            ctx.n += 1
            nm = re.match(r'^(\d+(?:\.\d+)*)\.?\s+(.*)', text)
            hid = f's{nm.group(1)}' if nm else f'h{ctx.n}'
            num = f'<span class="num">{nm.group(1)}</span>' if nm else ''
            body = inline(nm.group(2) if nm else text)
            if lv == 3 and ('落とし穴' in text or '引っかかりどころ' in text):
                out.append('<section class="callout warn">')
                ctx.warn = True
            out.append(f'<h{lv} id="{hid}">{num}{body}</h{lv}>')
            if lv == 2:
                ctx.toc.append((hid, re.sub(r'`', '', text)))
            out.append(extras(text))
            i += 1
            continue
        if l.startswith('|') and i + 1 < n and re.match(r'^\|[\s:|-]+\|\s*$', lines[i + 1]):
            j = i
            while j < n and lines[j].startswith('|'):
                j += 1
            out.append(table(lines[i:j]))
            i = j
            continue
        if l.startswith('>'):
            j = i
            while j < n and lines[j].startswith('>'):
                j += 1
            inner = [re.sub(r'^> ?', '', x) for x in lines[i:j]]
            out.append('<aside class="callout info">' + blocks(inner, Ctx()) + '</aside>')
            i = j
            continue
        if s.startswith('<details'):
            j = i
            while not lines[j].strip().startswith('</details>'):
                j += 1
            summ = lines[i + 1].strip()
            body = blocks(lines[i + 2:j], Ctx())
            summ = re.sub(r'^<summary>(.*)</summary>$', r'\1', summ)
            out.append(f'<details class="quiz"><summary>{summ}</summary><div class="answer">{body}</div></details>')
            i = j + 1
            continue
        mm = LIST.match(l)
        if mm:
            ordered = mm.group(2)[0].isdigit()
            items = []
            j = i
            while j < n:
                lm = LIST.match(lines[j])
                if lm:
                    items.append([lm.group(3)])
                elif lines[j].strip() and lines[j][0] in ' \t' and items:
                    items[-1].append(lines[j].strip())
                else:
                    break
                j += 1
            tag = 'ol' if ordered else 'ul'
            out.append(f'<{tag}>' + ''.join(f'<li>{inline(join_text(it))}</li>' for it in items) + f'</{tag}>')
            i = j
            continue
        j = i
        parts = []
        while j < n and lines[j].strip() and not (j > i and (STOP.match(lines[j]) or LIST.match(lines[j]))):
            parts.append(lines[j].strip())
            j += 1
        text = join_text(parts)
        out.append(f'<p>{inline(text)}</p>')
        out.append(extras(text))
        i = j
    close()
    return '\n'.join(out)


# ---------------------------------------------------------------- ページ
CSS = '''
:root { --accent:#22586B; --muted:#65747A; --pale:#EFF5F6; --line:#dee7e9;
  --commit:#22586B; --commit-bg:#E3EEF2; --blob:#2F7D55; --blob-bg:#E4F2EA; --tree:#A86A12; --tree-bg:#FAF0DC;
  --tag:#7A4B94; --tag-bg:#F0E8F5; --ref:#3B6FB0; --ref-bg:#E6EEF8; --head:#C0561F; --head-bg:#FBE9DE;
  --idx:#B24A5E; --idx-bg:#F8E6EA; --warn:#B7791F; --warn-bg:#FFF7E3; --bad:#B3352B; --bad-bg:#FBEAE8; --ok:#2F7D55; }
* { box-sizing:border-box; }
html { background:#fff; color:#111; color-scheme:light; }
body { margin:0; font-family:"Yu Mincho","Hiragino Mincho ProN","Noto Serif CJK JP",serif; line-height:1.9; }
h1,h2,h3,h4,nav,.eyebrow,.chips,.cap,figcaption,summary,th,.soon,footer,.legend { font-family:"Yu Gothic","Hiragino Kaku Gothic ProN",sans-serif; }
code,pre { font-family:ui-monospace,"SF Mono",Menlo,monospace; }
a { color:var(--accent); text-underline-offset:.2em; }
a:hover { background:var(--pale); }
a:focus-visible,summary:focus-visible { outline:2px solid var(--accent); outline-offset:3px; }
.soon { color:var(--muted); border-bottom:1px dotted var(--muted); cursor:default; }
.wrap { max-width:1180px; margin:0 auto; padding:40px 28px 64px; }
.back { font-family:sans-serif; font-size:.83rem; margin:0 0 20px; }
.back a { text-decoration:none; }
header.doc { border-bottom:2px solid var(--accent); padding-bottom:22px; margin-bottom:8px; }
.eyebrow { margin:0 0 6px; color:var(--accent); font-size:.85rem; letter-spacing:.04em; }
h1 { font-size:1.8rem; line-height:1.5; margin:0 0 12px; }
.chips { display:flex; flex-wrap:wrap; gap:8px; font-size:.75rem; }
.chips span { background:var(--pale); color:var(--accent); padding:2px 10px; border-radius:999px; }
.layout { display:grid; grid-template-columns:230px minmax(0,1fr); gap:44px; align-items:start; }
nav.toc { position:sticky; top:20px; font-size:.8rem; line-height:1.55; padding-top:22px; max-height:calc(100vh - 40px); overflow:auto; }
nav.toc p { margin:0 0 6px; color:var(--muted); font-weight:700; font-size:.75rem; }
nav.toc ul { list-style:none; margin:0 0 20px; padding:0; border-left:2px solid var(--line); }
nav.toc li a { display:block; padding:3px 10px; margin-left:-2px; border-left:2px solid transparent; color:var(--muted); text-decoration:none; }
nav.toc li a:hover { color:var(--accent); border-left-color:var(--accent); background:none; }
.legend { font-size:.75rem; display:grid; gap:5px; }
.legend span { display:flex; align-items:center; gap:8px; color:var(--muted); }
.legend i { width:14px; height:14px; border-radius:3px; display:inline-block; }
article { min-width:0; max-width:860px; }
h2 { font-size:1.45rem; line-height:1.5; margin:52px 0 16px; padding-bottom:8px; border-bottom:1px solid var(--line); scroll-margin-top:20px; }
h3 { font-size:1.12rem; color:var(--accent); margin:32px 0 10px; line-height:1.6; scroll-margin-top:20px; }
h4 { font-size:1rem; margin:22px 0 6px; }
.num { display:inline-block; font-size:.78em; background:var(--accent); color:#fff; border-radius:4px; padding:0 8px; margin-right:10px; line-height:1.6; vertical-align:2px; font-weight:600; }
h3 .num { background:var(--pale); color:var(--accent); }
p { margin:12px 0; overflow-wrap:anywhere; }
ul,ol { padding-left:1.7em; margin:14px 0; } li { margin:6px 0; }
code { font-size:.88em; background:#F1F4F5; padding:1px 5px; border-radius:3px; color:#1d3b46; }
.obj { font-family:ui-monospace,monospace; font-size:.86em; font-weight:700; padding:1px 8px; border-radius:4px; }
.obj.blob { background:var(--blob-bg); color:var(--blob); } .obj.tree { background:var(--tree-bg); color:var(--tree); }
.obj.commit { background:var(--commit-bg); color:var(--commit); } .obj.tag { background:var(--tag-bg); color:var(--tag); }
.callout { margin:20px 0; padding:4px 20px; border-radius:4px; border-left:5px solid; font-size:.95rem; }
.callout.info { background:var(--pale); border-color:var(--accent); }
.callout.warn { background:var(--warn-bg); border-color:var(--warn); }
.callout.warn h3 { color:#8a5a0e; margin-top:14px; }
.callout.warn h3::before { content:"⚠ "; }
.callout p,.callout ul { margin:8px 0; }
.tw { overflow-x:auto; margin:18px 0; }
table { border-collapse:collapse; width:100%; font-size:.9rem; line-height:1.65; }
th { background:var(--accent); color:#fff; text-align:left; padding:8px 12px; font-size:.82rem; white-space:nowrap; }
td { padding:8px 12px; border-bottom:1px solid var(--line); vertical-align:top; }
tbody tr:nth-child(even) td { background:#F8FBFB; }
td.neg { background:var(--bad-bg) !important; } td.neg strong { color:var(--bad); }
table.matrix td { text-align:center; } table.matrix td:first-child { text-align:left; }
table.matrix td.add { background:var(--blob-bg) !important; color:var(--blob); font-weight:700; }
table.matrix td.mod { background:var(--head-bg) !important; color:var(--head); font-weight:700; }
table.matrix td.sync { background:var(--ref-bg) !important; color:var(--ref); font-weight:700; }
table.matrix td.none { color:#b5bfc3; }
.code { margin:18px 0; border-radius:6px; overflow:hidden; border:1px solid var(--line); }
.code .cap { font-size:.75rem; padding:5px 14px; background:#E4ECEE; color:var(--muted); }
.code pre { margin:0; padding:14px 16px; overflow-x:auto; font-size:.82rem; line-height:1.65; }
.code code { background:none; padding:0; font-size:inherit; color:inherit; }
.code.term { background:#14232A; border-color:#14232A; } .code.term pre { color:#D6E2E6; }
.code.term .cap { background:#1F343D; color:#9db3ba; }
.term .ps { color:#7BD3A0; font-weight:700; } .term .cmd { color:#fff; }
.term .note,.plain .note { color:#F0B35C; } .plain .note { color:#B7791F; }
.term .hash { color:#8EC5DA; } .plain .hash { color:var(--accent); }
.code.plain { background:#F8FBFB; }
figure { margin:22px 0; } figcaption,.cap { font-size:.82rem; color:var(--muted); }
figcaption { margin-top:8px; }
figure.mm { background:#fff; border:1px solid var(--line); border-radius:6px; padding:18px 10px; text-align:center; overflow-x:auto; }
figure.mm pre { font-size:.85rem; background:none; margin:0; }
.card { border:1px solid; border-radius:6px; padding:12px 14px; line-height:1.5; }
.card small { display:block; font-family:sans-serif; font-size:.72rem; font-weight:700; opacity:.85; }
.card b { display:block; font-family:ui-monospace,monospace; font-size:1.02rem; }
.card em { display:block; font-style:normal; font-family:sans-serif; font-size:.78rem; margin:2px 0 6px; }
.card code { background:rgba(255,255,255,.7); font-size:.78rem; }
.card p { margin:8px 0 0; font-size:.82rem; line-height:1.55; color:#222; }
.c-obj,.c-core { background:var(--commit-bg); border-color:var(--commit); color:var(--commit); }
.c-ref,.c-conf { background:var(--ref-bg); border-color:var(--ref); color:var(--ref); }
.c-head { background:var(--head-bg); border-color:var(--head); color:var(--head); }
.c-idx { background:var(--idx-bg); border-color:var(--idx); color:var(--idx); }
.c-hook { background:var(--tag-bg); border-color:var(--tag); color:var(--tag); }
.c-misc { background:#EEF0F2; border-color:#8a959b; color:#5B6770; }
.c-old { background:#EEF0F2; border-color:#8a959b; color:#5B6770; } .c-new { background:var(--blob-bg); border-color:var(--blob); color:var(--blob); }
.c-ghost { background:#fff; border:2px dashed #9aa6ab; color:#7b878d; }
.four { display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:12px; margin:22px 0; }
.four.files .card b { font-size:.9rem; margin-top:3px; }
.change { display:flex; align-items:center; gap:14px; margin:20px 0; flex-wrap:wrap; }
.change .card { flex:1 1 180px; } .arrow { font-family:sans-serif; font-size:.8rem; color:var(--muted); text-align:center; line-height:1.4; }
.fmt .seg { display:flex; flex-wrap:wrap; font-family:ui-monospace,monospace; font-size:1.05rem; gap:0; }
.fmt .b { padding:12px 16px 8px; text-align:center; border:1px solid #fff; color:#fff; font-weight:700; }
.fmt .b i { display:block; font-family:sans-serif; font-size:.68rem; font-style:normal; font-weight:400; opacity:.9; margin-top:2px; }
.fmt .k { background:var(--commit); } .fmt .s { background:#7C8A90; } .fmt .n { background:var(--tree); } .fmt .z { background:var(--idx); } .fmt .d { background:var(--blob); }
.layers { margin:22px 0; display:grid; gap:0; border-radius:6px; overflow:hidden; border:1px solid var(--line); }
.layer { padding:14px 20px; } .layer b { font-family:sans-serif; margin-right:12px; } .layer p { margin:4px 0 0; font-size:.88rem; }
.l-logic { background:var(--blob-bg); color:var(--blob); } .l-phys { background:var(--tree-bg); color:var(--tree); }
.l-logic p,.l-phys p { color:#222; } .layer u { text-decoration:none; font-weight:700; }
.treeupd { border:1px solid var(--line); border-radius:6px; padding:16px 20px; }
.treeupd ul.tr,.treeupd ul.tr ul { list-style:none; padding-left:26px; margin:6px 0; border-left:2px solid var(--line); }
.treeupd ul.tr { border:0; padding-left:0; }
.nd { display:inline-block; font-family:ui-monospace,monospace; font-size:.82rem; padding:2px 10px; border-radius:4px; border:1px solid; margin:2px 0; }
.nd em { font-style:normal; font-family:sans-serif; font-size:.68rem; font-weight:700; margin-left:8px; padding:0 6px; border-radius:3px; background:#fff; }
.nd.new { border-width:2px; } .nd.old { opacity:.55; border-style:dashed; }
.c-commit { background:var(--commit-bg); border-color:var(--commit); color:var(--commit); } .c-blob { background:var(--blob-bg); border-color:var(--blob); color:var(--blob); } .c-tree { background:var(--tree-bg); border-color:var(--tree); color:var(--tree); }
.cfg { margin:22px 0; font-family:sans-serif; display:grid; gap:6px; }
.lv { padding:9px 16px; border-radius:5px; background:var(--pale); display:flex; gap:14px; align-items:baseline; flex-wrap:wrap; font-size:.88rem; }
.lv b { min-width:5.5em; color:var(--accent); } .lv span { color:#333; }
.lv1 { margin-right:60px; } .lv2 { margin-right:40px; } .lv3 { margin-right:20px; } .lv4 { margin-right:0; }
.lv.here { background:var(--head-bg); outline:2px solid var(--head); } .lv.here em { color:var(--head); font-style:normal; font-weight:700; }
.win { font-size:.78rem; color:var(--muted); text-align:right; }
.unborn { border:1px solid var(--line); border-radius:6px; padding:16px; }
.unborn .row { display:flex; gap:14px; align-items:center; flex-wrap:wrap; margin-bottom:12px; }
.unborn .row .card { flex:1 1 200px; }
.unborn .row.two { align-items:stretch; margin-bottom:0; }
.reader { flex:1 1 220px; border-radius:6px; padding:10px 14px; font-family:sans-serif; font-size:.85rem; line-height:1.6; }
.reader.ok { background:var(--blob-bg); } .reader.ng { background:var(--bad-bg); } .reader u { text-decoration:none; font-weight:700; }
details.quiz { border:1px solid var(--line); border-radius:6px; margin:12px 0; }
details.quiz summary { cursor:pointer; padding:12px 16px; font-size:.92rem; background:var(--pale); border-radius:6px; }
details.quiz[open] summary { border-radius:6px 6px 0 0; }
details.quiz .answer { padding:2px 18px 10px; border-top:1px solid var(--line); font-size:.95rem; }
footer.pager { display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; border-top:2px solid var(--accent); margin-top:48px; padding-top:18px; font-size:.88rem; }
footer.pager a,footer.pager span { max-width:48%; }
@media (max-width:900px) { .layout { grid-template-columns:1fr; gap:0; } nav.toc { position:static; max-height:none; padding-top:16px; } .wrap { padding:26px 16px 48px; } h1 { font-size:1.5rem; } }
@media print { nav.toc { display:none; } .layout { display:block; } .code.term { background:#fff; border-color:#999; } .code.term pre,.term .cmd { color:#111; } }
'''

LEGEND = '''<p>色の見かた</p><div class="legend">
<span><i style="background:var(--commit)"></i>commit / objects</span><span><i style="background:var(--blob)"></i>blob</span>
<span><i style="background:var(--tree)"></i>tree</span><span><i style="background:var(--tag)"></i>tag</span>
<span><i style="background:var(--ref)"></i>refs（名札）</span><span><i style="background:var(--head)"></i>HEAD</span>
<span><i style="background:var(--idx)"></i>index</span></div>'''

MERMAID = '''<script type="module">
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
mermaid.initialize({ startOnLoad: true, theme: "base", themeVariables: { fontFamily: "Yu Gothic, Hiragino Kaku Gothic ProN, sans-serif", primaryColor: "#EFF5F6", primaryBorderColor: "#22586B", lineColor: "#65747A", primaryTextColor: "#111" } });
</script>'''

FAVICON = ('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2032%2032%22%3E'
           '%3Crect%20width%3D%2232%22%20height%3D%2232%22%20rx%3D%226%22%20fill%3D%22%23EFF5F6%22%2F%3E%3Cpath%20d%3D%22M6%207h8l2%202%202-2h8v19h-8l-2%202-2-2H6zM16%209v19%22%20fill%3D%22none%22%20stroke%3D%22%2322586B%22%20stroke-width%3D%222%22%2F%3E%3C%2Fsvg%3E')


def head(title, desc):
    return f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="description" content="{esc(desc)}">
<title>{esc(title)}</title>
<link rel="icon" type="image/svg+xml" href="{FAVICON}">
<style>{CSS}</style>
</head>
<body>'''


def page_link(idx):
    stem, short, mins = ALL[idx]
    label = f'{stem[:4]} {short}'
    if stem in PAGES:
        return f'<a href="{stem}.html">{esc(label)}</a>'
    return f'<span class="soon" title="準備中">{esc(label)}（準備中）</span>'


def build_page(idx):
    stem, short, mins = ALL[idx]
    lines = (ROOT / f'{stem}.md').read_text(encoding='utf-8').split('\n')
    ctx = Ctx()
    body = blocks(lines, ctx)
    num, _, rest = ctx.title.partition(' ')
    eyebrow = f'GIT STUDY · {num.rstrip(".").replace("_", "-")}'
    title = re.sub(r'`', '', rest)
    toc = ''.join(f'<li><a href="#{i}">{esc(t)}</a></li>' for i, t in ctx.toc)
    prev = page_link(idx - 1) if idx > 0 else '<a href="index.html">ポータル</a>'
    nxt = page_link(idx + 1) if idx + 1 < len(ALL) else '<a href="index.html">ポータルへ</a>'
    out = head(f'{num.rstrip(".")} {title}｜Git study', f'{title}（Git を .git の中身から理解する資料）')
    out += f'''
<div class="wrap">
<p class="back"><a href="index.html">← ポータルに戻る</a></p>
<header class="doc">
<p class="eyebrow">{esc(eyebrow)}</p>
<h1>{inline(title)}</h1>
<div class="chips"><span>目安 {mins} 分</span><span>git 2.50.1 / macOS</span><span>対象日 2026-09-17</span></div>
</header>
<div class="layout">
<nav class="toc" aria-label="目次"><p>目次</p><ul>{toc}</ul>{LEGEND}</nav>
<article>
{body}
<footer class="pager"><span>← 前　{prev}</span><span>次 →　{nxt}</span></footer>
</article>
</div>
</div>
{MERMAID}
</body>
</html>
'''
    (ROOT / f'{stem}.html').write_text(out, encoding='utf-8')
    print(f'{stem}.html')


# ---------------------------------------------------------------- ポータル
COURSES = [
    ('まず全体をつかむ', '27 分', [0, 1, 2], '.git の地図 → オブジェクト → git init'),
    ('ローカルの操作を理解する', '32 分', [3, 4, 5], 'hooks と bare → add / commit → branch'),
    ('リモートの操作を理解する', '38 分', [6, 7, 8], 'remote → fetch → pull'),
    ('困ったときだけ開く', '10 分', [9], '早見表・復旧手順・worktree・gc'),
]
PORTAL_CSS = '''
.wrap { max-width:1180px; } header.doc { border-bottom:1px solid var(--accent); }
.intro { margin:0; } .two { display:grid; grid-template-columns:1fr 1fr; gap:14px; margin:18px 0 6px; }
.two .card b { font-family:sans-serif; } .two .card p { font-size:.88rem; }
.sec { font-family:sans-serif; display:flex; justify-content:space-between; align-items:baseline; margin:34px 0 12px; color:var(--muted); font-size:.82rem; }
.sec h2 { margin:0; border:0; padding:0; font-size:1rem; color:var(--accent); }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr)); gap:20px; }
.course { border:1px solid var(--line); border-radius:4px; padding:22px; display:flex; flex-direction:column; }
.course .t { font-family:sans-serif; font-size:.76rem; color:var(--muted); margin:0 0 4px; }
.course h3 { margin:0 0 4px; font-size:1.12rem; } .course .d { font-size:.85rem; color:var(--muted); margin:0 0 14px; }
.mats { list-style:none; padding:0; margin:0; } .mats li { margin:0 0 10px; }
.m { display:flex; justify-content:space-between; gap:12px; align-items:center; padding:12px 16px; background:var(--pale); border-radius:3px; text-decoration:none; color:#111; }
.m:hover { background:#e4eef0; } .m b { display:block; color:var(--accent); font-family:sans-serif; font-size:.95rem; }
.m small { font-family:sans-serif; color:var(--muted); font-size:.72rem; } .m.off { background:#F6F7F8; color:#9aa4a9; } .m.off b { color:#9aa4a9; }
.legendbox { border:1px solid var(--line); border-radius:4px; padding:14px 20px; display:flex; flex-wrap:wrap; gap:8px 22px; align-items:center; font-family:sans-serif; font-size:.82rem; }
.legendbox .legend { display:flex; flex-wrap:wrap; gap:6px 18px; }
@media (max-width:600px) { .two { grid-template-columns:1fr; } }
'''


def build_index():
    cards = ''
    for title, mins, idxs, desc in COURSES:
        rows = ''
        for k in idxs:
            stem, short, m = ALL[k]
            label = f'{stem[:4]}　{short}'
            if stem in PAGES:
                rows += f'<li><a class="m" href="{stem}.html"><span><b>{esc(label)}</b><small>目安 {m} 分</small></span><span aria-hidden="true">→</span></a></li>'
            else:
                rows += f'<li><span class="m off"><span><b>{esc(label)}</b><small>準備中</small></span></span></li>'
        n = sum(1 for k in idxs if ALL[k][0] in PAGES)
        cards += f'<section class="course"><p class="t">合計 {mins} · {n}/{len(idxs)} 公開</p><h3>{esc(title)}</h3><p class="d">{esc(desc)}</p><ul class="mats">{rows}</ul></section>'
    out = head('Git を .git から読む｜Git study', 'Git を .git フォルダの中身から理解する解説資料のポータル。')
    out = out.replace('</style>', PORTAL_CSS + '</style>')
    out += f'''
<div class="wrap">
<header class="doc">
<p class="eyebrow">GIT STUDY · NOTES</p>
<h1>Git を <code>.git</code> から読む</h1>
<p class="intro">「コマンドの使い方」ではなく、「そのコマンドが <code>.git</code> のどのファイルを書き換えたか」を追う解説資料。</p>
<div class="chips" style="margin-top:12px"><span>git 2.50.1 / macOS</span><span>対象日 2026-09-17</span><span>出力はすべて実物</span></div>
</header>
<div class="sec"><h2>Git のコマンドがやることは、この 2 つだけ</h2></div>
<div class="two">
<div class="card c-obj"><small>その 1</small><b>.git/objects/ に「中身」を書き足す</b><p>不変・追記のみ。blob / tree / commit / tag の 4 種類</p></div>
<div class="card c-head"><small>その 2</small><b>.git/refs/ や .git/HEAD の「文字列」を書き換える</b><p>ブランチや現在地を指す、数十バイトのテキスト</p></div>
</div>
<p style="font-size:.9rem">merge も rebase も pull も、この組み合わせです。<code>.git</code> の中の数個のテキストファイルが読めれば、Git の挙動はほぼ説明がつきます。</p>
<div class="sec"><h2>読むコース</h2><span>通しで全部：約 1 時間 45 分　／　急ぐなら 01_1 → 01_5 → 01_8</span></div>
<div class="grid">{cards}</div>
<div class="sec"><h2>色の見かた</h2></div>
<div class="legendbox"><span>各ページの図・表で同じ色を使います。</span>{LEGEND.replace('<p>色の見かた</p>', '')}</div>
</div>
</body>
</html>
'''
    (ROOT / 'index.html').write_text(out, encoding='utf-8')
    print('index.html')


if __name__ == '__main__':
    for k in range(len(PAGES)):
        build_page(k)
    build_index()
