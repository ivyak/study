#!/usr/bin/env python3
"""Public listing collection and deterministic offline candidate matching."""
import argparse
from collections import deque
from datetime import datetime, timezone
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import quote, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

ROOTS = [
    ('kuwiki', 'https://www.kuwiki.net/'),
    ('kuinfo2020', 'https://drive.google.com/drive/folders/10V3htAY7umRt8SR9FeuvP8wk0t86snaj'),
    ('ku1025', 'https://ku1025.netlify.app/'),
    ('past-exam-drive', 'https://drive.google.com/drive/folders/1yGxF3mHVCyU9GUaZlwP_i-2kq8pt3-kc'),
]
FOLDER = 'application/vnd.google-apps.folder'
CLASSIFICATIONS = ['全学共通科目', '工学部専門科目', '他学部聴講科目', '大学院授業科目',
                   '大学院入試科目', '人社群', '情報群', '自然群', '言語（E2含む）',
                   '地球工学科専門科目', '建築学科専門科目', '情報学科専門科目',
                   '物理工学科専門科目', '理工化学科専門科目', '電気電子工学科専門科目']


def norm(text):
    return re.sub(r'\s+', '', unicodedata.normalize('NFKC', text)).casefold()


def matches(text, terms):
    return any(norm(term) in norm(text) for term in terms)


GROUPS = ['sameTeacherPreviousYear', 'sameTeacherEarlier', 'differentTeacher']


def filename_match(filename, terms, teacher, academic_year):
    """Name-string matching only; neither hierarchy nor document content supplies fields."""
    name = unicodedata.normalize('NFKC', filename)
    compact = norm(name)
    course = any(re.search(r'(?<![a-z0-9一-龯ぁ-んァ-ヶ])' + re.escape(norm(term))
                 + r'(?=$|[^a-z0-9一-龯ぁ-んァ-ヶ]|(?:19|20)\d{2}(?!\d)|期末|中間|問題|解答|演習|講義|資料|過去問)', compact)
                 for term in terms)
    years = sorted(set(int(value) for value in re.findall(r'(?<!\d)(?:19|20)\d{2}(?!\d)', name)))
    year = years[0] if len(years) == 1 else None
    labels = [label.strip() for pair in re.findall(r'\(([^()]*)\)|\[([^\[\]]*)\]', name)
              for label in pair if label.strip()]
    teachers = [label for label in labels if re.fullmatch(r'[一-龯ぁ-んァ-ヶA-Za-z・.\s]+', label)
                and not re.search(r'解答|問題|演習|講義|資料|前期|後期|年度|期末|中間|過去問', label)]
    listed_teacher = teachers[0] if len(set(map(norm, teachers))) == 1 and teachers else None
    relation = ('same' if norm(listed_teacher) == norm(teacher) else 'different') if teacher and listed_teacher else 'unknown'
    groups = []
    if course and relation == 'same' and year == academic_year - 1:
        groups.append('sameTeacherPreviousYear')
    if course and relation == 'same' and year is not None and year < academic_year - 1:
        groups.append('sameTeacherEarlier')
    if course and relation == 'different':
        groups.append('differentTeacher')
    return {'courseMatched': course, 'teacherName': listed_teacher, 'year': year,
            'teacherRelation': relation, 'groups': groups}


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def fetch(url):
    parts = urlsplit(url)
    url = urlunsplit((parts.scheme, parts.netloc, quote(parts.path, safe='/%:@'), parts.query, ''))
    request = Request(url, headers={'User-Agent': 'KyotoPastExamLookup/1.0'})
    with urlopen(request, timeout=25) as response:
        return response.read().decode('utf-8')


