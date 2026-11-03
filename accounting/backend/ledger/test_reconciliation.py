from copy import deepcopy
from decimal import Decimal
from django.test import TransactionTestCase
from . import tests as fixtures
from .models import Account, Category, Decision, ImportBatch, RawRecord, Transaction, TransactionItem
from .plans import account_type, plan_digest
from .reconciliation import Reconciler
from .services import apply_review, publish_batch, validate_plan
from .reporting import serialize_transactions, snapshot, transaction_queryset


class ReconciliationProposalTests(TransactionTestCase):
  setUp = fixtures.AccountingTests.setUp
  tearDown = fixtures.AccountingTests.tearDown
  write_rows = fixtures.AccountingTests.write_rows
  ingest = fixtures.AccountingTests.ingest
  expense = fixtures.AccountingTests.expense
  def test_reconciliation_is_preview_only_and_cannot_publish(self):
    batch = self.ingest()
    document = Reconciler(batch.pk).build()
    self.assertTrue(document['preview_only'])
    self.assertNotIn('authorization', document)
    self.assertNotIn('answers', document)
    self.assertNotIn('new_plans', document)
    with self.assertRaises(ValueError):
      apply_review(batch.pk, document)
    with self.assertRaises(ValueError):
      apply_review(batch.pk, {'authorization': '個別確認を省略するという旧解釈', 'answers': []})
    with self.assertRaises(ValueError):
      publish_batch(batch.pk)
    self.assertTrue(batch.decisions.exclude(status='confirmed').exists())
    self.assertFalse(Transaction.objects.exists())
    self.assertFalse(snapshot()['ready'])
    self.assertEqual(account_type('仮受金'), 'liability')

  def test_zero_net_receipt_keeps_positive_and_negative_items(self):
    batch = self.ingest()
    raw = RawRecord.objects.get(transaction_date__isnull=False)
    plan = self.expense(raw)
    plan['amount'] = '0'
    plan['entries'] = [
      {'account': '食費', 'account_type': 'expense', 'debit': '1000', 'credit': '0'},
      {'account': '食費', 'account_type': 'expense', 'debit': '0', 'credit': '1000'},
    ]
    plan['items'] = [{'category': '食費', 'name': '商品', 'amount': '1000'}, {'category': '食費', 'name': '親負担', 'amount': '-1000'}]
    validate_plan(plan)
    plan['items'][1]['amount'] = '0'
    with self.assertRaises(ValueError):
      validate_plan(plan)

  def test_confirming_column_mapping_does_not_confirm_transactions(self):
    batch = self.ingest()
    mapping = batch.decisions.get(kind='mapping')
    apply_review(batch.pk, {'answers': [{'decision_id': mapping.pk,
      'expected_digest': plan_digest(mapping.proposal), 'answer': '列対応の確認だけ省略する。',
      'reason': '照合・分類はユーザー確認を継続する。'}]})
    mapping.refresh_from_db()
    self.assertEqual(mapping.status, 'confirmed')
    self.assertTrue(batch.decisions.filter(kind='transaction', status='proposed').exists())
    self.assertFalse(Transaction.objects.exists())
    with self.assertRaises(ValueError):
      publish_batch(batch.pk)

  def test_many_card_suica_evidence_is_grouped_without_arbitrary_pair(self):
    r = Reconciler(self.ingest().pk)
    template = {'operation': 'upsert', 'kind': 'transfer', 'date': '2026-10-01', 'amount': '1000',
      '_incoming': 'Suica', '_eligible': False, 'items': [], 'assessment': {}, 'title': 'チャージ'}
    plans = []
    for i, (account, side) in enumerate([('三井住友カード未払金', 'out'), ('楽天カード未払金', 'out'),
      ('クレジットカード未払金', 'in'), ('クレジットカード未払金', 'in')], 1):
      p = deepcopy(template)
      p.update(key=str(i), _outgoing=account, _side=side, raw_ids=[i], sources=[{'raw_record_id': i}], entries=[])
      plans.append(p)
    r.plans = plans
    r.merge_transfers()
    self.assertEqual(len(r.plans), 1)
    self.assertEqual(Decimal(r.plans[0]['amount']), 2000)
    self.assertEqual(set(r.plans[0]['raw_ids']), {1, 2, 3, 4})
    self.assertEqual([e['account'] for e in r.plans[0]['entries']], ['Suica', '三井住友カード未払金', '楽天カード未払金'])

  def test_more_than_one_thousand_distinct_receipt_sources(self):
    batch = ImportBatch.objects.create(status='published')
    account = Account.objects.create(name='食費', type='expense')
    category = Category.objects.create(name='食費', account=account)
    raw = RawRecord.objects.bulk_create([RawRecord(source='test', dedupe_scope='test', dedupe_key=f'bulk-{i}',
      occurrence_number=1, raw_data={'values': []}) for i in range(1005)])
    transactions = Transaction.objects.bulk_create([Transaction(identity_key=f'bulk-{i}', date='2026-10-01',
      kind='expense', title='架空の取引', amount=1, last_batch=batch) for i in range(1005)])
    TransactionItem.objects.bulk_create([TransactionItem(transaction=tx, category=category, source_raw_record=r,
      name='架空の品目', amount=1) for tx, r in zip(transactions, raw)])
    self.assertEqual(len(serialize_transactions(transaction_queryset())), 1005)
