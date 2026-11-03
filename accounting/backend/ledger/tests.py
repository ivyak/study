from copy import deepcopy
from decimal import Decimal
import csv
import json
from pathlib import Path
import tempfile
from django.db import connection, connections
from django.db.models import Sum
from django.test import TransactionTestCase, override_settings
from .backup import backup_database, check_database, restore_database, writer_lock
from .models import Account, Decision, ImportBatch, ImportFile, JournalEntry, RawOccurrence, RawRecord, Transaction
from .parsers import HEADERS, COOP_HEADERS, parse_file
from .plans import plan_digest
from .reporting import balances, snapshot
from .services import apply_review, export_review, publish_batch, stage_import, validate_plan


class AccountingTests(TransactionTestCase):
  def setUp(self):
    self.temp = tempfile.TemporaryDirectory()
    self.base = Path(self.temp.name)
    self.override = override_settings(BASE_DIR=self.base, DB_PATH=Path(connection.settings_dict['NAME']))
    self.override.enable()
    self.root = self.base / 'csv_raw_data'
    self.folder = self.root / 'Sumitomo_Mitsui_Banking_Corporation'
    self.folder.mkdir(parents=True)
    self.seed = self.base / 'seed.js'
    self.seed.write_text('window.LifeAccountingData = {"transactions": []};')
    self.file = self.folder / 'bank.csv'
    self.write_rows([['2026/10/01', '1000', '', 'スーパーA', '9000', '', '']])

  def tearDown(self):
    self.override.disable()
    self.temp.cleanup()

  def write_rows(self, rows):
    with self.file.open('w', newline='') as handle:
      csv.writer(handle).writerows([HEADERS[self.folder.name], *rows])

  def ingest(self):
    return stage_import(self.root, self.seed)[0]

  def expense(self, raw):
    return {'operation': 'upsert', 'key': 'test-expense', 'date': '2026-10-01', 'kind': 'expense',
      'title': 'スーパーA', 'amount': '1000', 'currency': 'JPY', 'raw_ids': [raw.pk],
      'entries': [{'account': '食費', 'account_type': 'expense', 'debit': '800', 'credit': '0'},
        {'account': '日用雑貨', 'account_type': 'expense', 'debit': '200', 'credit': '0'},
        {'account': '三井住友銀行', 'account_type': 'asset', 'debit': '0', 'credit': '1000'}],
      'items': [{'category': '食費', 'name': '食料品', 'amount': '800'}, {'category': '日用雑貨', 'name': '洗剤', 'amount': '200'}],
      'sources': [{'raw_record_id': raw.pk, 'role': 'payment', 'linked_amount': '1000'}]}

  def confirm(self, batch, plans=None):
    answers = []
    for d in batch.decisions.exclude(status='confirmed'):
      answer = {'decision_id': d.pk, 'expected_digest': plan_digest(d.proposal), 'answer': '架空データのテスト確認。', 'reason': 'テスト。'}
      if d.kind == 'transaction':
        raw = RawRecord.objects.get(pk=d.proposal['raw_ids'][0])
        answer['proposal'] = (plans or {}).get(raw.pk, self.expense(raw))
      answers.append(answer)
    apply_review(batch.pk, {'answers': answers})

  def test_import_idempotence_and_duplicate_occurrences(self):
    row = ['2026/10/01', '1000', '', 'スーパーA', '9000', '', '']
    self.write_rows([row, row])
    batch = self.ingest()
    self.assertEqual(RawRecord.objects.filter(transaction_date__isnull=False).count(), 2)
    self.assertEqual(set(RawRecord.objects.filter(transaction_date__isnull=False).values_list('occurrence_number', flat=True)), {1, 2})
    again, created = stage_import(self.root, self.seed)
    self.assertFalse(created)
    self.assertEqual(again.pk, batch.pk)
    self.assertEqual(RawOccurrence.objects.count(), 3)

  def test_update_time_tracks_published_data_not_pending_import_or_reads(self):
    from datetime import datetime, timezone
    from .reporting import publication_state
    updated = datetime(2026, 11, 3, 16, 0, tzinfo=timezone.utc)
    ImportBatch.objects.create(status='published', published_at=updated)
    ImportBatch.objects.create(status='review')
    for _ in range(2):
      self.assertEqual(publication_state()['dataUpdatedAt'], updated.isoformat())

  def test_duplicate_review_warning_does_not_change_published_amount(self):
    batch = self.ingest()
    self.confirm(batch)
    publish_batch(batch.pk)
    tx = Transaction.objects.get()
    review_batch = ImportBatch.objects.create()
    Decision.objects.create(batch=review_batch,kind='duplicate_review',status='proposed',
      proposal={'question_id':'D01','transaction_ids':[tx.pk]}, question='架空の原本2行は同じ支払いか。')
    data = snapshot()
    self.assertEqual(data['transactions'][0]['amount'],1000)
    self.assertEqual(data['transactions'][0]['status'],'重複確認待ち')
    self.assertEqual(data['transactions'][0]['duplicateReview'][0]['question_id'],'D01')
    self.assertEqual(data['publishedBatch'],batch.pk)
    self.assertEqual(data['pendingDecisions'],1)

  def test_unknown_requires_permission_and_separates_income_account(self):
    from .plans import entry
    self.write_rows([
      ['2026/10/01', '1000', '', '用途不明の出金', '9000', '', ''],
      ['2026/10/02', '', '200', '用途不明の入金', '9200', '', ''],
    ])
    batch = self.ingest()
    outgoing = RawRecord.objects.get(direction='out')
    incoming = RawRecord.objects.get(direction='in')
    expense = self.expense(outgoing)
    expense['items'] = [{'category': '不明', 'name': '用途不明の出金', 'amount': '1000'}]
    expense['entries'] = [entry('不明', 1000, 'debit', 'expense'), entry('三井住友銀行', 1000, 'credit')]
    with self.assertRaisesMessage(ValueError, '明示的に許可'):
      validate_plan(expense)
    expense['unknown_category_authorized'] = True
    income = {'operation': 'upsert', 'key': 'test-unknown-income', 'date': '2026-10-02',
      'kind': 'income', 'title': '用途不明の入金', 'amount': '200', 'currency': 'JPY',
      'raw_ids': [incoming.pk], 'unknown_category_authorized': True,
      'entries': [entry('三井住友銀行', 200, 'debit'), entry('不明', 200, 'credit', 'income')],
      'items': [{'category': '不明', 'name': '用途不明の入金', 'amount': '200'}],
      'sources': [{'raw_record_id': incoming.pk, 'role': 'payment', 'linked_amount': '200'}]}
    self.confirm(batch, {outgoing.pk: expense, incoming.pk: income})
    publish_batch(batch.pk)
    self.assertEqual(Account.objects.get(name='不明').type, 'expense')
    self.assertEqual(Account.objects.get(name='不明（収入）').type, 'income')
    rows = snapshot()['transactions']
    self.assertEqual({row['kind'] for row in rows}, {'expense', 'income'})
    self.assertEqual(set(Transaction.objects.values_list('items__category__name', flat=True)), {'不明'})

  def test_annual_reports_use_year_end_balance_and_annual_movement(self):
    from .models import Category, TransactionItem
    from .plans import entry
    batch = ImportBatch.objects.create(status='published')
    bank = Account.objects.create(name='架空銀行', type='asset', balance_start_date='2025-12-31')
    wallet = Account.objects.create(name='架空財布', type='asset', balance_start_date='2025-12-31')
    def post(day, kind, amount, entries, category=None):
      tx = Transaction.objects.create(identity_key=f'test-{Transaction.objects.count()}', date=day,
        kind=kind, title='架空取引', amount=amount, last_batch=batch)
      for position, value in enumerate(entries):
        account, _ = Account.objects.get_or_create(name=value['account'], defaults={'type': value['account_type']})
        JournalEntry.objects.create(transaction=tx, account=account, debit=value['debit'], credit=value['credit'], position=position)
      if category:
        account = Account.objects.get(name=category)
        group, _ = Category.objects.get_or_create(name=category, defaults={'account': account})
        TransactionItem.objects.create(transaction=tx, category=group, name='架空品目', amount=amount)
    post('2025-12-31', 'opening', 1000,
      [entry(bank.name, 1000, 'debit'), entry('開始残高調整', 1000, 'credit')])
    post('2026-01-01', 'income', 500,
      [entry(bank.name, 500, 'debit'), entry('給与', 500, 'credit', 'income')], '給与')
    post('2026-10-01', 'expense', 100,
      [entry('食費', 100, 'debit', 'expense'), entry(bank.name, 100, 'credit')], '食費')
    post('2026-12-31', 'expense', -20,
      [entry(bank.name, 20, 'debit'), entry('食費', 20, 'credit', 'expense')], '食費')
    post('2026-12-31', 'transfer', 200,
      [entry(wallet.name, 200, 'debit'), entry(bank.name, 200, 'credit')])
    post('2027-01-01', 'expense', 50,
      [entry('食費', 50, 'debit', 'expense'), entry(bank.name, 50, 'credit')], '食費')
    yearly = self.client.get('/api/accounting/bs?year=2026')
    self.assertEqual(yearly.status_code, 200)
    data = yearly.json()
    accounts = {a['name']: a for a in data['accounts']}
    self.assertEqual(data['year'], '2026')
    self.assertEqual(accounts[bank.name]['balance'], 1220)
    self.assertEqual(accounts[bank.name]['change'], 220)
    self.assertEqual(accounts[wallet.name]['balance'], 200)
    self.assertEqual(data['assets'], 1420)
    monthly = self.client.get('/api/accounting/bs?month=2026-10').json()
    self.assertEqual(next(a for a in monthly['accounts'] if a['name'] == bank.name)['change'], -100)
    pl = self.client.get('/api/accounting/pl?year=2026').json()
    self.assertEqual((pl['income'], pl['expense'], pl['difference']), (500, 80, 420))
    self.assertEqual(self.client.get('/api/accounting/bs?year=0000').status_code, 400)
    self.assertEqual(self.client.get('/api/accounting/bs?month=2026-10&year=2026').status_code, 400)

  def test_quest_debit_is_rent_but_other_quest_transfer_requires_review(self):
    from .reconciliation import Reconciler
    self.write_rows([
      ['2026/10/27', '1000', '', 'NS ｶ)ｸｴｽﾄｶﾝ', '9000', '', ''],
      ['2026/10/28', '2000', '', 'パソコン振込 ｶ)ｸｴｽﾄｶﾝﾘ', '7000', '', ''],
    ])
    batch = self.ingest()
    review = Reconciler(batch.pk).build()
    plans = [x['proposal'] for x in review['proposals'] + review['new_proposals']
      if x.get('proposal', {}).get('operation') == 'upsert' and x['proposal'].get('kind') != 'opening']
    self.assertEqual(len(plans), 2)
    rent = next(p for p in plans if p['date'] == '2026-10-27')
    self.assertEqual(rent['kind'], 'expense')
    self.assertEqual(rent['items'][0]['category'], '家賃')
    self.assertEqual(rent['amount'], '1000.00')
    other = next(p for p in plans if p['date'] == '2026-10-28')
    self.assertEqual(other['kind'], 'transfer')
    self.assertFalse(batch.decisions.filter(status='confirmed').exists())

  def write_coop(self, name, kind, rows):
    folder = self.root / 'univ_coop'
    folder.mkdir(exist_ok=True)
    path = folder / name
    with path.open('w', encoding='cp932', newline='') as handle:
      csv.writer(handle).writerows([COOP_HEADERS[kind], *rows])
    return path

  def test_coop_parser_preserves_quantity_points_and_separate_scopes(self):
    payment = ['2026-01-26 12:00:00', '', '生協電子マネー', 'テスト食堂', '支払い完了', '600 円', '3', '0']
    path = self.write_coop('money.csv', 'money', [payment, payment])
    records = parse_file(path, self.root)['rows']
    self.assertEqual(records[1]['record']['amount'], Decimal('600'))
    self.assertNotIn('balance', records[1]['record'])
    self.assertEqual(records[1]['record']['raw_data']['values'][6], '3')
    self.assertNotEqual(records[1]['record']['dedupe_key'], records[2]['record']['dedupe_key'])
    item = self.write_coop('items.csv', 'items', [['2026-01-26 12:00:01', 'テスト食堂', '架空の品物', '2', '300円']])
    record = parse_file(item, self.root)['rows'][1]['record']
    self.assertEqual(record['amount'], Decimal('600'))
    self.assertEqual(record['direction'], 'detail')
    self.assertEqual(record['dedupe_scope'], 'univ_coop:items')
    self.write_coop('unknown.csv', 'money', [[*payment[:4], '不明な取引', *payment[5:]]])
    with self.assertRaises(ValueError):
      parse_file(self.root / 'univ_coop/unknown.csv', self.root)

  def test_append_coop_preserves_approval_and_preview_does_not_post(self):
    from .coop import preview
    from .reconciliation import Reconciler
    batch = self.ingest()
    self.confirm(batch)
    approved = list(batch.decisions.values('id', 'status', 'proposal', 'user_answer'))
    self.write_coop('money.csv', 'money', [['2026-01-26 12:00:00', '', '生協電子マネー', 'テスト食堂（ベースマネー）', '支払い完了', '600 円', '3', '0']])
    self.write_coop('items.csv', 'items', [['2026-01-26 12:00:01', 'テスト食堂', '架空の品物', '2', '300円']])
    updated, created = stage_import(self.root, self.seed, extend_review=batch.pk)
    self.assertFalse(created)
    self.assertEqual(updated.pk, batch.pk)
    self.assertEqual(list(batch.decisions.filter(pk__in=[d['id'] for d in approved]).values('id', 'status', 'proposal', 'user_answer')), approved)
    report = preview(batch.pk)
    self.assertEqual(report['summary']['payments_with_unique_equal_items'], 1)
    self.assertFalse(report['payments'][0]['amount_meaning_confirmed'])
    self.assertFalse(Transaction.objects.exists())
    proposals = Reconciler(batch.pk).build()
    self.assertEqual(proposals['reconciliation_summary']['deferred_coop_records'], 2)
    coop_decisions = batch.decisions.filter(kind='transaction', proposal__source='univ_coop')
    self.assertEqual(coop_decisions.filter(status='proposed').count(), 2)
    stage_import(self.root, self.seed, extend_review=batch.pk)
    self.assertEqual(batch.occurrences.filter(import_file__source='univ_coop').count(), 4)
    self.write_rows([['2026/10/01', '999', '', '変更', '9001', '', '']])
    with self.assertRaises(ValueError):
      stage_import(self.root, self.seed, extend_review=batch.pk)

  def test_confirmed_card_only_charge_keeps_suica_opening_adjustment(self):
    from .reconciliation import Reconciler
    from .plans import entry
    batch = ImportBatch.objects.create()
    file = ImportFile.objects.create(source='Super_Urban_Intelligent_Card', original_name='test.csv',
      file_hash='0'*64, encoding='utf-8', parser_version='1.0')
    balance = RawRecord.objects.create(source='Super_Urban_Intelligent_Card', dedupe_scope='test',
      dedupe_key='test-balance', occurrence_number=1, raw_data={}, transaction_date='2026-08-21',
      amount=0, balance=1000, direction='unknown')
    card = RawRecord.objects.create(source='Rakuten_Card', dedupe_scope='test', dedupe_key='test-card',
      occurrence_number=1, raw_data={}, transaction_date='2026-08-21', amount=1000,
      direction='out', memo='モバイルスイカ')
    for line, raw in enumerate([balance, card], 1):
      RawOccurrence.objects.create(batch=batch, import_file=file, raw_record=raw, line_start=line, line_end=line)
    Decision.objects.create(batch=batch, kind='transaction', status='confirmed', proposal={
      'operation': 'upsert', 'key': card.dedupe_key, 'date': '2026-08-21', 'kind': 'transfer',
      'title': 'Suicaチャージ', 'amount': '1000', 'currency': 'JPY', 'raw_ids': [card.pk], 'items': [],
      'entries': [entry('Suica', 1000, 'debit'), entry('楽天カード未払金', 1000, 'credit')],
      'sources': [{'raw_record_id': card.pk, 'role': 'transfer_out', 'linked_amount': '1000'}]})
    document = Reconciler(batch.pk).build()
    openings = [x['proposal'] for x in document['new_proposals'] if x['proposal']['kind'] == 'opening']
    self.assertEqual(Decimal(openings[0]['amount']), Decimal('0'))
    self.assertEqual(Decimal(document['reconciliation_summary']['balance_checks'][0]['ledger_balance']), Decimal('1000'))
    apply_review(batch.pk, {'new_plans': [{'proposal': openings[0], 'answer': '架空の開始残高を確認。', 'reason': 'テスト。'}]})
    rebuilt = Reconciler(batch.pk).build()
    self.assertFalse(any(x['proposal']['kind'] == 'opening' for x in rebuilt['new_proposals']))
    self.assertEqual(Decimal(rebuilt['reconciliation_summary']['balance_checks'][0]['ledger_balance']), Decimal('1000'))

  def test_future_transactions_reject_rule_only_approval(self):
    (self.base / 'review_policy.json').write_text(json.dumps({'rules': {'explicitReviewFrom': '2026-11-04'}}))
    self.write_rows([['2026/11/04', '1000', '', 'スーパーA', '9000', '', '']])
    batch = self.ingest()
    decision = batch.decisions.get(kind='transaction')
    plan = self.expense(RawRecord.objects.get(pk=decision.proposal['raw_ids'][0]))
    plan['date'] = '2026-11-04'
    answer = {'decision_id': decision.pk, 'expected_digest': plan_digest(decision.proposal),
      'proposal': plan, 'answer': '同種ルール。', 'reason': 'テスト。', 'approval_mode': 'rule'}
    with self.assertRaises(ValueError):
      apply_review(batch.pk, {'answers': [answer]})
    ignored = {**answer, 'proposal': {'operation': 'ignore', 'raw_ids': plan['raw_ids'], 'reason': '架空のルール。'}}
    with self.assertRaises(ValueError):
      apply_review(batch.pk, {'answers': [ignored]})
    with self.assertRaises(ValueError):
      apply_review(batch.pk, {'new_plans': [{'proposal': {**plan, 'key': 'future-rule'},
        'answer': 'ルール適用。', 'reason': 'テスト。', 'approval_mode': 'rule'}]})
    decision.refresh_from_db()
    self.assertEqual(decision.status, 'proposed')
    answer['approval_mode'] = 'explicit'
    answer['answer'] = 'この取引の内容を個別確認。'
    apply_review(batch.pk, {'answers': [answer]})
    decision.refresh_from_db()
    self.assertEqual(decision.status, 'confirmed')

  def test_point_discount_is_visible_and_not_reported_as_advance(self):
    batch = self.ingest()
    raw = RawRecord.objects.get(transaction_date__isnull=False)
    receipt = RawRecord.objects.create(source='zaim', dedupe_scope='test', dedupe_key='test-point-receipt',
      occurrence_number=1, raw_data={}, transaction_date='2026-10-01', amount=1000, direction='out')
    file = batch.occurrences.first().import_file
    RawOccurrence.objects.create(batch=batch, raw_record=receipt, import_file=file, line_start=99, line_end=99)
    plan = self.expense(raw)
    plan['amount'] = '997'
    plan['entries'][0]['debit'] = '797'
    plan['entries'][-1]['credit'] = '997'
    for i in plan['items']:
      i.update(source_raw_record_id=receipt.pk, receipt_amount=i['amount'])
    plan['items'].append({'category': '食費', 'name': '架空ポイント利用による値引き', 'amount': '-3'})
    plan['raw_ids'].append(receipt.pk)
    plan['sources'].append({'raw_record_id': receipt.pk, 'role': 'detail', 'linked_amount': '1000'})
    self.confirm(batch, {raw.pk: plan})
    publish_batch(batch.pk)
    row = snapshot()['transactions'][0]
    self.assertNotIn('advanceAmount', row)
    self.assertEqual(row['itemDetails'][-1]['item'], '架空ポイント利用による値引き')
    self.assertEqual(row['itemDetails'][-1]['amount'], -3)

  def test_changed_header_aborts_before_db_write(self):
    self.file.write_text('未知の列\n1000\n')
    with self.assertRaises(ValueError):
      self.ingest()
    self.assertFalse(ImportBatch.objects.exists())
    self.assertFalse(RawRecord.objects.exists())

  def test_invalid_date_or_money_aborts(self):
    self.write_rows([['2026/02/30', '1000', '', '店', '9000', '', '']])
    with self.assertRaises(ValueError):
      self.ingest()
    self.write_rows([['2026/10/01', 'NaN', '', '店', '9000', '', '']])
    with self.assertRaises(ValueError):
      self.ingest()

  def test_csv_physical_line_range_includes_quoted_newline(self):
    self.write_rows([['2026/10/01', '1000', '', 'メモの1行目\nメモの2行目', '9000', '', '']])
    parsed = parse_file(self.file, self.root)
    self.assertEqual(parsed['rows'][1]['line_start'], 2)
    self.assertEqual(parsed['rows'][1]['line_end'], 3)
    batch = self.ingest()
    self.assertEqual(batch.occurrences.get(line_start=2).line_end, 3)

  def test_foreign_card_supplement_is_not_another_payment(self):
    folder = self.root / 'Rakuten_Card'
    folder.mkdir()
    path = folder / 'enavi202611.csv'
    header = ['利用日', '利用店名・商品名', '利用者', '支払方法', '利用金額', '手数料/利息', '支払総額', '11月支払金額', '12月繰越残高', '新規サイン']
    with path.open('w', newline='') as handle:
      csv.writer(handle).writerows([header,
        ['2026/10/01', '海外店舗', '', '1回', '1000', '0', '1000', '1000', '0', ''],
        ['', '現地利用額 10.00 変換レート100円', '', '', '', '', '', '', '', '']])
    parsed = parse_file(path, self.root)
    self.assertEqual(sum(bool(r['record'].get('transaction_date')) for r in parsed['rows']), 1)
    self.assertEqual(len(parsed['rows']), 3)

  def test_filename_change_keeps_raw_identity_and_provenance(self):
    batch = self.ingest()
    batch.status = 'failed'
    batch.save()
    self.file.rename(self.folder / 'old.csv')
    next_batch = self.ingest()
    self.assertEqual(RawRecord.objects.filter(transaction_date__isnull=False).count(), 1)
    self.assertEqual(ImportFile.objects.count(), 2)
    self.assertEqual(next_batch.occurrences.count(), 2)

  def test_unconfirmed_batch_cannot_publish_or_leak(self):
    batch = self.ingest()
    with self.assertRaises(ValueError):
      publish_batch(batch.pk)
    self.assertFalse(Transaction.objects.exists())
    data = snapshot()
    self.assertFalse(data['ready'])
    self.assertNotIn('transactions', data)

  def test_review_stale_digest_rejected(self):
    batch = self.ingest()
    d = batch.decisions.first()
    with self.assertRaises(ValueError):
      apply_review(batch.pk, {'answers': [{'decision_id': d.pk, 'expected_digest': 'old', 'answer': 'yes', 'reason': 'test'}]})
    d.refresh_from_db()
    self.assertEqual(d.status, 'proposed')

  def test_publish_balanced_split_and_readonly_api(self):
    batch = self.ingest()
    self.confirm(batch)
    publish_batch(batch.pk)
    self.assertEqual(Transaction.objects.count(), 1)
    self.assertEqual(JournalEntry.objects.aggregate(total=Sum('debit'))['total'], Decimal('1000'))
    data = self.client.get('/api/accounting/transactions?month=2026-10&kind=expense&category=日用雑貨').json()
    self.assertEqual(data['count'], 1)
    self.assertEqual(self.client.get('/api/accounting/pl?month=2026-10').json()['expense'], 1000)
    self.assertEqual(self.client.get('/api/accounting/calendar?month=2026-10').json()[0]['expense'], 1000)
    self.assertEqual(self.client.post('/api/accounting/transactions', data={}).status_code, 405)
    self.assertEqual(self.client.get('/api/accounting/snapshot', HTTP_ORIGIN='https://example.org').status_code, 403)
    self.assertEqual(self.client.get('/api/accounting/snapshot', HTTP_HOST='evil.example').status_code, 400)
    self.assertEqual(self.client.get('/api/accounting/transactions?month=2026-13').status_code, 400)
    self.assertEqual(self.client.get('/api/accounting/transactions?limit=-1').status_code, 400)
    self.assertEqual(self.client.get('/api/accounting/transactions/999999').status_code, 404)
    self.assertEqual(snapshot()['transactions'][0]['amount'], 1000)
    self.assertIsNone(balances('2026-10')['accounts'][0]['balance'])

  def test_unbalanced_or_unclassified_plan_rejected(self):
    batch = self.ingest()
    p = self.expense(RawRecord.objects.get(transaction_date__isnull=False))
    p['entries'][0]['debit'] = '801'
    with self.assertRaises(ValueError):
      validate_plan(p)
    p['entries'][0]['debit'] = '800'
    p['items'][0]['category'] = '未分類'
    with self.assertRaises(ValueError):
      validate_plan(p)

  def test_mixed_refund_and_purchase_remains_balanced(self):
    self.ingest()
    raw = RawRecord.objects.get(transaction_date__isnull=False)
    p = self.expense(raw)
    p['amount'] = '800'
    p['entries'][0]['debit'] = '1000'
    p['entries'][1].update(debit='0', credit='200')
    p['entries'][2]['credit'] = '800'
    p['items'][0]['amount'] = '1000'
    p['items'][1]['amount'] = '-200'
    p['sources'][0]['linked_amount'] = '800'
    validate_plan(p)

  def test_duplicate_source_causes_atomic_rollback(self):
    batch = self.ingest()
    self.confirm(batch)
    p = deepcopy(batch.decisions.get(kind='transaction').proposal)
    p['key'] = 'double-count'
    apply_review(batch.pk, {'new_plans': [{'proposal': p, 'answer': 'test', 'reason': 'test'}]})
    with self.assertRaises(ValueError):
      publish_batch(batch.pk)
    self.assertFalse(Transaction.objects.exists())
    self.assertFalse(Account.objects.exists())
    batch.refresh_from_db()
    self.assertEqual(batch.status, 'review')

  def test_card_charge_is_transfer_and_not_expense(self):
    batch = self.ingest()
    raw = RawRecord.objects.get(transaction_date__isnull=False)
    p = {'operation': 'upsert', 'key': 'charge', 'date': '2026-10-01', 'kind': 'transfer', 'title': 'Suicaチャージ',
      'amount': '1000', 'currency': 'JPY', 'raw_ids': [raw.pk], 'items': [],
      'entries': [{'account': 'Suica', 'account_type': 'asset', 'debit': '1000', 'credit': '0'},
        {'account': 'カード未払金', 'account_type': 'liability', 'debit': '0', 'credit': '1000'}],
      'sources': [{'raw_record_id': raw.pk, 'role': 'transfer_out', 'linked_amount': '1000'}]}
    self.confirm(batch, {raw.pk: p})
    publish_batch(batch.pk)
    self.assertEqual(self.client.get('/api/accounting/summary').json()['expense'], 0)
    self.assertEqual(self.client.get('/api/accounting/calendar').json()[0]['transfer'], 1000)

  def test_opening_balance_and_month_rollover(self):
    batch = self.ingest()
    self.confirm(batch)
    opening = {'operation': 'upsert', 'key': 'opening-bank', 'date': '2026-09-30', 'kind': 'opening',
      'title': '開始残高', 'amount': '10000', 'currency': 'JPY', 'raw_ids': [], 'items': [], 'sources': [],
      'entries': [{'account': '三井住友銀行', 'account_type': 'asset', 'debit': '10000', 'credit': '0'},
        {'account': '開始残高調整', 'account_type': 'equity', 'debit': '0', 'credit': '10000'}]}
    apply_review(batch.pk, {'new_plans': [{'proposal': opening, 'answer': '架空の開始残高。', 'reason': 'テスト。'}]})
    zero_opening = deepcopy(opening)
    zero_opening.update(key='opening-cash-zero', amount='0', title='現金の開始残高')
    zero_opening['entries'][0].update(account='現金', debit='0')
    zero_opening['entries'][1]['credit'] = '0'
    apply_review(batch.pk, {'new_plans': [{'proposal': zero_opening, 'answer': '架空の開始残高0円。', 'reason': 'テスト。'}]})
    publish_batch(batch.pk)
    self.assertEqual(next(a for a in balances('2026-10')['accounts'] if a['name'] == '三井住友銀行')['balance'], 9000)
    self.assertEqual(next(a for a in balances('2026-12')['accounts'] if a['name'] == '三井住友銀行')['balance'], 9000)
    self.assertEqual(next(a for a in balances('2026-10')['accounts'] if a['name'] == '現金')['balance'], 0)
    self.assertTrue(balances('2026-10')['complete'])
    self.assertEqual(self.client.get('/api/accounting/summary?year=2026').json()['expense'], 1000)

  def test_missing_rows_require_decision_without_auto_deletion(self):
    batch = self.ingest()
    self.confirm(batch)
    publish_batch(batch.pk)
    self.write_rows([['2026/10/02', '500', '', '店B', '8500', '', '']])
    updated = self.ingest()
    self.assertEqual(Transaction.objects.count(), 1)
    self.assertEqual(updated.decisions.filter(kind='missing_row').count(), 1)
    self.assertEqual(snapshot()['transactions'][0]['amount'], 1000)
    folder, _ = export_review(updated.pk)
    questions = [json.loads(line) for line in (folder / 'questions.jsonl').read_text().splitlines()]
    self.assertTrue(any(q['references'][0]['line'] == 2 for q in questions if q['references']))

  def test_backup_retention_and_restore(self):
    batch = self.ingest()
    with writer_lock():
      before = backup_database('test')
    self.confirm(batch)
    publish_batch(batch.pk)
    self.assertEqual(Transaction.objects.count(), 1)
    connections.close_all()
    with writer_lock():
      restore_database(before)
    self.assertEqual(Transaction.objects.count(), 0)
    for _ in range(11):
      with writer_lock():
        backup_database('test')
    self.assertEqual(len(list((self.base / 'backups').glob('*.sqlite3'))), 10)
    for path in (self.base / 'backups').glob('*.sqlite3'):
      check_database(path)
