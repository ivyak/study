from collections import defaultdict
from datetime import date
from decimal import Decimal
from django.db.models import Max, Min
from .models import Account, Category, Decision, ImportBatch, JournalEntry, RawRecord, Transaction
from .parsers import NAMES, billed_amount
from .remittance import adjustments, eligible_amounts, eligible_breakdown


def number(value):
  value = Decimal(value or 0)
  return int(value) if value == int(value) else float(value)


def refs(raw):
  occurrences = list(raw.occurrences.all())
  if not occurrences:
    return []
  o = max(occurrences, key=lambda x: (x.batch_id, x.pk))
  return [{'file': o.import_file.original_name, 'line': o.line_start,
    'lineEnd': o.line_end, 'recordId': raw.dedupe_key, 'rawRecordId': raw.pk}]


def journal_pairs(entries):
  debit = [[e.account.name, e.debit] for e in entries if e.debit]
  credit = [[e.account.name, e.credit] for e in entries if e.credit]
  pairs = []
  i = j = 0
  while i < len(debit) and j < len(credit):
    amount = min(debit[i][1], credit[j][1])
    pairs.append({'debit': debit[i][0], 'credit': credit[j][0], 'amount': number(amount)})
    debit[i][1] -= amount
    credit[j][1] -= amount
    i += debit[i][1] == 0
    j += credit[j][1] == 0
  return pairs


def transaction_queryset():
  return Transaction.objects.order_by('date', 'id').prefetch_related(
    'entries__account', 'items__category', 'items__source_raw_record__occurrences__import_file',
    'sources__raw_record__occurrences__import_file')


def serialize_transaction(tx):
  entries = sorted(tx.entries.all(), key=lambda e: e.position)
  items = sorted(tx.items.all(), key=lambda i: i.position)
  categories = defaultdict(Decimal)
  for item in items:
    categories[item.category.name] += item.amount
  if tx.kind == 'transfer':
    outgoing = ' / '.join(dict.fromkeys(e.account.name for e in entries if e.credit))
    incoming = ' / '.join(dict.fromkeys(e.account.name for e in entries if e.debit))
  else:
    payments = [e for e in entries if e.account.type not in {'expense', 'income'}]
    outgoing = ' / '.join(dict.fromkeys(e.account.name for e in payments))
    incoming = ''
  source_refs = [r for link in tx.sources.all() for r in refs(link.raw_record)]
  receipt = [i for i in items if i.source_raw_record and i.source_raw_record.source == 'zaim' and i.receipt_amount is not None]
  judgement = getattr(tx, '_assessment', {})
  duplicate_reviews = getattr(tx, '_duplicate_reviews', [])
  withdrawal_reviews = getattr(tx, '_withdrawal_reviews', [])
  status = '重複確認待ち' if duplicate_reviews else '用途確認待ち' if withdrawal_reviews else 'ユーザー確認済み' if judgement.get('confidence') == 'user' else 'Codex仮置き' if judgement.get('confidence') == 'assumed' else 'Codex判定' if judgement else '記帳済み'
  result = {'id': str(tx.pk), 'identityKey': tx.identity_key, 'date': str(tx.date), 'kind': tx.kind,
    'amount': number(tx.amount), 'account': outgoing, 'to': incoming, 'memo': tx.title,
    'category': ' / '.join(k for k, v in categories.items() if v) or ('振替' if tx.kind == 'transfer' else '開始残高'),
    'categoryAmounts': [{'category': k, 'amount': number(v)} for k, v in categories.items() if v],
    'sources': source_refs, 'status': status, 'splits': [],
    'categoryBasis': judgement.get('reason', ''), 'assumptions': list(judgement.get('assumptions', [])),
    'duplicateReview': duplicate_reviews,
    'withdrawalReview': withdrawal_reviews,
    'journalEntries': journal_pairs(entries)}
  if tx.kind in {'expense', 'income'} and tx.sources.all() and all(s.raw_record.source == 'zaim' for s in tx.sources.all()):
    result['assumptions'].append('Zaimのみを根拠にした記録です。現金の受け払いを個別確認していない場合は、別の決済との重複が残る可能性があります。分類の確認済みは重複なしの保証ではありません。')
  for review in duplicate_reviews:
    result['assumptions'].append(f"重複候補{review['question_id']}は回答待ち。元の計上を維持しており、同じ支払いと確認できるまで統合しない。")
  for review in withdrawal_reviews:
    result['assumptions'].append(f"現金引き出しの用途確認{review['question_id']}は回答待ち。近接する支出・入金は候補であり、資金の使途を確定していない。引き出し自体は振替として維持。")
  result['itemDetails'] = [{'item': i.name, 'category': i.category.name, 'detail': i.subcategory,
    'store': i.store, 'amount': number(i.receipt_amount if i.source_raw_record
      and i.source_raw_record.source == 'zaim' and i.receipt_amount is not None else i.amount)}
    for i in items if not (receipt and i.name == '自己負担分' and i.source_raw_record is None)]
  result['itemSourceLabel'] = 'Zaim' if receipt else '生協' if any(
    link.raw_record.source == 'univ_coop' for link in tx.sources.all()) else '取引'
  result['remittanceEligibleAmounts'] = {k: number(v) for k, v in eligible_amounts(items, tx.title).items()} if tx.kind == 'expense' else {}
  result['remittanceEligibleBreakdown'] = eligible_breakdown(items, tx.title) if tx.kind == 'expense' else []
  if receipt:
    result['zaimItems'] = [{'date': str(i.source_raw_record.transaction_date), 'category': i.category.name,
      'detail': i.subcategory, 'item': i.name, 'store': i.store, 'amount': number(i.receipt_amount),
      'source': refs(i.source_raw_record)[0]} for i in receipt]
    result['zaimMatch'] = {'status': status, 'reason': judgement.get('reason') or 'DBに保存された対応。', 'store': receipt[0].store}
    total = sum((i.receipt_amount for i in receipt), Decimal(0))
    advance = sum((e.debit-e.credit for e in entries
      if e.account.type == 'asset' and e.account.name.endswith('立替金')), Decimal(0))
    if total != tx.amount and advance > 0:
      result.update(receiptTotal=number(total), advanceAmount=number(advance))
  return result


