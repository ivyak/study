"""全確定取引の重複候補を読み取り専用で調べる。候補は重複の確定を意味しない。"""
from collections import Counter, defaultdict
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher
from functools import lru_cache
import re
from .models import Decision, Transaction
from .reconciliation import shop_key
from .reporting import refs


@lru_cache(maxsize=8192)
def merchant(value):
  key = shop_key(value)
  if re.search('時計台旅行|キャリア.*トラベル', key):
    return '大学生協旅行'
  if re.search('スペースマーケット|スペモ.*レンタル', key):
    return 'スペースマーケット'
  return key


def similarity(a, b):
  def keys(row):
    return {merchant(x) for x in row['merchants'] if x and len(merchant(x)) >= 2
      and merchant(x) not in {'現金支出', '食費の精算', '支払い', '送った金額'}
      and not re.fullmatch(r'[\d_*]+', merchant(x))}
  def chain(key):
    for name in ['ファミリーマート', 'セブンイレブン', 'ローソン', 'サイゼリヤ', '松屋', 'MOVIX', '深夜ラーメンB']:
      if name in key:
        return name
    return None
  return max((0 if chain(x) and chain(y) and chain(x) != chain(y)
    else SequenceMatcher(None, x, y).ratio() for x in keys(a) for y in keys(b)), default=0)


def subsets(rows, target):
  # 2通り見つかった時点で一意ではないと分かる。曖昧な候補は自動統合しない。
  reachable = {Decimal(0): [()]}
  for row in rows:
    value = Decimal(row['amount'])
    for total, solutions in [(value, list(solutions)) for value, solutions in reachable.items()]:
      new = total+value
      if new > target:
        continue
      bucket = reachable.setdefault(new, [])
      for solution in list(solutions):
        candidate = solution+(row['id'],)
        if candidate not in bucket and len(bucket) < 2:
          bucket.append(candidate)
  return reachable.get(target, [])


