"""既存LIFEサーバーからローカルDRFの閲覧APIへ橋渡しする。"""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def proxy_accounting(handler):
  port = int(os.environ.get('LIFE_ACCOUNTING_API_PORT', '8766'))
  request = Request(f'http://127.0.0.1:{port}'+handler.path, headers={'Accept': 'application/json'})
  try:
    with urlopen(request, timeout=30) as response:
      handler.respond(json.loads(response.read()), response.status)
  except HTTPError as error:
    handler.respond({'error': '家計APIのリクエストを確認してください。'}, error.code)
  except (URLError, TimeoutError, ValueError, OSError):
    handler.respond({'error': '家計バックエンドに接続できません。accounting/run.pyで起動してください。'}, 503)
