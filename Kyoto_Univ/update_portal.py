#!/usr/bin/env python3
"""授業フォルダのHTML資料を読み取り、ローカル用ポータルを更新する。"""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self.subtitle = []
        self.in_title = False
        self.in_subtitle = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag == 'p' and 'subtitle' in attrs.get('class', '').split():
            self.in_subtitle = True

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag == 'p':
            self.in_subtitle = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)
        if self.in_subtitle:
            self.subtitle.append(data)


def course_info(folder):
    match = re.fullmatch(r'\[(.*?)\](.+)', folder.name)
    return match.groups() if match else ('', folder.name)


def course_order(folder):
    schedule, name = course_info(folder)
    schedule = schedule.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    match = re.fullmatch(r'(\d{4})(前期|後期)([月火水木金土日])(\d+)', schedule)
    if match:
        year, term, day, period = match.groups()
        return (-int(year), 0 if term == '前期' else 1, '月火水木金土日'.index(day), int(period), name)
    return (0, 0, 7, 0, folder.name)


def display_schedule(schedule):
    schedule = schedule.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    match = re.fullmatch(r'(\d{4})(前期|後期)([月火水木金土日])(\d+)', schedule)
    if not match:
        return schedule
    year, term, day, period = match.groups()
    return f'{year}年度 {term} · {day}曜{period}限'


def documents(folder):
    result = []
    for path in sorted(folder.rglob('*'), key=lambda p: p.relative_to(folder).as_posix()):
        relative = path.relative_to(ROOT)
        if path.suffix.lower() not in {'.html', '.htm'} or not path.is_file():
            continue
        if any(part.startswith('.') for part in relative.parts):
            continue
        # ポータルの対象はこのディレクトリ内にある資料のみ。
        if not path.resolve().is_relative_to(ROOT):
            continue
        metadata = Metadata()
        metadata.feed(path.read_text(encoding='utf-8-sig', errors='replace'))
        title = ''.join(metadata.subtitle).strip() or ''.join(metadata.title).strip() or path.stem
        result.append((title, relative, path.relative_to(folder)))
    return result


STYLE = '''
:root { --accent: #22586B; --muted: #65747A; --pale: #EFF5F6; --line: #dee7e9; }
* { box-sizing: border-box; }
html { background: #fff; color: #111; color-scheme: light; }
body { margin: 0; font-family: "Yu Mincho", "Hiragino Mincho ProN", "Noto Serif CJK JP", serif; line-height: 1.9; }
main { max-width: 1640px; margin: 0 auto; padding: 38px 32px 56px; }
h1, h2, nav, .eyebrow, .schedule, .count, footer { font-family: "Yu Gothic", "Hiragino Kaku Gothic ProN", sans-serif; }
header { border-bottom: 1px solid var(--accent); padding-bottom: 24px; }
.eyebrow { margin: 0 0 8px; color: var(--accent); font-size: .85rem; letter-spacing: .04em; }
h1 { margin: 0 0 10px; font-size: 1.8rem; line-height: 1.5; }
.intro { margin: 0; font-size: 1rem; }
.overview { display: flex; align-items: baseline; justify-content: space-between; gap: 16px; margin: 24px 0 10px; }
.overview p { margin: 0; color: var(--muted); font-size: .8rem; }
nav { margin: 0 0 24px; font-size: .83rem; }
nav ul { display: flex; flex-wrap: wrap; gap: 4px 18px; list-style: none; margin: 0; padding: 0; }
nav li { margin: 3px 0; }
nav a { display: inline-block; color: var(--muted); text-decoration: none; padding: 1px 5px; border-radius: 3px; }
a { text-underline-offset: .22em; }
a:hover { color: var(--accent); background: var(--pale); }
a:focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; }
.course-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(100%, 280px), 1fr)); gap: 20px; }
.course { aspect-ratio: 1; min-width: 0; min-height: 0; padding: 24px; border: 1px solid var(--line); border-radius: 4px; display: flex; flex-direction: column; overflow: hidden; scroll-margin-top: 24px; }
.course-content { flex: 1; min-height: 0; overflow-y: auto; margin-top: 14px; scrollbar-width: thin; }
.course-heading { display: flex; justify-content: space-between; align-items: baseline; gap: 16px; }
.schedule { margin: 0 0 4px; color: var(--muted); font-size: .76rem; }
h2 { margin: 0; font-size: 1.12rem; color: var(--accent); line-height: 1.65; overflow-wrap: anywhere; }
.count { flex-shrink: 0; color: var(--muted); font-size: .75rem; }
.materials { list-style: none; margin: 0; padding: 0; }
.materials li + li { margin-top: 10px; }
.material { display: flex; align-items: center; justify-content: space-between; gap: 12px; color: #111; text-decoration: none; padding: 13px 16px; background: var(--pale); border-radius: 3px; }
.material:hover { background: #e4eef0; }
.material-title { display: block; color: var(--accent); font-size: .98rem; }
.filename { display: block; color: var(--muted); font-family: sans-serif; font-size: .72rem; overflow-wrap: anywhere; margin-top: 3px; }
.arrow { color: var(--accent); flex-shrink: 0; font-family: sans-serif; }
.empty { margin: 12px 0 0; color: var(--muted); font-size: .85rem; }
footer { border-top: 1px solid var(--accent); margin-top: 32px; padding-top: 16px; color: var(--muted); font-size: .73rem; }
@media (max-width: 600px) {
  main { padding: 26px 16px 40px; }
  .course-grid { gap: 14px; }
  .course { padding: 20px; }
  h1 { font-size: 1.5rem; }
  h2 { font-size: 1.05rem; }
  .course-heading { gap: 10px; }
  .material { padding: 12px; gap: 10px; }
}
@media print { main { max-width: none; padding: 0; } nav { display: none; } .course-grid { grid-template-columns: repeat(2, 1fr); } .course { break-inside: avoid; aspect-ratio: auto; min-height: 65mm; overflow: visible; } .course-content { overflow: visible; } }
'''


