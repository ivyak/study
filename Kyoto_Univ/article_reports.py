"""Persist article explanations and render them for LIFE's list/detail views."""
import argparse
from datetime import datetime
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
from urllib.parse import urlsplit, unquote
from uuid import uuid4
from zoneinfo import ZoneInfo

REPO = Path(__file__).resolve().parent.parent
REPORTS = REPO / 'article_management'
READ_STATUSES = {'unread', 'reading', 'read'}
FIELDS = ('title', 'publishedAt', 'knownKnowledge', 'sources')
HTML_FIELDS = ('knownKnowledge', 'sources')


def local_article_asset(value, extensions):
    """Allow existing, relative portal assets only."""
    parsed = urlsplit(value)
    decoded = unquote(parsed.path)
    if parsed.scheme or parsed.netloc or not decoded or decoded.startswith('/') or '\\' in decoded or '\x00' in decoded:
        return False
    root = REPO / 'Kyoto_Univ'
    path = (root / decoded).resolve()
    return path.is_relative_to(root) and path.is_file() and path.suffix.lower() in extensions


class SafeArticleHTML(HTMLParser):
    """Keep article formatting while excluding active HTML and unsafe links."""
    TAGS = {'p', 'h2', 'h3', 'ul', 'ol', 'li', 'strong', 'em', 'code', 'br', 'blockquote',
            'details', 'summary', 'cite', 'figure', 'figcaption', 'table', 'caption', 'thead', 'tbody', 'tr', 'th', 'td'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'th':
            scope = dict(attrs).get('scope', '')
            self.parts.append(f'<th scope="{scope}">' if scope in ('col', 'row') else '<th>')
        elif tag == 'img':
            values = dict(attrs)
            src = values.get('src', '')
            if local_article_asset(src, {'.png', '.jpg', '.jpeg', '.webp'}):
                self.parts.append(f'<img src="{escape(src, quote=True)}" alt="{escape(values.get("alt", ""), quote=True)}" loading="lazy">')
        elif tag in self.TAGS:
            self.parts.append(f'<{tag}>')
        elif tag == 'a':
            href = dict(attrs).get('href', '')
            if urlsplit(href).scheme in ('http', 'https') or local_article_asset(href, {'.html', '.htm', '.pdf', '.png', '.jpg', '.jpeg', '.webp'}):
                self.parts.append(f'<a href="{escape(href, quote=True)}" target="_blank" rel="noopener noreferrer">')
                self.links.append('a')
            else:
                self.parts.append('<span>')
                self.links.append('span')

    def handle_endtag(self, tag):
        if tag in self.TAGS and tag != 'br':
            self.parts.append(f'</{tag}>')
        elif tag == 'a':
            if self.links:
                self.parts.append(f'</{self.links.pop()}>')

    def handle_data(self, data):
        self.parts.append(escape(data))


def safe_html(value):
    parser = SafeArticleHTML()
    parser.feed(value)
    parser.close()
    return ''.join(parser.parts)


def now():
    return datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(timespec='seconds')


def validate(report):
    if not isinstance(report, dict) or any(not isinstance(report.get(key), str) or not report[key].strip() for key in FIELDS):
        raise ValueError('記事タイトル・執筆時・既知知識・参照元が必要です')
    result = {key: report[key].strip() for key in FIELDS}
    if any(not result[key].startswith('<') for key in HTML_FIELDS):
        raise ValueError('記事解説の本文はHTMLで記述してください')
    if 'sections' in report:
        if not isinstance(report.get('summary'), str) or not report['summary'].strip().startswith('<'):
            raise ValueError('この記事が言いたいことをHTMLで記述してください')
        result['summary'] = safe_html(report['summary'])
        if not isinstance(report['sections'], list) or not report['sections']:
            raise ValueError('解説の節が必要です')
        result['sections'] = []
        for section in report['sections']:
            if not isinstance(section, dict) or any(not isinstance(section.get(k), str) or not section[k].strip() for k in ('title', 'html')):
                raise ValueError('解説の見出しと本文が必要です')
            slides = section.get('slides', [])
            if not isinstance(slides, list) or any(not isinstance(slide, dict) or any(not isinstance(slide.get(k), str) or not slide[k].strip() for k in ('title', 'html')) for slide in slides):
                raise ValueError('補助スライドの見出しと本文を確認してください')
            result['sections'].append({'title': section['title'], 'html': safe_html(section['html']), 'slides': [{'title': slide['title'], 'html': safe_html(slide['html'])} for slide in slides]})
    elif 'slides' in report:
        slides = report['slides']
        if not isinstance(slides, list) or not slides:
            raise ValueError('スライドが必要です')
        clean = []
        for slide in slides:
            if not isinstance(slide, dict) or slide.get('section') not in {'summary', 'prerequisites', 'industryKnowledge'} or any(not isinstance(slide.get(key), str) or not slide[key].strip() for key in ('title', 'html')):
                raise ValueError('スライドの区分・タイトル・HTMLを確認してください')
            html = safe_html(slide['html'])
            if not all(tag in html for tag in ('<ul>', '<figure>', '<figcaption>', '<p>')):
                raise ValueError('各スライドに短い箇条書き・図・結論を入れてください')
            clean.append({'section': slide['section'], 'title': slide['title'].strip(), 'html': html})
        if not {'summary', 'prerequisites', 'industryKnowledge'} <= {slide['section'] for slide in clean}:
            raise ValueError('要点・前提知識・業界知識のスライドが必要です')
        if any(not any('<figure>' in slide['html'] for slide in clean if slide['section'] == section) for section in ('prerequisites', 'industryKnowledge')):
            raise ValueError('前提知識と業界知識にはそれぞれ図が必要です')
        result['slides'] = clean
    else:
        for key in ('summary', 'prerequisites', 'industryKnowledge'):
            if not isinstance(report.get(key), str) or not report[key].strip().startswith('<'):
                raise ValueError('従来形式の解説本文が必要です')
            result[key] = report[key].strip()
        if any('<figure>' not in safe_html(result[key]) for key in ('prerequisites', 'industryKnowledge')):
            raise ValueError('前提知識と業界知識に図が必要です')
    for key in ('inputText', 'inputUrl'):
        if key in report:
            if not isinstance(report[key], str):
                raise ValueError('入力元は文字列で指定してください')
            result[key] = report[key]
    return result


def save(report, url='', report_id=None, generated_at=None):
    if report.get('status') == 'failed':
        raise ValueError(report.get('error') or '記事を取得・解説できませんでした')
    result = validate(report)
    result.update(status=report.get('status', 'complete'), error=report.get('error', ''), readStatus='unread')
    result.update(id=report_id or uuid4().hex, generatedAt=generated_at or now(), url=url or result.get('inputUrl', ''))
    if len(result['id']) != 32 or any(c not in '0123456789abcdef' for c in result['id']):
        raise ValueError('記事IDが不正です')
    REPORTS.mkdir(exist_ok=True)
    path = REPORTS / f"{result['id']}.json"
    if report_id and path.is_file():
        previous = json.loads(path.read_text(encoding='utf-8'))
        result['generatedAt'] = previous.get('generatedAt', result['generatedAt'])
        result['readStatus'] = previous.get('readStatus', 'unread')
        if previous.get('readStatusUpdatedAt'):
            result['readStatusUpdatedAt'] = previous['readStatusUpdatedAt']
        if 'bookmarkIndex' in previous:
            result['bookmarkIndex'] = previous['bookmarkIndex']
            result['bookmarkUpdatedAt'] = previous.get('bookmarkUpdatedAt', '')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return result


def update_read_status(report_id, read_status):
    if not isinstance(report_id, str) or len(report_id) != 32 or any(c not in '0123456789abcdef' for c in report_id):
        raise ValueError('記事IDが不正です')
    if not isinstance(read_status, str) or read_status not in READ_STATUSES:
        raise ValueError('読書ステータスが不正です')
    path = REPORTS / f'{report_id}.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    report.update(readStatus=read_status, readStatusUpdatedAt=now())
    if read_status == 'read':
        report.update(bookmarkIndex=None, bookmarkUpdatedAt=now())
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return report


def update_bookmark(report_id, slide_index):
    if not isinstance(report_id, str) or len(report_id) != 32 or any(c not in '0123456789abcdef' for c in report_id):
        raise ValueError('記事IDが不正です')
    path = REPORTS / f'{report_id}.json'
    report = json.loads(path.read_text(encoding='utf-8'))
    if slide_index is not None:
        if isinstance(slide_index, bool) or not isinstance(slide_index, int) or slide_index < 0 or slide_index >= (len(report['sections']) + 1 if 'sections' in report else len(report['slides']) if 'slides' in report else 1000):
            raise ValueError('しおりの位置が不正です')
    report['bookmarkIndex'] = slide_index
    report['bookmarkUpdatedAt'] = now()
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
    return report


def article_records():
    records = []
    for path in REPORTS.glob('????????????????????????????????.json'):
        report = json.loads(path.read_text(encoding='utf-8'))
        validate(report)
        record = {key: report[key] for key in ('id', 'title', 'publishedAt', 'generatedAt', 'url')}
        record.update(readStatus=report.get('readStatus', 'unread'), readStatusUpdatedAt=report.get('readStatusUpdatedAt', ''), bookmarkIndex=report.get('bookmarkIndex'), bookmarkUpdatedAt=report.get('bookmarkUpdatedAt', ''), inputText=report.get('inputText', ''))
        if 'sections' in report:
            clean = validate(report)
            record.update(summary=clean['summary'], sections=clean['sections'])
            record['appendix'] = '<h2>参照した資料</h2>' + safe_html(report['knownKnowledge']) + safe_html(report['sources'])
            record['error'] = report.get('error', '')
        elif 'slides' in report:
            record['slides'] = [{'section': slide['section'], 'title': slide['title'], 'html': safe_html(slide['html'])} for slide in report['slides']]
            record['appendix'] = '<h2>既知知識として参照したリポジトリ情報</h2>' + safe_html(report['knownKnowledge']) + '<h2>記事・参考資料</h2>' + safe_html(report['sources'])
            if report.get('error'):
                record['appendix'] = f'<p>確認範囲・未確認事項：{escape(report["error"])}</p>' + record['appendix']
        else:
            record['html'] = ''.join([
                f'<p>確認範囲・未確認事項：{escape(report["error"])}</p>' if report.get('error') else '',
                safe_html(report['summary']), '<h2>記事を読むために必要な前提知識</h2>', safe_html(report['prerequisites']),
                '<h2>記事に関して、業界人なら知っておきたい知識</h2>', safe_html(report['industryKnowledge']),
                '<h2>既知知識として参照したリポジトリ情報</h2>', safe_html(report['knownKnowledge']),
                '<h2>記事・参考資料</h2>', safe_html(report['sources']),
            ])
        records.append(record)
    return sorted(records, key=lambda item: item['generatedAt'], reverse=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['save'])
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--url', default='')
    parser.add_argument('--id', help='既存記事のID。日時・読書ステータス・しおりを保持して更新')
    args = parser.parse_args()
    result = save(json.loads(args.input.read_text(encoding='utf-8')), args.url, report_id=args.id)
    print(json.dumps({'id': result['id'], 'path': str(REPORTS / (result['id'] + '.json'))}, ensure_ascii=False))
