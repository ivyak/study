"""Persist per-document study status and bookmarks for LIFE lesson pages."""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FILE = ROOT / 'lesson_progress.json'


def records():
    try:
        value = json.loads(FILE.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) else {}
    except FileNotFoundError:
        return {}


def update(path, status, bookmark):
    if not isinstance(path, str) or len(path) > 500 or path.startswith('/') or '\\' in path:
        raise ValueError('資料のパスが不正です')
    resolved = (ROOT / path).resolve()
    if not resolved.is_relative_to(ROOT) or not resolved.is_file() or resolved.suffix.lower() not in {'.html', '.htm'}:
        raise ValueError('資料が見つかりません')
    if any(part.startswith('.') for part in resolved.relative_to(ROOT).parts):
        raise ValueError('資料のパスが不正です')
    if 'data-life-page="document"' not in resolved.read_text(encoding='utf-8', errors='replace'):
        raise ValueError('授業資料ではありません')
    if status not in {'unread', 'reading', 'read'} or bookmark is not None and (type(bookmark) is not int or not 0 <= bookmark < 1000):
        raise ValueError('ステータスまたはしおりが不正です')
    value = {'status': status, 'bookmark': bookmark, 'updatedAt': datetime.now(timezone.utc).isoformat()}
    data = records()
    data[path] = value
    FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return value
