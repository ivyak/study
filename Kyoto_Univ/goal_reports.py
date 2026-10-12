"""Render the small Markdown reports kept in goal_management without external assets."""
from html import escape
from pathlib import Path
from urllib.parse import urlsplit
from datetime import date
import re

REPORTS = Path(__file__).resolve().parent.parent / 'goal_management'


def inline(text):
    """Escape all source HTML and allow only web links."""
    parts, offset = [], 0
    for match in re.finditer(r'\[([^\]\n]+)\]\(([^\s)]+)\)', text):
        parts.append(escape(text[offset:match.start()]))
        label, url = match.groups()
        if urlsplit(url).scheme in ('https', 'http'):
            parts.append(f'<a href="{escape(url, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(label)}</a>')
        else:
            parts.append(escape(label))
        offset = match.end()
    parts.append(escape(text[offset:]))
    return ''.join(parts)


def render(markdown):
    lines = markdown.splitlines()
    output, index = [], 0
    while index < len(lines):
        line = lines[index].strip()
        if not line or line.startswith('# '):
            index += 1
            continue
        if line.startswith('|') and index + 1 < len(lines) and re.fullmatch(r'[\s|:\-]+', lines[index + 1]):
            cells = lambda row: [cell.strip() for cell in row.strip().strip('|').split('|')]
            headers = cells(line)
            output.append('<table><thead><tr>' + ''.join(f'<th scope="col">{inline(cell)}</th>' for cell in headers) + '</tr></thead><tbody>')
            index += 2
            while index < len(lines) and lines[index].strip().startswith('|'):
                output.append('<tr>' + ''.join(f'<td>{inline(cell)}</td>' for cell in cells(lines[index])) + '</tr>')
                index += 1
            output.append('</tbody></table>')
            continue
        if line.startswith('## '):
            output.append(f'<h2>{inline(line[3:])}</h2>')
        elif line.startswith('- '):
            output.append('<ul>')
            while index < len(lines) and lines[index].strip().startswith('- '):
                output.append(f'<li>{inline(lines[index].strip()[2:])}</li>')
                index += 1
            output.append('</ul>')
            continue
        else:
            paragraph = [line]
            while index + 1 < len(lines) and lines[index + 1].strip() and not lines[index + 1].strip().startswith(('#', '|', '- ')):
                index += 1
                paragraph.append(lines[index].strip())
            output.append(f'<p>{inline(" ".join(paragraph))}</p>')
        index += 1
    return ''.join(output)


def goal_records():
    records = []
    for path in sorted(REPORTS.glob('????-??-??.md'), reverse=True):
        try:
            date.fromisoformat(path.stem)
        except ValueError:
            continue
        records.append({'date': path.stem, 'html': render(path.read_text(encoding='utf-8'))})
    return records