def drive_rows(html):
    match = re.search(r"window\['_DRIVE_ivd'\]\s*=\s*'((?:\\.|[^'])*)'", html)
    if not match:
        raise ValueError('Drive public listing marker missing (access or layout changed)')
    # Decode JS escapes without evaluating JavaScript or corrupting Unicode.
    def escape(match):
        value = match[1]
        if value.startswith(('x', 'u')):
            return chr(int(value[1:], 16))
        return {'n': '\n', 'r': '\r', 't': '\t', '\\': '\\', "'": "'", '/': '/'}.get(value, '\\' + value)
    decoded = re.sub(r'\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|.)', escape, match[1])
    payload = json.loads(decoded)
    rows = payload[0]
    if rows is None:
        raise ValueError('Drive listing unavailable; empty folder not established')
    if not isinstance(rows, list):
        raise ValueError('Drive listing schema changed')
    for row in rows:
        if not isinstance(row, list) or len(row) < 4 or not all(isinstance(row[i], str) for i in (0, 2, 3)):
            raise ValueError('Drive entry schema changed')
    return rows


class Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links, self.href, self.label = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.href, self.label = dict(attrs).get('href'), []

    def handle_data(self, data):
        if self.href is not None:
            self.label.append(data)

    def handle_endtag(self, tag):
        if tag == 'a' and self.href is not None:
            self.links.append((self.href, ''.join(self.label).strip()))
            self.href = None


def collect(args):
    terms = [args.course, *args.alias]
    if args.resume and Path(args.out).exists():
        index = json.loads(Path(args.out).read_text())
        if index['terms'] != terms:
            raise ValueError('Resume requires identical course and aliases')
        if index.get('teacher') and index['teacher'] != args.teacher:
            raise ValueError('Resume requires the same teacher spelling')
        index['teacher'] = args.teacher
    else:
        index = {'schema': 1, 'terms': terms, 'teacher': args.teacher, 'started_at': now(), 'sources': []}
        for name, root in ROOTS:
            pending = [{'url': root, 'path': name, 'kind': 'html'}]
            if name == 'kuwiki':
                queries = list(dict.fromkeys(
                    variant for term in terms for variant in
                    (term, re.sub(r'\s+', '', unicodedata.normalize('NFKC', term)))))
                pending = [{'url': root + 'api/exams?' + urlencode({'q': term}),
                            'path': name, 'kind': 'api'} for term in queries]
            index['sources'].append({'name': name, 'root': root, 'visited': [], 'pending': pending,
                                     'errors': [], 'items': [], 'drive_listing_complete': False})
    for source in index['sources']:
        queue = deque(source['pending'])
        visited = set(source['visited'])
        if args.resume:
            queue.extend(error['task'] for error in source['errors'])
            source['errors'] = []
        seen_items = {(item['url'], item['path']) for item in source['items']}
        count = 0
        while queue and count < args.max_pages:
            task = queue.popleft()
            url, path = task['url'], task['path']
            if url in visited:
                continue
            visited.add(url)
            count += 1
            try:
                html = fetch(url)
                if task['kind'] == 'api':
                    entries = json.loads(html)
                    if not isinstance(entries, list):
                        raise ValueError('Wiki API schema changed')
                    for entry in sorted(entries, key=lambda e: e['name']):
                        queue.append({'url': entry['drive_link'], 'path': path+'/'+entry['name'], 'kind': 'drive'})
                    continue
                if urlsplit(url).hostname == 'drive.google.com' and '/folders/' in url:
                    for row in sorted(drive_rows(html), key=lambda r: (norm(r[2]), r[0])):
                        child_path = path + '/' + row[2]
                        if row[3] == FOLDER:
                            queue.append({'url': 'https://drive.google.com/drive/folders/'+row[0],
                                          'path': child_path, 'kind': 'drive'})
                        else:
                            item = {'url': 'https://drive.google.com/file/d/'+row[0]+'/view',
                                    'path': child_path, 'name': row[2], 'mime': row[3]}
                            if (item['url'], item['path']) not in seen_items:
                                source['items'].append(item)
                                seen_items.add((item['url'], item['path']))
                else:
                    parser = Links()
                    parser.feed(html)
                    for href, label in sorted(parser.links):
                        link = urljoin(url, href).split('#')[0]
                        if urlsplit(link).hostname == 'ku1025.netlify.app':
                            if label in CLASSIFICATIONS or matches(label, terms):
                                queue.append({'url': link, 'path': path+'/'+label, 'kind': 'html'})
                        elif matches(path, terms) and urlsplit(link).hostname == 'drive.google.com':
                            if '/folders/' in link:
                                queue.append({'url': link, 'path': path+'/'+label, 'kind': 'drive'})
                            elif (link, path+'/'+label) not in seen_items:
                                source['items'].append({'url': link, 'path': path+'/'+label,
                                                        'name': label, 'mime': 'unknown'})
                                seen_items.add((link, path+'/'+label))
            except Exception as error:
                source['errors'].append({'task': task, 'error': str(error)})
                visited.remove(url)
            finally:
                source['visited'] = sorted(visited)
                source['pending'] = list(queue)
                index['updated_at'] = now()
                Path(args.out).write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n')
                print(f"{source['name']}: {count} pages, {len(source['items'])} items, {len(queue)} pending", file=sys.stderr)
        # Skipped duplicate URLs also leave the queue; persist the final frontier.
        source['pending'] = list(queue)
        source['page_limit'] = args.max_pages
        source['page_limit_reached'] = bool(queue and count >= args.max_pages)
        index['updated_at'] = now()
        Path(args.out).write_text(json.dumps(index, ensure_ascii=False, indent=2)+'\n')
    return {'index': args.out, 'sources': [
        {'name': s['name'], 'pages': len(s['visited']), 'items': len(s['items']),
         'pending': len(s['pending']), 'errors': len(s['errors'])} for s in index['sources']]}