def detect(rows):
  candidates = {}
  by_id = {r['id']: r for r in rows}
  def add(kind, ids, evidence):
    ids = tuple(sorted(set(ids)))
    if len(ids) < 2 and kind != 'existing_link_needs_review':
      return
    key = (kind, ids)
    candidates[key] = {'type': kind, 'transaction_ids': ids, 'evidence': evidence,
      'status': 'needs_review', 'transactions': [by_id[i] for i in ids]}
  receipts = [r for r in rows if r['receipt_only'] and r['kind'] in {'expense', 'income'} and Decimal(r['amount']) > 0]
  payments = [r for r in rows if not r['receipt_only'] and r['has_financial_source']
    and r['kind'] in {'expense', 'income'} and Decimal(r['amount']) > 0]
  pair_checks = 0
  for receipt in receipts:
    near = []
    for payment in payments:
      if payment['kind'] != receipt['kind']:
        continue
      pair_checks += 1
      days = abs((date.fromisoformat(receipt['date'])-date.fromisoformat(payment['date'])).days)
      score = similarity(receipt, payment)
      amount, target = Decimal(payment['amount']), Decimal(receipt['amount'])
      item_amounts = {Decimal(i['amount']) for i in receipt['items'] if Decimal(i['amount']) > 0}
      if days <= 7:
        near.append((payment, score))
        payment_amounts = {amount, *[Decimal(v) for v in payment.get('payment_gross_amounts', [])]}
        if target in payment_amounts:
          add('same_amount', [receipt['id'], payment['id']], {'days': days, 'merchant_similarity': round(score, 3),
            'personal_payment': payment['personal_payment'], 'includes_discount': amount != target})
        elif payment_amounts & item_amounts:
          add('receipt_item_matches_payment', [receipt['id'], payment['id']],
            {'days': days, 'merchant_similarity': round(score, 3), 'difference': str(target-amount)})
        elif score >= .6 and abs(target-amount) <= max(Decimal(100), target*Decimal('.03')):
          add('near_amount', [receipt['id'], payment['id']],
            {'days': days, 'merchant_similarity': round(score, 3), 'difference': str(target-amount)})
      elif score >= .85 and amount == target:
        add('same_merchant_outside_window', [receipt['id'], payment['id']],
          {'days': days, 'merchant_similarity': round(score, 3), 'warning': '別日の通常利用の可能性もある。'})
    compatible = [p for p, score in near if score >= .7]
    solutions = subsets(compatible, Decimal(receipt['amount']))
    for solution in solutions:
      if len(solution) > 1:
        add('multiple_payments_one_receipt', [receipt['id'], *solution],
          {'amount': receipt['amount'], 'ambiguous': len(solutions) > 1})
    personal = [p for p, score in near if p['personal_payment'] and p['date'] == receipt['date']]
    for solution in subsets(personal, Decimal(receipt['amount'])):
      if len(solution) > 1:
        add('multiple_personal_payments_one_receipt', [receipt['id'], *solution],
          {'amount': receipt['amount'], 'warning': '店名の根拠がないため必ず個別確認する。'})
  for payment in payments:
    compatible = [r for r in receipts if r['kind'] == payment['kind']
      and abs((date.fromisoformat(r['date'])-date.fromisoformat(payment['date'])).days) <= 7
      and similarity(r, payment) >= .7]
    solutions = subsets(compatible, Decimal(payment['amount']))
    for solution in solutions:
      if len(solution) > 1:
        add('multiple_receipts_one_payment', [payment['id'], *solution],
          {'amount': payment['amount'], 'ambiguous': len(solutions) > 1})
  for index, a in enumerate(payments):
    for b in payments[index+1:]:
      if a['kind'] != b['kind'] or a['amount'] != b['amount'] or set(a['source_names']) & set(b['source_names']):
        continue
      days = abs((date.fromisoformat(a['date'])-date.fromisoformat(b['date'])).days)
      if days <= 7 and similarity(a, b) >= .85:
        add('financial_sources_same_payment', [a['id'], b['id']], {'days': days, 'merchant_similarity': round(similarity(a, b), 3)})
  # 同じ外部取引番号が複数の確定取引に現れる場合も、全期間で検査する。
  external = defaultdict(set)
  for row in rows:
    for source in row['external_ids']:
      external[(source['source'], source['id'], row['kind'], row['amount'])].add(row['id'])
  for (source, external_id, kind, amount), ids in external.items():
    if len(ids) > 1:
      add('shared_external_id', ids, {'source': source, 'external_id': external_id,
        'warning': '購入・返金・ポイント・一部精算は区別して確認する。'})
  linked_count = 0
  for row in rows:
    payments = row.get('financial_raws', [])
    receipts = row.get('linked_receipts', [])
    if not payments or not receipts:
      continue
    linked_count += 1
    named_payments = [p for p in payments if not p['personal_payment'] and len(merchant(p['store'])) >= 2]
    named_receipts = [r for r in receipts if len(merchant(r['store'])) >= 2]
    score = similarity({'merchants': [p['store'] for p in named_payments]},
      {'merchants': [r['store'] for r in named_receipts]})
    days = max((abs((date.fromisoformat(p['date'])-date.fromisoformat(r['date'])).days)
      for p in payments for r in receipts if p['date'] and r['date']), default=0)
    if days > 7 or (named_payments and named_receipts and score < .35):
      add('existing_link_needs_review', [row['id']], {'merchant_similarity': round(score, 3), 'days': days,
        'warning': '既存の照合も検査対象。表記差・施設名・加盟店名の違いか、誤対応かを区別する。'})
  result = sorted(candidates.values(), key=lambda c: (min(r['date'] for r in c['transactions']), c['type'], c['transaction_ids']))
  for index, candidate in enumerate(result, 1):
    candidate['id'] = f'R{index:03d}'
  affected = {i for c in result for i in c['transaction_ids']}
  return {'transactions_checked': len(rows), 'receipt_payment_pairs_checked': pair_checks,
    'existing_receipt_links_checked': linked_count,
    'candidate_count': len(result), 'candidate_types': dict(Counter(c['type'] for c in result)),
    'coverage': [{'transaction_id': r['id'], 'kind': r['kind'], 'has_candidate': r['id'] in affected,
      'sources': r['source_names'], 'check': '金額・日付・店名・外部番号・内訳・仕訳を検査。候補なしでも重複なしの保証ではない。'} for r in rows],
    'candidates': result}


