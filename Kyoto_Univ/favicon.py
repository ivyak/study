"""Keep the shared LIFE favicon on all public HTML pages, including local files."""
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parent
ICON = ROOT / 'ui/favicon.svg'


def sync_favicons():
    for path in ROOT.parent.rglob('*.html'):
        if path.is_relative_to(ROOT.parent / 'chrome_extensions'):
            continue  # Extension popups are packaged separately from LIFE pages.
        if any(part.startswith('.') for part in path.relative_to(ROOT.parent).parts):
            continue
        content = path.read_text(encoding='utf-8')
        if not re.search(r'<head\b[^>]*>', content, re.IGNORECASE):
            continue  # Shared HTML fragments have no document head.
        href = Path(os.path.relpath(ICON, path.parent)).as_posix()
        tag = f'<link rel="icon" type="image/svg+xml" href="{href}">'
        updated = re.sub(r'\s*<link\b(?=[^>]*\brel=[\"\'](?:shortcut )?icon[\"\'])[^>]*>', '', content, flags=re.IGNORECASE)
        updated = re.sub(r'(<head\b[^>]*>)', lambda match: match[0] + '\n' + tag, updated, count=1, flags=re.IGNORECASE)
        if updated != content:
            path.write_text(updated, encoding='utf-8')


if __name__ == '__main__':
    sync_favicons()
