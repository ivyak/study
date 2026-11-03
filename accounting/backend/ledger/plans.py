"""表示デモの判断を明示的な仕訳案へ変換する。元コードは実行しない。"""
from collections import defaultdict
from decimal import Decimal
import hashlib
import json

COLORS = {'食費': '#b8d866', '日用雑貨': '#7dcede', '交通': '#b69ad8',
  'エンタメ': '#e6a36a', '教育・教養': '#bb9674', '美容・衣服': '#78bc8c',
  'その他': '#a4a4a4', '水道光熱費': '#e0cc65', '通信・サブスク': '#7da9e4',
  '住まい': '#bda589', '通信': '#7da9e4', 'ゲーム': '#dfb56e',
  '不明': '#a4a4a4', '大型出費/旅行': '#a4a4a4',
  '交際費': '#d86c87', 'クルマ': '#e57d73', '医療・保険': '#e0cc65'}
ALIASES = {'交通費': '交通', '美容': '美容・衣服', '衣服': '美容・衣服',
  '娯楽費': 'エンタメ', '書籍・教材費': '教育・教養', '教育': '教育・教養', '宿泊費': '大型出費/旅行'}


def category_name(value):
  return ALIASES.get(value, value)


def account_type(name):
  return 'liability' if name.endswith('未払金') or name == '仮受金' else 'equity' if name == '開始残高調整' else 'asset'


def category_account_name(name, kind):
  # 表示カテゴリは共通でも、収益勘定と費用勘定は区別する。
  return '不明（収入）' if name == '不明' and kind == 'income' else name


def entry(account, value, side, kind=None):
  account = category_account_name(account, kind)
  value = Decimal(str(value))
  if value < 0:
    side, value = ('credit' if side == 'debit' else 'debit'), -value
  return {'account': account, 'account_type': kind or account_type(account),
    'debit': str(value if side == 'debit' else 0), 'credit': str(value if side == 'credit' else 0)}


def legacy_plan(row, lookup):
  kind = row['kind']
  amounts = defaultdict(Decimal)
  for part in row.get('categoryAmounts') or [{'category': row['category'], 'amount': row['amount']}]:
    amounts[category_name(part['category'])] += Decimal(str(part['amount']))
  references = []
  missing = []
  for ref in row.get('sources', []):
    raw_id = lookup.get(ref.get('recordId'))
    if raw_id:
      references.append(raw_id)
    else:
      missing.append(ref)
  entries = []
  if kind == 'transfer':
    entries = [entry(row['to'], row['amount'], 'debit'), entry(row['account'], row['amount'], 'credit')]
  elif kind in {'income', 'expense'}:
    for name, value in amounts.items():
      entries.append(entry(name, value, 'credit' if kind == 'income' else 'debit', kind))
    for part in row.get('splits') or [{'account': row['account'], 'amount': row['amount']}]:
      entries.append(entry(part['account'], part['amount'], 'debit' if kind == 'income' else 'credit'))
  items = []
  receipt = row.get('zaimItems', [])
  if receipt:
    for i, z in enumerate(receipt):
      name = category_name(z['category'])
      receipt_amount = Decimal(str(z['amount']))
      # 立替の自己負担への配分は、既存デモから機械的に決めず確認する。
      allocation = receipt_amount if row.get('receiptTotal', row['amount']) == row['amount'] else None
      items.append({'category': name, 'name': z['item'], 'store': z['store'], 'subcategory': z['detail'],
        'amount': str(allocation) if allocation is not None else None, 'receipt_amount': str(receipt_amount),
        'source_raw_record_id': lookup.get(z['source'].get('recordId')), 'position': i})
  elif kind in {'income', 'expense'}:
    items = [{'category': name, 'name': row['memo'], 'amount': str(value), 'receipt_amount': None,
      'source_raw_record_id': None, 'store': '', 'subcategory': '', 'position': i} for i, (name, value) in enumerate(amounts.items())]
  sources = []
  zaim_ids = {i['source_raw_record_id'] for i in items if i['source_raw_record_id']}
  for raw_id in sorted(set(references)):
    sources.append({'raw_record_id': raw_id, 'role': 'detail' if raw_id in zaim_ids else 'payment', 'linked_amount': None})
  return {'operation': 'upsert', 'key': row['id'], 'date': row['date'], 'kind': kind,
    'title': row['memo'], 'amount': str(row['amount']), 'currency': 'JPY', 'entries': entries,
    'items': items, 'sources': sources, 'raw_ids': sorted(set(references)),
    'legacy': {'status': row['status'], 'zaimMatch': row.get('zaimMatch'), 'missingReferences': missing,
      'receiptTotal': row.get('receiptTotal'), 'advanceAmount': row.get('advanceAmount')}}


def plan_digest(plan):
  return hashlib.sha256(json.dumps(plan, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
