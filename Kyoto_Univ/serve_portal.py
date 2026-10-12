#!/usr/bin/env python3
"""Serve LIFE locally and run the installed past-exam skill after a UI request."""
import argparse
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
from article_reports import article_records, update_read_status, update_bookmark
from lesson_progress import records as lesson_progress_records, update as update_lesson_progress
from urllib.parse import unquote, urlsplit

from past_exams import ROOT, SKILL, SOURCE_NAMES, MATERIAL_TYPES, from_listing, load_report, now, save_report, snapshot, save_markdown, normalize_candidate, candidate_key
from update_portal import course_records, build

TOKEN = secrets.token_urlsafe(32)
JOBS_LOCK = threading.Lock()
ACTIVE_JOBS = set()
def get_course(course_id):
    return next((course for course in course_records() if course['id'] == course_id), None)


def save_stage(folder, report, status, stage, error=None):
    report['execution'].update(status=status, stage=stage, updatedAt=now())
    if error:
        report['execution']['error'] = error
    else:
        report['execution'].pop('error', None)
    save_report(folder, report)


def review_prompt(course, folder, index, result):
    return f'''Use the kyoto-past-exams skill at {SKILL / 'SKILL.md'} and its sources reference.
Course: {course['name']}; teacher spelling in filenames: {result.get('teacher') or 'unknown'};
academic year: {result['academic_year']}.
Listing collection and filename matching are done. Read {index},
{folder / 'study/past_exam_candidates.json'} and {folder / 'study/past_exam_search.json'}.
DO NOT infer course, teacher or year from document contents, folder names or dates:
the server computes ONLY the three filename groups specified by the skill.
Your task is to view each candidate in the public Drive preview and classify its
CONTENT as 問題, 講義資料, 解答, 演習問題, or 未確認. Mixed documents may have multiple
badges. Record brief content evidence. A filename alone is not type evidence.
DO NOT download or save PDFs/images/other source materials, even into /tmp.
DO NOT use download/uc/export endpoints. Use Drive view/preview links only.
If preview is unavailable, keep 未確認 and record previewError. Preserve every
candidate, all source paths and URLs, and previous content evidence.
Return JSON using the provided schema. status is partial if any type is 未確認 or
any listing/preview failed. Preserve pending URLs and errors for all four sources.
Do not write any files except your schema output: the server writes the compact
report with 教科名 / 資料の種類 / URL and unscanned URLs at the bottom.
Do not change any portal, code, original material, or another course.
Do not ask for credentials or bypass approval. If automatic review rejects an
action, include its action and reason in error.
'''


def validate_review(review, year=None, teacher=''):
    if review.get('status') not in {'complete', 'partial'}:
        raise ValueError('検索結果の完了状態が不正です')
    if len(review.get('coverage', [])) != 4 or {source.get('source') for source in review['coverage']} != set(SOURCE_NAMES):
        raise ValueError('検索結果に4ソースの確認状況がありません')
    for candidate in review.get('candidates', []):
        url = urlsplit(candidate.get('url', ''))
        if url.scheme != 'https' or url.hostname != 'drive.google.com' or not (url.path.startswith('/file/d/') or url.path.startswith('/drive/folders/')):
            raise ValueError('Driveの閲覧リンクが不正です')
        types = candidate.get('materialTypes', [])
        if not types or not all(kind in MATERIAL_TYPES for kind in types) or ('未確認' in types and len(types) != 1):
            raise ValueError('資料の種類が不正です')
        if types != ['未確認'] and not candidate.get('evidence', '').strip():
            raise ValueError('資料の種類の内容確認根拠がありません')
        if any(key in candidate for key in ['localPath', 'sha256', 'verification']):
            raise ValueError('新しい検索結果はDriveリンクのみです')


