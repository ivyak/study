#!/usr/bin/env python3
"""授業フォルダのHTML資料を読み取り、ローカル用ポータルを更新する。"""
from html import escape
from html.parser import HTMLParser
from pathlib import Path
import re
import json
from urllib.parse import quote
from past_exams import snapshot, resources
from skill_catalog import build_skills
from goal_reports import goal_records
from article_reports import article_records

ROOT = Path(__file__).resolve().parent
SHELL_START = '<!-- LIFE-SHELL:START -->'
SHELL_END = '<!-- LIFE-SHELL:END -->'
# One experiment course spans four timetable cells. Share its documents and
# resources so edits to the canonical folder appear in every cell.
MATH_EXPERIMENT_SLOTS = (('月', 3), ('月', 4), ('火', 3), ('火', 4))


class Metadata(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self.subtitle = []
        self.in_title = False
        self.in_subtitle = False
        self.hidden_from_portal = False
        self.fields = {}
        self.in_body = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'body':
            self.in_body = True
        if tag == 'meta' and attrs.get('name', '').startswith('study-'):
            self.fields[attrs['name']] = attrs.get('content', '')
        # タブから開く補助ページは、study-portal=hiddenで一覧への重複掲載を避ける。
        if tag == 'meta' and attrs.get('name') == 'study-portal' and attrs.get('content') == 'hidden':
            self.hidden_from_portal = True
        if tag == 'title' and not self.in_body:
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
        if metadata.hidden_from_portal:
            continue
        title = ''.join(metadata.subtitle).strip() or ''.join(metadata.title).strip() or path.stem
        result.append((title, relative, path.relative_to(folder)))
    return result


def material_data(title, relative):
    path = ROOT / relative
    metadata = Metadata()
    metadata.feed(path.read_text(encoding='utf-8-sig', errors='replace'))
    lesson_text = metadata.fields.get('study-lesson', '')
    match = re.search(r'第([0-9０-９]+)回', path.stem)
    if not lesson_text and match:
        lesson_text = match[1].translate(str.maketrans('０１２３４５６７８９', '0123456789'))
    lesson = int(lesson_text) if lesson_text.isdigit() else None
    kind = metadata.fields.get('study-kind')
    if not kind:
        kind = ('理解度クイズ' if 'クイズ' in path.stem else
                '対応問題' if any(word in path.stem for word in ['演習問題', '対応問題']) else
                '要約' if '要約' in path.stem else '解説')
    return {
        'title': title,
        'url': quote(relative.as_posix(), safe='/'),
        'lesson': lesson,
        'kind': kind,
        # Filesystem modification times are not document creation dates.
        'created': metadata.fields.get('study-created', ''),
    }


def course_records():
    folders = sorted((p for p in ROOT.iterdir()
                      if p.is_dir() and not p.name.startswith(('.', '__'))
                      and p.name != 'ui' and not p.is_symlink()), key=course_order)
    entries = []
    for folder in folders:
        schedule, name = course_info(folder)
        normalized = schedule.translate(str.maketrans('０１２３４５６７８９', '0123456789'))
        match = re.fullmatch(r'(\d{4})(前期|後期)([月火水木金土日])(\d+)', normalized)
        if not match:
            continue
        year, semester, day, period = match.groups()
        docs = documents(folder)
        past_exams = snapshot(folder)
        entries.append({
            'id': 'calculus2' if folder.name == '[2026後期木３]微分積分学続論II' else folder.name,
            'name': name,
            'folder': folder.name,
            'term': year + semester,
            'day': day,
            'period': int(period),
            'hasPastPaper': past_exams['hasPastPaper'],
            'pastExams': past_exams,
            'resources': {category: resources(folder, category) for category in ['weapons', 'practice']},
            'documents': [material_data(title, relative) for title, relative, _ in docs],
        })
    experiment = next((entry for entry in entries
                       if entry['id'] == '[2026後期月３]数理工学実験'), None)
    if experiment:
        for day, period in MATH_EXPERIMENT_SLOTS[1:]:
            entries.append({**experiment,
                            'id': f'[2026後期{day}{period}]数理工学実験',
                            'day': day, 'period': period})
    entries.sort(key=lambda item: (item['term'][:4], 0 if item['term'].endswith('前期') else 1,
                                   '月火水木金土日'.index(item['day']), item['period'], item['name']))
    return entries


def sync_document_shells(shell):
    """Keep LIFE lesson pages on the same sidebar component as the portal."""
    replacement = f'{SHELL_START}\n{shell.rstrip()}\n{SHELL_END}'
    for path in ROOT.rglob('*.html'):
        if path.is_relative_to(ROOT / 'ui') or path == ROOT / 'index.html':
            continue
        content = path.read_text(encoding='utf-8')
        if 'data-life-page="document"' not in content:
            continue
        if content.count(SHELL_START) != 1 or content.count(SHELL_END) != 1:
            raise ValueError(f'LIFE document is missing the shared shell markers: {path}')
        start = content.index(SHELL_START)
        end = content.index(SHELL_END) + len(SHELL_END)
        updated = content[:start] + replacement + content[end:]
        if updated != content:
            path.write_text(updated, encoding='utf-8')


def build():
    ui = ROOT / 'ui'
    template = (ui / 'portal.html').read_text(encoding='utf-8')
    shell = (ui / 'shell.html').read_text(encoding='utf-8')
    sync_document_shells(shell)
    entries = course_records()
    skill_cards = build_skills(shell)
    payload = json.dumps(entries, ensure_ascii=False).replace('<', chr(92) + 'u003c')
    fallback = ['<p>授業資料（JavaScriptを有効にすると時間割から選べます）</p>']
    for course in entries:
        fallback.append(f"<h2>{escape(course['name'])}</h2><ul>")
        for doc in course['documents']:
            fallback.append(f'<li><a href="{escape(doc["url"], quote=True)}">{escape(doc["title"])}</a></li>')
        fallback.append('</ul>')
    output = template.replace('__SHELL__', shell).replace('__COURSE_DATA__', payload).replace('__FALLBACK_LINKS__', '\n'.join(fallback)).replace('__SKILL_CARDS__', skill_cards)
    goals = json.dumps(goal_records(), ensure_ascii=False).replace('<', chr(92) + 'u003c')
    output = output.replace('__GOAL_DATA__', goals)
    articles = json.dumps(article_records(), ensure_ascii=False).replace('<', chr(92) + 'u003c')
    output = output.replace('__ARTICLE_DATA__', articles)
    (ROOT / 'index.html').write_text(output, encoding='utf-8')
    total = sum(len(course['documents']) for course in entries)
    print(f'index.html を更新しました：{len(entries)} 授業 / {total} 資料')


if __name__ == '__main__':
    build()
