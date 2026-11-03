#!/usr/bin/env python3
"""LIFEと家計用DRFをまとめて起動する。"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import socket
import subprocess
import time
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent


def main():
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument('--port', type=int, default=8765)
  parser.add_argument('--backend-port', type=int, default=8766)
  args = parser.parse_args()
  python = ROOT / '.venv/bin/python'
  if not python.exists():
    raise SystemExit('先にaccounting/README.mdに従って仮想環境を準備してください。')
  if args.port == args.backend_port:
    raise SystemExit('LIFEとDRFには異なるポートを指定してください。')
  for port in [args.port, args.backend_port]:
    try:
      with socket.socket() as probe:
        # 停止直後の接続待機状態を、稼働中サーバーと取り違えない。
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', port))
    except PermissionError:
      raise SystemExit(f'ローカルポート{port}を開く権限がありません。実行環境のネットワーク許可を確認してください。')
    except OSError:
      raise SystemExit(f'ポート{port}は使用中です。既存サーバーを止めるか、--portと--backend-portを指定してください。')
  database = Path(os.environ.get('LIFE_ACCOUNTING_DB', ROOT / 'data/accounting.sqlite3')).resolve()
  database.parent.mkdir(parents=True, exist_ok=True)
  server_lock = database.with_suffix('.server.lock').open('a')
  try:
    fcntl.flock(server_lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
  except BlockingIOError:
    raise SystemExit('同じ家計DBを使うサーバーが起動中です。')
  manage = [str(python), str(ROOT / 'backend/manage.py')]
  subprocess.run(manage+['accounting', 'migrate-safe'], check=True)
  database.chmod(0o600)
  children = []
  runtime = database.with_suffix('.server.json')
  try:
    backend = subprocess.Popen([str(python), str(ROOT / 'backend/manage.py'), 'runserver', f'127.0.0.1:{args.backend_port}', '--noreload'])
    children.append(backend)
    for attempt in range(100):
      if backend.poll() is not None:
        raise RuntimeError('家計バックエンドの起動に失敗しました。')
      try:
        with urlopen(f'http://127.0.0.1:{args.backend_port}/api/accounting/status', timeout=1):
          break
      except OSError:
        time.sleep(.1)
    else:
      raise RuntimeError('家計バックエンドの起動を確認できません。')
    environment = {**os.environ, 'LIFE_ACCOUNTING_API_PORT': str(args.backend_port)}
    portal = subprocess.Popen([str(python), str(ROOT.parent / 'Kyoto_Univ/serve_portal.py'), '--port', str(args.port), '--skip-build'], env=environment)
    children.append(portal)
    runtime.write_text(json.dumps({'pid': os.getpid(), 'children': [p.pid for p in children], 'port': args.port, 'backendPort': args.backend_port}))
    print(f'LIFE＋家計DB: http://127.0.0.1:{args.port}/index.html#section=%E5%AE%B6%E8%A8%88', flush=True)
    while all(child.poll() is None for child in children):
      time.sleep(.5)
  except KeyboardInterrupt:
    pass
  finally:
    for child in children:
      if child.poll() is None:
        child.terminate()
    for child in children:
      try:
        child.wait(timeout=5)
      except subprocess.TimeoutExpired:
        child.kill()
    runtime.unlink(missing_ok=True)
    server_lock.close()


if __name__ == '__main__':
  main()