def serialize_transactions(queryset):
  # SQLiteの式の深さ上限を避け、関連する元行も小さな単位で取得する。
  transactions = list(queryset.iterator(chunk_size=50)) if hasattr(queryset, 'iterator') else list(queryset)
  batches = {tx.last_batch_id for tx in transactions}
  judgements = {}
  reviews = defaultdict(list)
  withdrawal_reviews = defaultdict(list)
  for decision in Decision.objects.filter(kind='duplicate_review', status='proposed', batch__status='review'):
    for tx_id in decision.proposal.get('transaction_ids', []):
      reviews[tx_id].append({'question_id': decision.proposal['question_id'], 'question': decision.question})
  for decision in Decision.objects.filter(kind='withdrawal_review', status='proposed', batch__status='review'):
    withdrawal_reviews[decision.proposal['transaction_id']].append({
      'question_id': decision.proposal['question_id'], 'question': decision.question})
  for decision in Decision.objects.filter(kind='transaction', status='confirmed', batch_id__in=batches).order_by('id'):
    judgements[(decision.batch_id, decision.proposal.get('key'))] = decision.proposal.get('assessment', {})
  for tx in transactions:
    tx._assessment = judgements.get((tx.last_batch_id, tx.identity_key), {})
    tx._duplicate_reviews = reviews.get(tx.pk, [])
    tx._withdrawal_reviews = withdrawal_reviews.get(tx.pk, [])
  return [serialize_transaction(tx) for tx in transactions]


def summary(rows):
  income = sum(r['amount'] for r in rows if r['kind'] == 'income')
  expense = sum(r['amount'] for r in rows if r['kind'] == 'expense')
  groups = defaultdict(lambda: {'income': 0, 'expense': 0})
  for row in rows:
    if row['kind'] in {'income', 'expense'}:
      for item in row['categoryAmounts']:
        groups[item['category']][row['kind']] += item['amount']
  return {'income': income, 'expense': expense, 'difference': income-expense,
    'categories': [{'category': k, **v} for k, v in groups.items()]}


