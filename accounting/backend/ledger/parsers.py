"""CSVの列変換だけを行う。照合や用途の推測はしない。"""
from collections import Counter
from datetime import datetime
from decimal import Decimal, InvalidOperation
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import unicodedata

VERSION = '1.0'
NAMES = {
  'Sumitomo_Mitsui_Banking_Corporation': '三井住友銀行',
  'THE_KYOTO_SHINKIN_BANK': '京都信用金庫',
  'RAKUTEN_BANK_LTD': '楽天銀行',
  'JAPAN_POST_BANK': 'ゆうちょ銀行',
  'PayPay_Corporation': 'PayPay残高',
  'Super_Urban_Intelligent_Card': 'Suica',
  'Vpass': '三井住友カード未払金',
  'Rakuten_Card': '楽天カード未払金',
  'zaim': '現金',
  'univ_coop': '大学生協電子マネー',
}
COOP_HEADERS = {
  'money': ['ご利用日', '返品日.取り消し日', 'マネー', 'ご利用店舗', 'ステータス', 'ご利用金額', 'ポイント（内）', 'ポイント（付与）'],
  'items': ['ご利用日時', 'ご利用店舗', '商品名', '個数', 'ご利用単価'],
}
HEADERS = {
  'Sumitomo_Mitsui_Banking_Corporation': ['年月日', 'お引出し', 'お預入れ', 'お取り扱い内容', '残高', 'メモ', 'ラベル'],
  'THE_KYOTO_SHINKIN_BANK': ['お取引日', 'お取引内容', 'お支払金額', 'お預り金額', '残高'],
  'RAKUTEN_BANK_LTD': ['取引日', '入出金(円)', '取引後残高(円)', '入出金内容'],
  'JAPAN_POST_BANK': ['取引日', '入出金明細ＩＤ', '受入金額（円）', '払出金額（円）', '詳細１', '詳細２', '現在（貸付）高', ''],
  'PayPay_Corporation': ['取引日', '出金金額（円）', '入金金額（円）', '海外出金金額', '通貨', '変換レート（円）', '利用国', '取引内容', '取引先', '取引方法', '支払い区分', '利用者', '取引番号'],
  'Super_Urban_Intelligent_Card': ['月日', '種別', '利用場所', '種別', '利用場所', '残高', '入金・利用額'],
  'zaim': ['日付', '方法', 'カテゴリ', 'カテゴリの内訳', '支払元', '入金先', '品目', 'メモ', 'お店', '通貨', '収入', '支出', '振替', '残高調整', '通貨変換前の金額', '集計の設定'],
}


def normalize(value):
  return unicodedata.normalize('NFKC', str(value)).strip()


def money(value, nullable=False):
  value = normalize(value).replace(',', '').replace('円', '').replace('¥', '').replace('\\', '')
  if value in {'', '-', '―'}:
    return None if nullable else Decimal(0)
  try:
    result = Decimal(value)
  except InvalidOperation as error:
    raise ValueError('金額の形式が不正です。') from error
  if not result.is_finite() or result != result.quantize(Decimal('0.01')) or abs(result) >= 10**16:
    raise ValueError('金額の精度・範囲が不正です。')
  return result


def day(value):
  value = normalize(value).split(' ')[0]
  for fmt in ['%Y/%m/%d', '%Y-%m-%d', '%Y%m%d']:
    try:
      return datetime.strptime(value, fmt).date()
    except ValueError:
      pass
  raise ValueError('日付の形式が不正です。')


def signed_fields(value):
  return {'amount': abs(value), 'direction': 'in' if value > 0 else 'out' if value < 0 else 'unknown'}


def billed_amount(source, values, columns):
  if source == 'Vpass':
    if len(values) == 7:
      return money(values[5])
    return money(values[7]) if re.fullmatch(r'-?[\d,]+', normalize(values[7])) else money(values[6])
  if '当月請求額' in columns:
    return money(values[columns.index('当月請求額')])
  column = next(i for i, name in enumerate(columns) if re.fullmatch(r'\d+月支払金額', name))
  return money(values[column])