def search(args):
    index = json.loads(Path(args.index).read_text())
    if index.get('teacher') and index['teacher'] != args.teacher:
        raise ValueError('Search teacher spelling must match the collected index')
    terms = [args.course, *args.alias]
    candidates = []
    for source in index['sources']:
        for item in source['items']:
            if matches(item['path'], terms):
                candidates.append({**item, 'source': source['name'],
                    'filenameMatch': filename_match(item['name'], terms, args.teacher, args.academic_year)})
    candidates.sort(key=lambda c: (GROUPS.index(c['filenameMatch']['groups'][0]) if c['filenameMatch']['groups'] else 3,
                                  c['source'], norm(c['name']), c['url']))
    return {'course': args.course, 'teacher': args.teacher, 'academic_year': args.academic_year,
            'previous_year': args.academic_year-1, 'started_at': index['started_at'],
            'updated_at': index['updated_at'], 'listing_terms': index['terms'],
            'coverage': [{'source': s['name'], 'pages': len(s['visited']), 'pending': s['pending'],
                          'errors': s['errors'], 'drive_listing_complete': s['drive_listing_complete'],
                          'page_limit': s.get('page_limit'), 'page_limit_reached': s.get('page_limit_reached', False)}
                         for s in index['sources']], 'candidates': candidates}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    for command in ('collect', 'search'):
        sub = commands.add_parser(command)
        sub.add_argument('--course', required=True)
        sub.add_argument('--alias', action='append', default=[])
        if command == 'collect':
            sub.add_argument('--teacher', required=True)
            sub.add_argument('--out', required=True)
            sub.add_argument('--max-pages', type=int, default=200)
            sub.add_argument('--resume', action='store_true')
        else:
            sub.add_argument('--index', required=True)
            sub.add_argument('--teacher', required=True)
            sub.add_argument('--academic-year', type=int, required=True)
    args = parser.parse_args()
    if not args.course.strip() or not args.teacher.strip() or any(not a.strip() for a in args.alias):
        parser.error('Course, teacher and aliases must not be empty')
    if args.command == 'collect' and args.max_pages < 1:
        parser.error('--max-pages must be positive')
    print(json.dumps(collect(args) if args.command == 'collect' else search(args),
                     ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