def balances(month=None, year=None):
  if year is not None:
    start, end = date(int(year), 1, 1), date(int(year)+1, 1, 1)
  else:
    end = date(int(month[:4])+(month[5:] == '12'), int(month[5:]) % 12+1, 1)
    start = date.fromisoformat(month+'-01')
  result = []
  for account in Account.objects.filter(type__in=['asset', 'liability', 'equity']).order_by('id'):
    signed = lambda e: e.debit-e.credit if account.type == 'asset' else e.credit-e.debit
    entries = JournalEntry.objects.filter(account=account, transaction__date__lt=end).select_related('transaction')
    known = account.balance_start_date is not None and account.balance_start_date < end
    value = sum((signed(e) for e in entries if known and e.transaction.date >= account.balance_start_date), Decimal(0)) if known else None
    movement = sum((signed(e) for e in entries if start <= e.transaction.date and e.transaction.kind != 'opening'), Decimal(0))
    result.append({'id': account.pk, 'name': account.name, 'type': account.type, 'currency': account.currency,
      'balanceStartDate': str(account.balance_start_date) if account.balance_start_date else None,
      'balance': number(value) if value is not None else None, 'change': number(movement)})
  holdings = [a for a in result if a['type'] in {'asset', 'liability'}]
  complete = bool(holdings) and all(a['balance'] is not None for a in holdings)
  assets = sum(a['balance'] or 0 for a in result if a['type'] == 'asset')
  liabilities = sum(a['balance'] or 0 for a in result if a['type'] == 'liability')
  return {'month': month, 'year': str(year) if year is not None else None, 'accounts': result, 'complete': complete,
    'assets': assets if complete else None, 'liabilities': liabilities if complete else None,
    'netAssets': assets-liabilities if complete else None}


def publication_state():
  latest = ImportBatch.objects.order_by('-id').first()
  published = ImportBatch.objects.filter(status='published').order_by('-id').first()
  return {'ready': published is not None, 'publishedBatch': published.pk if published else None,
    'dataUpdatedAt': published.published_at.isoformat() if published and published.published_at else None,
    'pendingBatch': latest.pk if latest and latest.status == 'review' else None,
    'pendingDecisions': latest.decisions.exclude(status='confirmed').count() if latest and latest.status == 'review' else 0}


def snapshot():
  state = publication_state()
  if not state['ready']:
    return state
  published = ImportBatch.objects.get(pk=state['publishedBatch'])
  # 複数SELECTの途中で確定処理が割り込まないよう、呼び出し側でread transactionを使う。
  rows = serialize_transactions(transaction_queryset())
  months = sorted({r['date'][:7] for r in rows})
  dates = [r['date'] for r in rows]
  bills = {}
  for raw in RawRecord.objects.filter(source__in=['Vpass', 'Rakuten_Card'], transaction_date__isnull=False,
    occurrences__batch=published).distinct().prefetch_related('occurrences__import_file'):
    key = f'{raw.source}-{raw.billing_month}'
    bill = bills.setdefault(key, {'id': key, 'account': NAMES[raw.source], 'billingMonth': raw.billing_month,
      'total': 0, 'items': [], 'paymentTransactionIds': [], 'totalBasis': '保存済みCSVの請求金額の合計。'})
    amount = number(billed_amount(raw.source, raw.raw_data['values'], raw.raw_data['columns']))
    bill['total'] += amount
    bill['items'].append({'date': str(raw.transaction_date), 'memo': raw.memo, 'amount': amount, 'sources': refs(raw)})
  for bill in bills.values():
    bill['paymentTransactionIds'] = [r['id'] for r in rows if r['kind'] == 'transfer' and r['to'] == bill['account']
      and r['date'].startswith(bill['billingMonth']) and r['amount'] == bill['total']]
  state.update(start=min(dates) if dates else '', end=max(dates) if dates else '',
    transactions=rows, evidence=[], bills=list(bills.values()), coverage={'complete': False, 'scope': '確定したCSV収録分。',
      'openingBalancesKnown': not Account.objects.filter(type__in=['asset', 'liability'], balance_start_date__isnull=True).exists(),
      'sources': list(RawRecord.objects.filter(transaction_date__isnull=False, occurrences__batch=published).values('source').annotate(observedStart=Min('transaction_date'), observedEnd=Max('transaction_date')))},
    categoryColors=dict(Category.objects.values_list('name', 'color')),
    accountTypes=dict(Account.objects.values_list('name', 'type')),
    monthlySummaries={m: summary([r for r in rows if r['date'].startswith(m)]) for m in months},
    remittanceAdjustments=adjustments(rows),
    balanceSheets={m: balances(m) for m in months})
  return state