def parse_file(path, root):
  path, root = Path(path), Path(root)
  source = path.parent.name
  if source not in NAMES:
    raise ValueError(f'未対応のCSVフォルダです: {source}')
  raw = path.read_bytes()
  try:
    text, encoding = raw.decode('utf-8-sig'), 'utf-8-sig'
  except UnicodeDecodeError:
    text, encoding = raw.decode('cp932'), 'cp932'
  reader = csv.reader(io.StringIO(text, newline=''), strict=True)
  rows = []
  while True:
    start = reader.line_num + 1
    try:
      values = next(reader)
    except StopIteration:
      break
    rows.append((start, reader.line_num, values))
  if not rows:
    raise ValueError(f'空のCSVです: {path.name}')
  header = rows[0][2]
  coop_format = next((kind for kind, expected in COOP_HEADERS.items() if header == expected), None)
  if source == 'univ_coop' and not coop_format:
    raise ValueError(f'生協CSVの列構成が変わっています: {path.name}')
  if source in HEADERS and header != HEADERS[source]:
    raise ValueError(f'列構成が変わっています: {source}/{path.name}')
  if source == 'Rakuten_Card' and (header[:7] != ['利用日', '利用店名・商品名', '利用者', '支払方法', '利用金額', '手数料/利息', '支払総額'] or len(header) not in {10, 11, 12}):
    raise ValueError(f'楽天カードの列構成が変わっています: {path.name}')
  billing = ''
  scope = source
  if source == 'univ_coop':
    scope += ':'+coop_format
  if source in {'Vpass', 'Rakuten_Card'}:
    match = re.search(r'20\d{4}', path.stem)
    if not match:
      raise ValueError('カードの請求月をファイル名から取得できません。')
    billing = match[0][:4]+'-'+match[0][4:]
    scope += ':'+match[0]
  result, counts, year = [], Counter(), None
  for line_start, line_end, row in rows:
    payload = json.dumps([scope, row], ensure_ascii=False, separators=(',', ':'))
    fingerprint = hashlib.sha256(payload.encode()).hexdigest()
    counts[fingerprint] += 1
    record = {'source': source, 'dedupe_scope': scope,
      'dedupe_key': f'raw-{fingerprint}-{counts[fingerprint]}',
      'occurrence_number': counts[fingerprint],
      'raw_data': {'columns': header if source != 'Vpass' else [], 'values': row},
      'account_hint': NAMES[source], 'billing_month': billing}
    parsed = {}
    try:
      if source == 'Super_Urban_Intelligent_Card':
        if row and re.fullmatch(r'# (\d{4})年', row[0]):
          year = int(row[0][2:6])
        match = re.fullmatch(r'(\d{1,2})月(\d{1,2})日', row[0]) if row else None
        if match:
          if not year or len(row) != 7:
            raise ValueError('Suicaの年または列数を確認してください。')
          parsed = {'transaction_date': day(f'{year}-{match[1]}-{match[2]}'),
            **signed_fields(money(row[6])), 'memo': row[1], 'store': row[2],
            'counterparty_hint': row[4], 'balance': money(row[5], True)}
      elif source == 'Vpass':
        if row and re.match(r'^20\d{2}[/-]', row[0]):
          if len(row) not in {7, 13}:
            raise ValueError('Vpassの列数が変わっています。')
          value = money(row[6] if len(row) == 13 else row[2])
          parsed = {'transaction_date': day(row[0]), **signed_fields(-value), 'memo': row[1], 'store': row[1]}
      elif line_start != 1:
        if not row or not any(row):
          continue
        if len(row) != len(header):
          raise ValueError('列数がヘッダーと一致しません。')
        if source == 'Rakuten_Card' and not row[0] and normalize(row[1]).startswith('現地利用額') and not any(row[2:]):
          result.append({'record': record, 'line_start': line_start, 'line_end': line_end})
          continue
        parsed['transaction_date'] = day(row[0])
        if source == 'univ_coop':
          timestamp = datetime.strptime(normalize(row[0]), '%Y-%m-%d %H:%M:%S')
          parsed['transaction_date'] = timestamp.date()
          if coop_format == 'items':
            quantity = money(row[3])
            unit_price = money(row[4])
            if quantity <= 0 or quantity != int(quantity) or unit_price < 0:
              raise ValueError('商品個数または単価が不正です。')
            parsed.update(amount=quantity*unit_price, direction='detail', store=row[1], item_name=row[2], memo='商品内訳')
          else:
            if row[4] not in {'支払い完了', 'チャージ', 'ポイント'} or row[1]:
              raise ValueError('未知のステータスまたは返品があります。意味を確認してください。')
            value, points_used, points_awarded = money(row[5]), money(row[6]), money(row[7])
            if min(value, points_used, points_awarded) < 0 or (row[4] == '支払い完了' and points_used > value):
              raise ValueError('利用額またはポイント欄が不正です。')
            parsed.update(amount=value, direction={'支払い完了': 'out', 'チャージ': 'in', 'ポイント': 'unknown'}[row[4]],
              store=row[3], memo=row[4])
        elif source == 'Sumitomo_Mitsui_Banking_Corporation':
          if money(row[1]) and money(row[2]):
            raise ValueError('同じ行に出金と入金があります。')
          parsed.update(**signed_fields(money(row[2])-money(row[1])), memo=row[3], balance=money(row[4], True))
        elif source == 'THE_KYOTO_SHINKIN_BANK':
          if money(row[2]) and money(row[3]):
            raise ValueError('同じ行に出金と入金があります。')
          parsed.update(**signed_fields(money(row[3])-money(row[2])), memo=row[1], balance=money(row[4], True))
        elif source == 'RAKUTEN_BANK_LTD':
          parsed.update(**signed_fields(money(row[1])), memo=row[3], balance=money(row[2], True))
        elif source == 'JAPAN_POST_BANK':
          if money(row[2]) and money(row[3]):
            raise ValueError('同じ行に出金と入金があります。')
          parsed.update(**signed_fields(money(row[2])-money(row[3])), source_transaction_id=row[1], memo=row[4], balance=money(row[6], True))
        elif source == 'Rakuten_Card':
          parsed.update(**signed_fields(-money(row[4])), memo=row[1], store=row[1])
        elif source == 'PayPay_Corporation':
          if money(row[1]) and money(row[2]):
            raise ValueError('同じ行に出金と入金があります。')
          parsed.update(**signed_fields(money(row[2])-money(row[1])), memo=row[7], store=row[8], source_transaction_id=row[12])
        elif source == 'zaim':
          method = row[1]
          if method not in {'payment', 'income', 'transfer', 'balance'}:
            raise ValueError('Zaimの方法が未知の値です。')
          value = money(row[11] if method == 'payment' else row[10] if method == 'income' else row[12] if method == 'transfer' else row[13])
          parsed.update(amount=value, direction={'payment': 'out', 'income': 'in', 'transfer': 'transfer', 'balance': 'unknown'}[method],
            account_hint=row[4], counterparty_hint=row[5], item_name=row[6], memo=row[7], store=row[8],
            category_name=row[2], subcategory_name=row[3], currency=row[9] or 'JPY')
    except (ValueError, IndexError) as error:
      raise ValueError(f'{source}/{path.name}：{line_start}行目：{error}') from error
    record.update(parsed)
    result.append({'record': record, 'line_start': line_start, 'line_end': line_end})
  if source == 'Vpass':
    printed = [money(row[5]) for _, _, row in rows if len(row) == 7 and not any(row[:5]) and row[5]]
    if printed:
      total = sum((billed_amount(source, i['record']['raw_data']['values'], []) for i in result if i['record'].get('transaction_date')), Decimal(0))
      if len(printed) != 1 or total != printed[0]:
        raise ValueError(f'{path.name}の請求合計と明細合計が一致しません。')
  return {'source': source, 'original_name': path.relative_to(root).as_posix(),
    'file_hash': hashlib.sha256(raw).hexdigest(), 'encoding': encoding,
    'parser_version': VERSION, 'rows': result}
