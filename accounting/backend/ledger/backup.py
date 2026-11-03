"""SQLiteのバックアップ・整合性検査・復元。"""
from contextlib import contextmanager
from datetime import datetime
import fcntl
import os
from pathlib import Path
import sqlite3
import tempfile
from django.conf import settings


@contextmanager
def writer_lock():
  lock_path = Path(settings.DB_PATH).with_suffix('.writer.lock')
  lock_path.parent.mkdir(parents=True, exist_ok=True)
  with lock_path.open('a') as handle:
    fcntl.flock(handle, fcntl.LOCK_EX)
    try:
      yield
    finally:
      fcntl.flock(handle, fcntl.LOCK_UN)


def check_database(path):
  with sqlite3.connect(f'file:{Path(path).resolve()}?mode=ro', uri=True) as db:
    if db.execute('PRAGMA integrity_check').fetchall() != [('ok',)]:
      raise ValueError('DBの整合性検査に失敗しました。')
    if db.execute('PRAGMA foreign_key_check').fetchone():
      raise ValueError('DBの参照関係に不整合があります。')
    names = {row[0] for row in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if not {'transactions', 'raw_records', 'decisions', 'django_migrations'} <= names:
      raise ValueError('家計DBではありません。')


def backup_database(label='before-update', retain=10):
  folder = settings.BASE_DIR / 'backups'
  folder.mkdir(parents=True, exist_ok=True)
  stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
  target = folder / f'accounting_{stamp}_{label}.sqlite3'
  temp = target.with_suffix('.partial')
  try:
    with sqlite3.connect(f'file:{Path(settings.DB_PATH).resolve()}?mode=ro', uri=True) as source:
      with sqlite3.connect(temp) as destination:
        source.backup(destination)
    check_database(temp)
    os.chmod(temp, 0o600)
    temp.replace(target)
    backups = sorted(folder.glob('accounting_*.sqlite3'))
    for old in backups[:-retain]:
      old.unlink()
  finally:
    if temp.exists():
      temp.unlink()
  return target


def restore_database(path):
  # 呼び出し側でサーバー停止の明示指定とwriter_lockを要求する。
  path = Path(path).resolve()
  check_database(path)
  runtimes = [Path(settings.DB_PATH).with_suffix('.server.json'), settings.BASE_DIR / 'data/server.json']
  for runtime in runtimes:
    if not runtime.exists():
      continue
    import json
    for pid in json.loads(runtime.read_text()).get('children', []):
      try:
        os.kill(pid, 0)
      except ProcessLookupError:
        continue
      raise ValueError('家計サーバーを停止してから復元してください。')
  with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as db:
    saved = db.execute('SELECT app, name FROM django_migrations ORDER BY app, name').fetchall()
  with sqlite3.connect(settings.DB_PATH) as db:
    current = db.execute('SELECT app, name FROM django_migrations ORDER BY app, name').fetchall()
  if saved != current:
    raise ValueError('DB構造の版が異なります。対応するコードで復元してください。')
  descriptor, temp_name = tempfile.mkstemp(dir=Path(settings.DB_PATH).parent, suffix='.restore')
  os.close(descriptor)
  temp = Path(temp_name)
  try:
    with sqlite3.connect(f'file:{path}?mode=ro', uri=True) as source:
      with sqlite3.connect(temp) as destination:
        source.backup(destination)
    check_database(temp)
    backup_database('before-restore')
    os.chmod(temp, 0o600)
    temp.replace(settings.DB_PATH)
    for suffix in ['-wal', '-shm']:
      Path(str(settings.DB_PATH)+suffix).unlink(missing_ok=True)
  finally:
    temp.unlink(missing_ok=True)