def audit():
  rows = []
  integrity_errors = []
  queryset = Transaction.objects.order_by('date', 'id').prefetch_related('items__category', 'entries__account',
    'sources__raw_record__occurrences__import_file')
  for tx in queryset.iterator(chunk_size=50):
    sources, entries, items = list(tx.sources.all()), list(tx.entries.all()), list(tx.items.all())
    if sum((e.debit-e.credit for e in entries), Decimal(0)):
      integrity_errors.append({'id': tx.pk, 'error': '借方貸方不一致'})
    if tx.kind in {'expense', 'income'} and sum((i.amount for i in items), Decimal(0)) != tx.amount:
      integrity_errors.append({'id': tx.pk, 'error': '取引金額と内訳不一致'})
    financial = [s.raw_record for s in sources if s.role != 'detail' and s.raw_record.source != 'zaim'
      and (s.raw_record.source != 'univ_coop' or s.raw_record.direction in {'out', 'in'})]
    rows.append({'id': tx.pk, 'key': tx.identity_key, 'kind': tx.kind, 'date': str(tx.date),
      'title': tx.title, 'amount': str(tx.amount), 'receipt_only': bool(sources) and all(s.raw_record.source == 'zaim' for s in sources),
      'has_financial_source': bool(financial), 'source_names': sorted({s.raw_record.source for s in sources}),
      'personal_payment': any(r.source == 'PayPay_Corporation' and '送った金額' in r.memo for r in financial),
      'payment_gross_amounts': [str(r.amount) for r in financial if r.amount is not None],
      'financial_raws': [{'id': r.pk, 'date': str(r.transaction_date) if r.transaction_date else None,
        'store': r.store or r.memo, 'personal_payment': r.source == 'PayPay_Corporation' and '送った金額' in r.memo} for r in financial],
      'linked_receipts': [{'id': s.raw_record_id, 'date': str(s.raw_record.transaction_date) if s.raw_record.transaction_date else None,
        'store': s.raw_record.store} for s in sources if s.raw_record.source == 'zaim'],
      'merchants': list(dict.fromkeys([tx.title, *[s.raw_record.store or s.raw_record.memo for s in sources]])),
      'external_ids': [{'source': r.source, 'id': r.source_transaction_id} for r in financial if r.source_transaction_id],
      'items': [{'name': i.name, 'category': i.category.name, 'amount': str(i.amount)} for i in items],
      'entries': [{'account': e.account.name, 'type': e.account.type, 'debit': str(e.debit), 'credit': str(e.credit)} for e in entries],
      'refs': [ref for s in sources for ref in refs(s.raw_record)]})
  result = detect(rows)
  resolutions = {}
  for decision in Decision.objects.filter(kind='duplicate_review',status='confirmed',batch__status='published').order_by('id'):
    proposal = decision.proposal
    if proposal.get('resolution') in {'distinct', 'existing_link_confirmed'}:
      resolutions[tuple(sorted(proposal['transaction_ids']))] = {
        'question_id': proposal['question_id'], 'resolution': proposal['resolution'],
        'decision_id': decision.pk, 'reason': decision.reason}
  for candidate in result['candidates']:
    resolution = resolutions.get(tuple(candidate['transaction_ids']))
    if resolution:
      candidate['status'] = 'user_reviewed'
      candidate['review_resolution'] = resolution
  result.update(read_only=True, version='1.1', integrity_errors=integrity_errors,
    limitations=['同額だけで同一決済とは確定しない。複数候補・立替精算・差額・異なる用途は人が確認する。',
      '全取引を検査するが、取引内訳のない現金支払い・日付の大きなずれ・差額や未知の店名表記から重複なしを証明することはできない。',
      '7日以内は金額一致・内訳一致・類似店名で比較。期間外も同店同額と外部番号を検査する。',
      '複数決済合算は店名の裏付けを条件に探索し、2通り見つかれば曖昧と記録する。',
      'ホームの仕送り控除は表示条件であり、取引の重複解消ではない。',
      'カテゴリで絞った取引一覧は取引全額、カテゴリ別集計は該当内訳の金額を表示する。'])
  return result