def build():
    folders = sorted((p for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(('.', '__')) and not p.is_symlink()), key=course_order)
    entries = [(folder, documents(folder)) for folder in folders]
    total = sum(len(docs) for _, docs in entries)
    nav = []
    sections = []
    for index, (folder, docs) in enumerate(entries, 1):
        schedule, name = course_info(folder)
        ident = f'course-{index}'
        nav.append(f'<li><a href="#{ident}">{escape(name)}</a></li>')
        if docs:
            rows = []
            for title, relative, course_relative in docs:
                url = quote(relative.as_posix(), safe='/')
                rows.append(f'''<li><a class="material" href="{url}">
<span class="material-title">{escape(title)}</span>
<span class="arrow" aria-hidden="true">→</span>
</a></li>''')
            content = '<ul class="materials">\n' + '\n'.join(rows) + '\n</ul>'
        else:
            content = '<p class="empty">HTML資料はまだありません。</p>'
        sections.append(f'''<section class="course" id="{ident}" aria-labelledby="{ident}-title">
<p class="schedule">{escape(display_schedule(schedule))}</p>
<div class="course-heading"><h2 id="{ident}-title">{escape(name)}</h2><span class="count">{len(docs)} 資料</span></div>
<div class="course-content">{content}</div>
</section>''')
    favicon = quote('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="6" fill="#EFF5F6"/><path d="M6 7h8l2 2 2-2h8v19h-8l-2 2-2-2H6zM16 9v19" fill="none" stroke="#22586B" stroke-width="2"/></svg>', safe='')
    output = f'''<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light">
<meta name="description" content="京都大学の授業ごとに講義ノート・HTML資料を閲覧する学習ポータル。">
<title>授業ノート｜Kyoto Univ.</title>
<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,{favicon}">
<style>{STYLE}</style>
</head>
<body>
<main>
<header>
<p class="eyebrow">KYOTO UNIV. · STUDY NOTES</p>
<h1>授業ノート</h1>
<p class="intro">授業ごとのノートと資料を、ここから。</p>
</header>
<div class="overview"><p id="course-nav-label">授業一覧</p><p>{len(entries)} 授業 / {total} 資料</p></div>
<nav aria-labelledby="course-nav-label"><ul>
{chr(10).join(nav)}
</ul></nav>
<div class="course-grid">
{chr(10).join(sections)}
</div>
<footer>Kyoto Univ. · 学習資料</footer>
</main>
</body>
</html>
'''
    (ROOT / 'index.html').write_text(output, encoding='utf-8')
    print(f'index.html を更新しました：{len(entries)} 授業 / {total} 資料')


if __name__ == '__main__':
    build()