def run_search(course, teacher, year):
    folder = ROOT / course['folder']
    study = folder / 'study'
    study.mkdir(exist_ok=True)
    index = study / 'past_exam_index.json'
    result_path = study / 'past_exam_candidates.json'
    log_path = study / 'past_exam_execution.log'
    previous = snapshot(folder)
    report = {**previous, 'schema': 2, 'course': course['name'], 'teacher': teacher,
              'academicYear': year, 'previousYear': year - 1,
              'execution': {'status': 'running', 'stage': '4ソースの一覧を検索中', 'startedAt': now(), 'updatedAt': now()}}
    save_report(folder, report)
    try:
        with log_path.open('w', encoding='utf-8') as log:
            command = [sys.executable, str(SKILL / 'scripts/search.py')]
            subprocess.run(command + ['collect', '--course', course['name'], '--teacher', teacher, '--out', str(index)],
                           cwd=folder, stdout=log, stderr=log, check=True, timeout=3600)
            while True:
                collected = json.loads(index.read_text(encoding='utf-8'))
                sources = collected.get('sources', [])
                remaining = sum(len(source.get('pending', [])) for source in sources)
                if not remaining:
                    break
                visited_before = {url for source in sources for url in source.get('visited', [])}
                save_stage(folder, report, 'running', f'未調査の一覧を継続取得中（残り{remaining}件）')
                subprocess.run(command + ['collect', '--course', course['name'], '--teacher', teacher,
                                           '--out', str(index), '--resume'],
                               cwd=folder, stdout=log, stderr=log, check=True, timeout=3600)
                updated = json.loads(index.read_text(encoding='utf-8'))
                visited_after = {url for source in updated.get('sources', []) for url in source.get('visited', [])}
                if not visited_after - visited_before:
                    break  # Failed access stays explicit; do not retry forever.
            result = subprocess.run(command + ['search', '--course', course['name'], '--index', str(index),
                                              '--teacher', teacher, '--academic-year', str(year)],
                                    cwd=folder, capture_output=True, text=True, check=True, timeout=60)
            result = json.loads(result.stdout)
            result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            report = from_listing(result, previous)
            save_stage(folder, report, 'running', 'Driveプレビューで資料の種類を確認中')
            executable = shutil.which('codex')
            if not executable:
                save_stage(folder, report, 'partial', '一覧検索済み・内容確認待ち', '内容を確認するCodex CLIが見つかりません。')
                return
            output = study / 'past_exam_review.json'
            # No approval bypass: network/write approval is handled by Codex's automatic review.
            subprocess.run([executable, 'exec', '--sandbox', 'workspace-write', '--approve-for-me',
                            '--ephemeral', '-C', str(folder), '--output-schema', str(ROOT / 'ui/past-exam-review.schema.json'),
                            '-o', str(output), '-'], input=review_prompt(course, folder, index, result),
                           text=True, stdout=log, stderr=log, check=True, timeout=3600)
            review = json.loads(output.read_text(encoding='utf-8'))
            # Keep actual collection coverage even if the content reviewer resumes it.
            refreshed = subprocess.run(command + ['search', '--course', course['name'], '--index', str(index),
                                                 '--teacher', teacher, '--academic-year', str(year)],
                                       cwd=folder, capture_output=True, text=True, check=True, timeout=60)
            raw_coverage = {source['source']: source for source in json.loads(refreshed.stdout)['coverage']}
            for source in review.get('coverage', []):
                source.update(raw_coverage.get(source.get('source'), {}))
            validate_review(review, year, teacher)
            if any(source.get('pending') or source.get('errors') for source in review['coverage']):
                review['status'] = 'partial'
            # Keep canonical filenames and links from the collected index.
            reviewed = {candidate_key(c['url']): c for c in review['candidates']}
            for candidate in report['candidates']:
                info = reviewed.get(candidate_key(candidate['url']))
                if info:
                    for key in ['materialTypes', 'evidence', 'previewError']:
                        candidate[key] = info.get(key)
            report['coverage'] = review['coverage']
            if any(c.get('materialTypes') == ['未確認'] or c.get('previewError') for c in report['candidates']):
                review['status'] = 'partial'
            save_stage(folder, report, review['status'], '検索・内容確認完了' if review['status'] == 'complete' else '検索済み・未確認項目あり', review.get('error'))
    except (subprocess.SubprocessError, OSError, ValueError) as error:
        status = 'partial' if result_path.is_file() else 'failed'
        save_stage(folder, report, status, '検索が完了していません', f'{type(error).__name__}: {error}')
    finally:
        with JOBS_LOCK:
            ACTIVE_JOBS.discard(course['id'])
        latest = snapshot(folder)
        save_report(folder, latest)
        save_markdown(folder, latest)
        build()


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def allowed(self):
        host = self.headers.get('Host', '')
        origin = self.headers.get('Origin')
        if host not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
            return False
        if origin in {None, 'null'}:
            return True
        parsed = urlsplit(origin)
        return (parsed.scheme == 'http' and parsed.hostname in {'127.0.0.1', 'localhost'}
                and not parsed.username and not parsed.password and not parsed.path
                and not parsed.query and not parsed.fragment)

    def end_headers(self):
        if self.allowed() and self.headers.get('Origin'):
            self.send_header('Access-Control-Allow-Origin', self.headers['Origin'])
            self.send_header('Vary', 'Origin')
        super().end_headers()

    def respond(self, value, status=200):
        data = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        if not self.allowed():
            self.respond({'error': 'この接続元は利用できません'}, 403)
            return
        self.send_response(204)
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, X-LIFE-Token')
        self.end_headers()

    def do_GET(self):
        if not self.allowed():
            self.respond({'error': 'この接続元は利用できません'}, 403)
            return
        path = unquote(urlsplit(self.path).path)
        if path == '/api/runtime':
            self.respond({'token': TOKEN, 'skillAvailable': (SKILL / 'scripts/search.py').is_file(),
                          'reviewAvailable': bool(shutil.which('codex'))})
        elif path == '/api/articles':
            self.respond({'articles': article_records()})
        elif path == '/api/lesson-progress':
            self.respond({'progress': lesson_progress_records()})
        elif path.startswith('/api/exams/'):
            course = get_course(path[len('/api/exams/'):])
            self.respond(snapshot(ROOT / course['folder']) if course else {'error': '教科が見つかりません'}, 200 if course else 404)
        elif path.startswith('/api/'):
            self.respond({'error': 'ページが見つかりません'}, 404)
        else:
            resolved = Path(self.translate_path(self.path)).resolve()
            if not resolved.is_relative_to(ROOT) or any(part.startswith('.') for part in resolved.relative_to(ROOT).parts):
                self.send_error(403)
                return
            super().do_GET()

    def do_POST(self):
        if not self.allowed() or self.headers.get('X-LIFE-Token') != TOKEN:
            self.respond({'error': 'ローカルの接続を確認してください'}, 403)
            return
        path = unquote(urlsplit(self.path).path)
        if path == '/api/lesson-progress':
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('学習ステータスが不正です')
                payload = json.loads(self.rfile.read(length))
                with JOBS_LOCK:
                    result = update_lesson_progress(payload.get('path'), payload.get('status'), payload.get('bookmark'))
                self.respond({'progress': result})
            except (ValueError, TypeError, AttributeError) as error:
                self.respond({'error': str(error)}, 400)
            return
        if path.startswith('/api/articles/') and path.endswith('/bookmark'):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('しおりが不正です')
                payload = json.loads(self.rfile.read(length))
                with JOBS_LOCK:
                    report = update_bookmark(path[len('/api/articles/'):-len('/bookmark')], payload.get('slideIndex'))
                    build()
                self.respond({'bookmarkIndex': report['bookmarkIndex'], 'bookmarkUpdatedAt': report['bookmarkUpdatedAt']})
            except FileNotFoundError:
                self.respond({'error': '記事が見つかりません'}, 404)
            except (ValueError, TypeError, AttributeError) as error:
                self.respond({'error': str(error)}, 400)
            return
        if path.startswith('/api/articles/') and path.endswith('/read-status'):
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length <= 4096:
                    raise ValueError('ステータスが不正です')
                payload = json.loads(self.rfile.read(length))
                with JOBS_LOCK:
                    report = update_read_status(path[len('/api/articles/'):-len('/read-status')], payload.get('readStatus'))
                    build()
                self.respond({'readStatus': report['readStatus'], 'readStatusUpdatedAt': report['readStatusUpdatedAt'], 'bookmarkIndex': report.get('bookmarkIndex'), 'bookmarkUpdatedAt': report.get('bookmarkUpdatedAt', '')})
            except FileNotFoundError:
                self.respond({'error': '記事が見つかりません'}, 404)
            except (ValueError, TypeError, AttributeError) as error:
                self.respond({'error': str(error)}, 400)
            return
        if not path.startswith('/api/exams/'):
            self.respond({'error': 'ページが見つかりません'}, 404)
            return
        course = get_course(path[len('/api/exams/'):])
        if not course:
            self.respond({'error': '教科が見つかりません'}, 404)
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 4096:
                raise ValueError('検索条件が不正です')
            payload = json.loads(self.rfile.read(length))
            teacher = payload.get('teacher', '').strip()
            year = int(payload.get('academicYear', course['term'][:4]))
            if not teacher:
                raise ValueError('教員名を入力してください。空欄のまま検索できません。')
            if len(teacher) > 100 or not 1900 <= year <= 2100:
                raise ValueError('教員名または授業年度を確認してください')
        except (ValueError, TypeError, AttributeError) as error:
            self.respond({'error': str(error)}, 400)
            return
        with JOBS_LOCK:
            if ACTIVE_JOBS:
                self.respond({'error': '別の検索を実行中です。完了後に実行してください'}, 409)
                return
            ACTIVE_JOBS.add(course['id'])
            folder = ROOT / course['folder']
            report = load_report(folder)
            report.update(course=course['name'], teacher=teacher, academicYear=year, previousYear=year - 1,
                          execution={'status': 'running', 'stage': '検索を開始しています', 'startedAt': now(), 'updatedAt': now()})
            save_report(folder, report)
        threading.Thread(target=run_search, args=(course, teacher, year), daemon=True).start()
        self.respond({'status': 'running'}, 202)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    # A killed server cannot leave a search marked as running forever.
    for course in course_records():
        folder = ROOT / course['folder']
        report = load_report(folder)
        if report.get('execution', {}).get('status') == 'running':
            save_stage(folder, report, 'partial', '前回の検索が中断されました')
    build()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'LIFE: http://127.0.0.1:{args.port}/index.html', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
