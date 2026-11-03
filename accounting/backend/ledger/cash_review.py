"""高額現金引き出しの用途確認。資金の使途は日付・金額から断定しない。"""
from decimal import Decimal
from .models import Decision, Transaction
from .reporting import refs


MINIMUM = Decimal(10000)


def needs_review(amount, status):
  return Decimal(amount) >= MINIMUM and status not in {'confirmed', 'reviewed_unknown'}


def withdrawals():
  resolutions = {}
  pending = {}
  for decision in Decision.objects.filter(kind='withdrawal_review').order_by('id'):
    pk = decision.proposal.get('transaction_id')
    if decision.status == 'confirmed' and decision.proposal.get('purpose_status') in {'confirmed', 'reviewed_unknown'}:
      resolutions[pk] = decision.proposal
    elif decision.status == 'proposed':
      pending[pk] = decision.pk
  result = []
  queryset = Transaction.objects.filter(kind='transfer', amount__gte=MINIMUM).order_by('date','id').prefetch_related(
    'entries__account','sources__raw_record__occurrences__import_file')
  for tx in queryset.iterator(chunk_size=50):
    entries = list(tx.entries.all())
    cash = sum((e.debit-e.credit for e in entries if e.account.name == '現金'), Decimal(0))
    if cash < MINIMUM:
      continue
    resolution = resolutions.get(tx.pk,{})
    status = resolution.get('purpose_status','awaiting_user')
    result.append({'transaction_id':tx.pk,'identity_key':tx.identity_key,'date':str(tx.date),'amount':str(cash),
      'bank':' / '.join(e.account.name for e in entries if e.credit and e.account.name != '現金'),
      'purpose_status':status,'purpose':resolution.get('purpose',''), 'needs_user_answer':needs_review(cash,status),
      'review_decision_id':pending.get(tx.pk),
      'sources':[r for source in tx.sources.all() for r in refs(source.raw_record)]})
  return result
