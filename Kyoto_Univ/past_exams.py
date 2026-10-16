"""Filename-only comparisons and link-only past-exam reports."""
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
import importlib.util
import json
import re
from urllib.parse import quote, urlsplit, parse_qs

ROOT = Path(__file__).resolve().parent
SKILL = ROOT.parent / '.codex/skills/kyoto-past-exams'
SOURCE_NAMES = ['kuwiki', 'kuinfo2020', 'ku1025', 'past-exam-drive']
CONDITIONS = ['sameTeacherPreviousYear', 'sameTeacherEarlier', 'differentTeacher']
MATERIAL_TYPES = ['問題', '講義資料', '解答', '演習問題', '未確認']


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


@lru_cache(maxsize=1)
def skill_module():
    spec = importlib.util.spec_from_file_location('kyoto_exam_search', SKILL / 'scripts/search.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def candidate_key(url):
    parts = urlsplit(url or '')
    if parts.hostname == 'drive.google.com':
        match = re.search(r'/file/d/([^/]+)', parts.path)
        drive_id = match[1] if match else parse_qs(parts.query).get('id', [None])[0]
        if drive_id:
            return 'drive:' + drive_id
    return url


def report_path(folder):
    return folder / 'study/past_exam_search.json'


def load_report(folder):
    path = report_path(folder)
    if not path.is_file():
        return {'schema': 2, 'execution': {'status': 'unsearched'}, 'coverage': [], 'candidates': []}
    try:
        report = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(report, dict) or report.get('schema') not in {1, 2}:
            raise ValueError('Unsupported search report')
        return report
    except (ValueError, OSError) as error:
        return {'schema': 2, 'execution': {'status': 'failed', 'error': f'保存結果を読み取れません：{error}'}, 'coverage': [], 'candidates': []}


def save_report(folder, report):
    path = report_path(folder)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def normalize_candidate(candidate, course, teacher, year, aliases=()):
    candidate = {key: value for key, value in candidate.items() if key not in {'local', 'localPath', 'sha256', 'verification'}}
    candidate['filenameMatch'] = skill_module().filename_match(candidate.get('name', ''), [course, *aliases], teacher, year)
    candidate.setdefault('subjectName', course)
    types = candidate.get('materialTypes', ['未確認'])
    candidate['materialTypes'] = types if types and all(value in MATERIAL_TYPES for value in types) else ['未確認']
    candidate.setdefault('evidence', '')
    return candidate


def exam_confirmed(candidate):
    return ('問題' in candidate.get('materialTypes', []) and bool(candidate.get('evidence'))
            and candidate.get('filenameMatch', {}).get('courseMatched') is True)


def unscanned_urls(report):
    roots = dict(skill_module().ROOTS)
    entries = {}
    def add(url, reason, path='', source=''):
        if urlsplit(url or '').scheme in {'http', 'https'}:
            key = (source, path or url)
            entry = entries.setdefault(key, {'url': url, 'path': path or source or url,
                                             'source': source, 'reasons': []})
            if reason not in entry['reasons']:
                entry['reasons'].append(reason)
    by_source = {source['source']: source for source in report.get('coverage', [])}
    for name in SOURCE_NAMES:
        source = by_source.get(name)
        if source is None:
            if report.get('execution', {}).get('status') != 'unsearched':
                add(roots[name], '未走査', name, name)
            continue
        explicit = False
        for task in source.get('pending', []):
            add(task.get('url'), '未走査', task.get('path', name), name)
            explicit = True
        for error in source.get('errors', []):
            task = error.get('task', {})
            detail = str(error.get('error') or '').strip()
            add(task.get('url'), '取得失敗' + (f'（{detail}）' if detail else ''),
                task.get('path', name), name)
            explicit = True
        # The collector cannot certify public Drive pagination. Show its root only
        # when it has no more precise unresolved folder to point to.
        if name != 'ku1025' and source.get('drive_listing_complete') is not True and not explicit:
            add(roots[name], '一覧の全件取得は未確認', name, name)
    for candidate in report.get('candidates', []):
        if candidate.get('previewError') or candidate.get('materialTypes') == ['未確認']:
            sources = candidate.get('sources', [])
            paths = candidate.get('paths', [])
            source = sources[0] if sources else ''
            path = paths[0] if paths else candidate.get('name', candidate.get('url', ''))
            reason = 'プレビューを確認できず' if candidate.get('previewError') else '内容未確認'
            add(candidate.get('url'), reason, path, source)

    # If a folder itself is unresolved, its descendants add no useful location.
    ordered = sorted(entries.values(), key=lambda item: (item['source'], item['path'].count('/'), item['path']))
    kept = []
    for item in ordered:
        if any(parent['source'] == item['source'] and parent['path'] != item['path']
               and item['path'].startswith(parent['path'].rstrip('/') + '/') for parent in kept):
            continue
        kept.append(item)
    return [{'url': item['url'], 'path': item['path'], 'source': item['source'],
             'reason': ' / '.join(item['reasons'])} for item in kept]


def filename_results(report):
    candidates = [candidate for candidate in report.get('candidates', []) if candidate['filenameMatch']['courseMatched']]
    sources = report.get('coverage', [])
    incomplete = len({s['source'] for s in sources}) != 4 or any(
        not s.get('pages') or s.get('pending') or s.get('errors')
        or (s['source'] != 'ku1025' and s.get('drive_listing_complete') is not True) for s in sources)
    results = {}
    for key in CONDITIONS:
        if any(key in c['filenameMatch']['groups'] for c in candidates):
            results[key] = 'あり'
        elif not report.get('teacher') or incomplete or any(
                c['filenameMatch']['teacherRelation'] == 'unknown'
                or (key != 'differentTeacher' and c['filenameMatch']['teacherRelation'] == 'same' and c['filenameMatch']['year'] is None)
                for c in candidates):
            results[key] = '未確認'
        else:
            results[key] = '確認範囲では未発見'
    return results


def snapshot(folder):
    report = load_report(folder)
    course = report.get('course', folder.name.partition(']')[2])
    year_in_folder = re.search(r'\d{4}', folder.name)
    year = report.get('academicYear', int(year_in_folder[0]) if year_in_folder else datetime.now().year)
    candidates = []
    for raw in report.get('candidates', []):
        candidate = dict(raw)
        verified = candidate.get('verification', {})
        if 'materialTypes' not in candidate and verified.get('isExam') and verified.get('courseConfirmed') and verified.get('evidence'):
            candidate.update(materialTypes=['問題'], evidence=verified['evidence'])
        candidates.append(normalize_candidate(candidate, course, report.get('teacher', ''), year, report.get('aliases', [])))
    report = {**report, 'schema': 2, 'candidates': candidates,
              'coverage': [{k: v for k, v in source.items() if k != 'conditions'} for source in report.get('coverage', [])]}
    report.pop('inferredTeacher', None)
    report['filenameResults'] = filename_results(report)
    report['unscanned'] = unscanned_urls(report)
    report['hasPastPaper'] = any(exam_confirmed(candidate) for candidate in candidates)
    report.pop('localCheckedAt', None)
    return report


def public_file(path):
    return {'name': path.name, 'path': path.relative_to(ROOT).as_posix(),
            'url': quote(path.relative_to(ROOT).as_posix(), safe='/'), 'bytes': path.stat().st_size}


def resources(folder, category):
    pattern = r'武器|weapons' if category == 'weapons' else r'演習|練習問題|対応問題|課題|practice|exercise|kadai'
    extensions = {'.html', '.htm', '.pdf', '.md', '.txt', '.py', '.png', '.jpg', '.jpeg'}
    # Explicit registrations supplement filename-based discovery without renaming sources.
    registry = folder / 'study/resources.json'
    registered = set()
    notes = {}
    if registry.is_file():
        data = json.loads(registry.read_text(encoding='utf-8'))
        registered = set(data.get(category, []))
        notes = data.get('notes', {}) if category == 'practice' else {}
    result = [public_file(path) for path in sorted(folder.rglob('*'))
            if path.is_file() and path.suffix.lower() in extensions
            and path.resolve().is_relative_to(folder.resolve())
            and not any(part.startswith('.') for part in path.relative_to(folder).parts)
            and (path.relative_to(folder).as_posix() in registered
                 or re.search(pattern, path.relative_to(folder).as_posix(), re.I))]
    for item in result:
        note = notes.get(Path(item['path']).relative_to(folder.relative_to(ROOT)).as_posix())
        if isinstance(note, str):
            path = folder / note
            if path.is_file() and path.suffix.lower() in {'.html', '.htm'} and path.resolve().is_relative_to(folder.resolve()):
                item['noteUrl'] = public_file(path)['url']
    return result


def from_listing(result, previous=None):
    previous = previous or {}
    old = {candidate_key(c.get('url')): c for c in previous.get('candidates', [])}
    candidates = {}
    for item in result.get('candidates', []):
        identity = candidate_key(item['url'])
        if identity not in candidates:
            known = old.get(identity, {})
            kept = {key: known[key] for key in ['materialTypes', 'evidence', 'previewError'] if key in known}
            candidates[identity] = {**item, **kept, 'sources': [], 'paths': []}
        entry = candidates[identity]
        if item['source'] not in entry['sources']: entry['sources'].append(item['source'])
        if item['path'] not in entry['paths']: entry['paths'].append(item['path'])
    return {'schema': 2, 'course': result['course'], 'teacher': result.get('teacher', ''),
            'academicYear': result['academic_year'], 'previousYear': result['previous_year'],
            'aliases': result.get('listing_terms', [result['course']])[1:],
            'execution': {'status': 'partial', 'stage': '資料の種類を確認中',
                          'startedAt': result['started_at'], 'updatedAt': result['updated_at']},
            'coverage': result.get('coverage', []),
            'candidates': [normalize_candidate(c, result['course'], result.get('teacher', ''), result['academic_year']) for c in candidates.values()]}


def save_markdown(folder, report):
    labels = ['同名教科・同名教員・前年度', '同名教科・同名教員・前年度よりも前', '同名教科・違う名前の教員']
    lines = [f"# {report.get('course', '')} 資料リンク", '']
    for key, label in zip(CONDITIONS, labels): lines.append(f"- {label}：{report['filenameResults'][key]}")
    lines += ['', '| タイトル名 | 資料の種類 | URL |', '|---|---|---|']
    for candidate in report['candidates']:
        url = candidate['url']
        if urlsplit(url).hostname != 'drive.google.com': continue
        name = (candidate.get('name') or candidate.get('title') or candidate.get('subjectName') or '').replace('|', '\\|').replace('\n', ' ')
        types = ' '.join(f'`{kind}`' for kind in candidate['materialTypes'])
        lines.append(f'| {name} | {types} | [Driveで開く]({url}) |')
    if report['unscanned']:
        lines += ['', '## 走査できなかった領域', '']
        for item in report['unscanned']:
            parts = [part for part in item.get('path', item['url']).split('/') if part]
            source = item.get('source')
            if source in {'kuinfo2020', 'past-exam-drive'}:
                if parts and parts[0] == source:
                    parts = parts[1:]
                path = f"Google Drive（検索元: {source}）" + (' / ' + ' / '.join(parts) if parts else ' / 検索元フォルダ')
            else:
                path = ' / '.join(parts)
            lines.append(f"- `{path}`：{item['reason']} — {item['url']} ([Driveで開く]({item['url']}))")
    (folder / 'study/past_exam_search.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
