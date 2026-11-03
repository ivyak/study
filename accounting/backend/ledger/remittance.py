"""ホームの表示だけで、同月の仕送りに含まれる対象支出を控除する。"""
from collections import defaultdict
from decimal import Decimal, ROUND_DOWN
import re
import unicodedata


def purpose(item, title):
  text = unicodedata.normalize('NFKC', item.name or title)
  category = item.category.name
  if category == '住まい' and '家賃' in text:
    return '家賃'
  if category == '交通' and re.search(r'新幹線|スマート\s*EX', text, re.I):
    return '新幹線代'
  if category in {'教育・教養', 'クルマ'} and '免許合宿' in text:
    return '免許合宿代'
  if category == '教育・教養':
    if re.search(r'参考書|教科書|ゼミナール.*コーポレート|財務会計講義|情報符号理論', text):
      return '参考書代'
  if category in {'医療・保険', '美容・衣服'} and re.search(r'コンタクト(?:代|レンズ|購入)', text):
    return 'コンタクト代'
  return None


def apportion(values, total):
  denominator = sum(values.values(), Decimal(0))
  parts = {k: (v*total/denominator).quantize(Decimal('.01'), rounding=ROUND_DOWN) for k, v in values.items()}
  remainder = total-sum(parts.values(), Decimal(0))
  for key in parts:
    extra = min(remainder, Decimal('.01'))
    parts[key] += extra
    remainder -= extra
  return parts


def eligible_amounts(items, title):
  groups = defaultdict(Decimal)
  totals = defaultdict(Decimal)
  for item in items:
    category = item.category.name
    totals[category] += item.amount
    if purpose(item, title):
      groups[category] += item.amount
  # 値引きや立替レシートの自己負担額を超えて控除しない。
  return {k: min(v, max(totals[k], Decimal(0))) if v > 0 else max(v, min(totals[k], Decimal(0)))
    for k, v in groups.items()}


def eligible_breakdown(items, title):
  by_category = defaultdict(lambda: defaultdict(Decimal))
  for item in items:
    label = purpose(item, title)
    if label:
      by_category[item.category.name][label] += item.amount
  result = []
  for category, amount in eligible_amounts(items, title).items():
    if not amount:
      continue
    sign = Decimal(1) if amount > 0 else Decimal(-1)
    values = {k: v*sign for k, v in by_category[category].items() if v*sign > 0}
    for label, value in apportion(values, amount*sign).items():
      result.append({'category': category, 'purpose': label, 'amount': float(value*sign)})
  return result


def adjustments(rows):
  months = defaultdict(lambda: {'support': Decimal(0), 'expenses': defaultdict(Decimal),
    'purposes': defaultdict(lambda: defaultdict(Decimal))})
  for row in rows:
    month = months[row['date'][:7]]
    if row['kind'] == 'income':
      month['support'] += sum((Decimal(str(c['amount'])) for c in row['categoryAmounts']
        if c['category'] == '仕送り'), Decimal(0))
    elif row['kind'] == 'expense':
      for category, amount in row.get('remittanceEligibleAmounts', {}).items():
        month['expenses'][category] += Decimal(str(amount))
      for item in row.get('remittanceEligibleBreakdown', []):
        month['purposes'][item['category']][item['purpose']] += Decimal(str(item['amount']))
  result = {}
  for key, month in months.items():
    expenses = {k: v for k, v in sorted(month['expenses'].items()) if v > 0}
    total = sum(expenses.values(), Decimal(0))
    amount = min(max(month['support'], Decimal(0)), total)
    if not amount:
      continue
    # 同月の仕送りが不足する場合、表示用の控除額を対象カテゴリの金額比で配分する。
    parts = apportion(expenses, amount)
    purposes = defaultdict(Decimal)
    for category, value in parts.items():
      values = {k: v for k, v in sorted(month['purposes'][category].items()) if v > 0}
      for label, portion in apportion(values or {category: expenses[category]}, value).items():
        purposes[label] += portion
    result[key] = {'amount': float(amount), 'expenseByCategory': {k: float(v) for k, v in parts.items()},
      'expenseByPurpose': {k: float(v) for k, v in purposes.items() if v > 0}}
  return result
