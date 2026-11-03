from collections import Counter, defaultdict
from decimal import Decimal
import json
from pathlib import Path
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from .backup import backup_database, writer_lock
from .models import Account, Category, Decision, ImportBatch, ImportFile, JournalEntry, RawOccurrence, RawRecord, Transaction, TransactionItem, TransactionSource
from .parsers import parse_file, day, money, VERSION
from .plans import COLORS, category_name, category_account_name, legacy_plan, plan_digest


def json_safe(value):
  return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def load_legacy_snapshot(path=None):
  path = Path(path or settings.BASE_DIR.parent / 'Kyoto_Univ/ui/accounting-data.js')
  text = path.read_text()
  return json.loads(text[text.index('=')+1:].strip().rstrip(';'))


def source_refs(raw_id):
  return [{'file': o.import_file.original_name, 'line': o.line_start, 'lineEnd': o.line_end,
    'rawRecordId': raw_id} for o in RawOccurrence.objects.filter(raw_record_id=raw_id)
    .select_related('import_file').order_by('-batch_id', 'line_start')[:1]]


def archive_legacy_records(batch):
  path = settings.BASE_DIR / 'demo_store/raw_records.json'
  if not path.exists():
    return
  legacy = json.loads(path.read_text())['records']
  existing = set(RawRecord.objects.values_list('dedupe_key', flat=True))
  for key in legacy.keys()-existing:
    record = legacy[key]
    raw = RawRecord.objects.create(source=record['scope'].split(':')[0], dedupe_scope=record['scope'],
      dedupe_key=key, occurrence_number=record['occurrence'],
      raw_data={'columns': [], 'values': record['row'], 'legacy_sources': record['sources']})
    Decision.objects.create(batch=batch, kind='legacy_archive', status='confirmed',
      targets=[{'table': 'raw_records', 'id': raw.pk}],
      proposal={'archived': True, 'inactive': record.get('inactive', False), 'original_sources': record['sources']},
      reason='過去の取り込み台帳にのみ残る元行を監査用に保存。現在の取引として再計上しない。', confirmed_at=timezone.now())


def stage_import(root=None, legacy_path=None, extend_review=None):
  root = Path(root or settings.BASE_DIR / 'csv_raw_data')
  paths = sorted(root.rglob('*.csv'))
  if not paths:
    raise ValueError('CSVがありません。')
  # 全ファイルを先に検査する。1つでも不正ならDBを変更しない。
  files = [parse_file(path, root) for path in paths]
  manifest = {f['original_name']: f['file_hash'] for f in files}
  with writer_lock(), db_transaction.atomic():
    previous = ImportBatch.objects.order_by('-id').first()
    if previous and previous.status != 'failed' and previous.proposed_changes.get('manifest') == manifest and previous.proposed_changes.get('parserVersion', VERSION) == VERSION:
      archive_legacy_records(previous)
      return previous, False
    if previous and previous.status not in {'published', 'failed'}:
      if extend_review == previous.pk:
        return append_review_files(previous, files), False
      raise ValueError(f'更新{previous.id}が確認途中です。先にreviewへ訂正内容を適用するか、abandonしてください。')
    batch = ImportBatch.objects.create(proposed_changes={'schema': 1, 'manifest': manifest, 'parserVersion': VERSION})
    added = 0
    current_ids = set()
    for file_data in files:
      meta = {k: v for k, v in file_data.items() if k != 'rows'}
      file, _ = ImportFile.objects.get_or_create(source=meta['source'], file_hash=meta['file_hash'], original_name=meta['original_name'], defaults=meta)
      for item in file_data['rows']:
        record = item['record']
        raw, created = RawRecord.objects.get_or_create(dedupe_key=record['dedupe_key'], defaults=record)
        if not created:
          changes = {key: value for key, value in record.items() if getattr(raw, key) != value}
          if changes:
            if raw.raw_data.get('legacy_sources') and not raw.links.exists():
              before = json_safe({key: getattr(raw, key) for key in changes})
              for key, value in changes.items():
                setattr(raw, key, value)
              raw.save()
              Decision.objects.create(batch=batch, kind='archive_reimport', status='confirmed',
                targets=[{'table': 'raw_records', 'id': raw.pk}], before=before, after=json_safe(changes),
                reason='アーカイブしていた元行をCSVで再取得。元行の変換のみ更新し、帳簿の再計上は別途確認する。', confirmed_at=timezone.now())
            else:
              raise ValueError(f"{meta['original_name']}：{item['line_start']}行目の保存済み変換値と新ルールが異なります。列対応を確認し、明示的なデータ移行を行ってください。")
        added += created
        current_ids.add(raw.pk)
        RawOccurrence.objects.create(batch=batch, import_file=file, raw_record=raw,
          line_start=item['line_start'], line_end=item['line_end'])
    lookup = dict(RawRecord.objects.values_list('dedupe_key', 'pk'))
    raw_map = RawRecord.objects.in_bulk()
    covered = set(TransactionSource.objects.values_list('raw_record_id', flat=True))
    for old in Decision.objects.filter(kind='transaction', status='confirmed', batch__status='published', proposal__operation='ignore'):
      covered.update(old.proposal.get('raw_ids', []))
    if not Transaction.objects.exists():
      seed = load_legacy_snapshot(legacy_path)
      for row in seed['transactions']:
        plan = legacy_plan(row, lookup)
        for link in plan['sources']:
          raw = raw_map[link['raw_record_id']]
          link['linked_amount'] = str(raw.amount or 0)
          if link['role'] != 'detail' and len([s for s in plan['sources'] if s['role'] != 'detail']) == 1:
            link['linked_amount'] = str(abs(Decimal(plan['amount'])))
          if plan['kind'] == 'transfer':
            link['role'] = 'transfer_in' if raw.direction == 'in' else 'transfer_out'
        # レシート全体と自己負担を混同しない。品目への配賦は行わない。
        if any(i['amount'] is None for i in plan['items']):
          for item in plan['items']:
            item['amount'] = '0'
          totals = row.get('categoryAmounts') or [{'category': row['category'], 'amount': row['amount']}]
          for item in totals:
            plan['items'].append({'category': category_name(item['category']), 'name': '自己負担分',
              'amount': str(item['amount']), 'receipt_amount': None, 'source_raw_record_id': None,
              'store': '', 'subcategory': '', 'position': len(plan['items'])})
        approved = row['status'] == 'ユーザー確認済み' and plan['kind'] != 'pending' and not plan['legacy']['missingReferences']
        if row.get('zaimMatch') and row['zaimMatch']['status'] != 'ユーザー確認済み':
          approved = False
        Decision.objects.create(batch=batch, kind='transaction', status='confirmed' if approved else 'proposed',
          targets=[{'table': 'raw_records', 'id': rid} for rid in plan['raw_ids']], proposal=plan,
          reason='既存デモの保存済み対応を移行。ユーザー承認の有無を区別。',
          user_answer='以前のCodexセッションで承認済み。' if approved else '',
          question='' if approved else '既存案の照合・分類・精算内容を確認してください。',
          confirmed_at=timezone.now() if approved else None)
        covered.update(plan['raw_ids'])
      # 個別回答の原文・変更前後も保持し、旧コードを再実行する必要をなくす。
      history_path = settings.BASE_DIR / 'review/applied_answers.json'
      if history_path.exists():
        Decision.objects.create(batch=batch, kind='legacy_history', status='confirmed',
          proposal=json.loads(history_path.read_text()), reason='旧デモの回答履歴を原文のまま保存。', confirmed_at=timezone.now())
    for source in sorted({f['source'] for f in files}):
      approved = Decision.objects.filter(kind='mapping', status='confirmed', proposal__source=source, proposal__parser_version=VERSION).exists()
      Decision.objects.create(batch=batch, kind='mapping', status='confirmed' if approved else 'proposed',
        proposal={'source': source, 'parser_version': VERSION},
        question='' if approved else f'{source}の列変換を確認してください。',
        reason='CSVの列対応はユーザー確認後に確定する。', confirmed_at=timezone.now() if approved else None)
    for raw_id in sorted(current_ids-covered):
      raw = raw_map[raw_id]
      if not raw.transaction_date:
        continue
      proposal = {'operation': 'review', 'key': raw.dedupe_key, 'raw_ids': [raw.pk],
        'date': str(raw.transaction_date), 'amount': str(raw.amount or 0), 'currency': raw.currency,
        'account_hint': raw.account_hint, 'direction': raw.direction,
        'store': raw.store, 'memo': raw.memo, 'item_name': raw.item_name,
        'category_hint': category_name(raw.category_name), 'source': raw.source,
        'source_transaction_id': raw.source_transaction_id}
      proposal['possible_edit_ids'] = [other.pk for other in raw_map.values() if other.pk != raw.pk
        and other.source == raw.source and ((raw.source_transaction_id and other.source_transaction_id == raw.source_transaction_id)
          or (raw.source == 'zaim' and (other.transaction_date, other.item_name, other.store, other.direction)
            == (raw.transaction_date, raw.item_name, raw.store, raw.direction) and other.raw_data != raw.raw_data))]
      Decision.objects.create(batch=batch, kind='transaction', targets=[{'table': 'raw_records', 'id': raw.pk}],
        proposal=proposal, question='既存決済との対応・分類・資金移動の内容を確認してください。')
    # 消えた行は削除と断定しない。取得範囲の違いも候補として残す。
    if previous:
      old_ids = set(previous.occurrences.filter(raw_record__transaction_date__isnull=False).values_list('raw_record_id', flat=True))
      for raw_id in sorted(old_ids-current_ids):
        Decision.objects.create(batch=batch, kind='missing_row', targets=[{'table': 'raw_records', 'id': raw_id}],
          proposal={'operation': 'review', 'raw_ids': [raw_id]},
          question='今回のCSVにない行です。出力期間外か、訂正・削除かを確認してください。')
    batch.proposed_changes.update(added_records=added, input_records=len(current_ids))
    archive_legacy_records(batch)
    batch.save()
    return batch, True


def append_review_files(batch, files):
  """確認中の承認を維持し、新規ファイルだけを同じ更新へ追加する。"""
  old_manifest = batch.proposed_changes.get('manifest', {})
  manifest = {f['original_name']: f['file_hash'] for f in files}
  if batch.status != 'review' or any(manifest.get(name) != digest for name, digest in old_manifest.items()):
    raise ValueError('確認中の追加取り込みでは、既存ファイルの変更・削除はできません。')
  additions = [f for f in files if f['original_name'] not in old_manifest]
  if not additions:
    return batch
  saved = str(backup_database('before-extend-review'))
  before = dict(batch.proposed_changes)
  covered = {target['id'] for d in batch.decisions.filter(kind='transaction')
    for target in d.targets if target.get('table') == 'raw_records'}
  added = 0
  for file_data in additions:
    meta = {k: v for k, v in file_data.items() if k != 'rows'}
    file, _ = ImportFile.objects.get_or_create(source=meta['source'], original_name=meta['original_name'], file_hash=meta['file_hash'], defaults=meta)
    for item in file_data['rows']:
      record = item['record']
      raw, created = RawRecord.objects.get_or_create(dedupe_key=record['dedupe_key'], defaults=record)
      if not created and any(getattr(raw, key) != value for key, value in record.items()):
        raise ValueError(f"{meta['original_name']}：{item['line_start']}行目の保存済み変換値と一致しません。")
      added += created
      RawOccurrence.objects.get_or_create(batch=batch, import_file=file, line_start=item['line_start'],
        defaults={'raw_record': raw, 'line_end': item['line_end']})
      if raw.transaction_date and raw.pk not in covered:
        Decision.objects.create(batch=batch, kind='transaction', targets=[{'table': 'raw_records', 'id': raw.pk}],
          proposal={'operation': 'review', 'key': raw.dedupe_key, 'raw_ids': [raw.pk],
            'date': str(raw.transaction_date), 'amount': str(raw.amount or 0), 'currency': raw.currency,
            'source': raw.source, 'direction': raw.direction, 'store': raw.store,
            'memo': raw.memo, 'item_name': raw.item_name, 'account_hint': raw.account_hint},
          question='追加CSVの決済対応・内訳・ポイントの意味を確認してください。')
        covered.add(raw.pk)
    if not batch.decisions.filter(kind='mapping', proposal__source=meta['source']).exists():
      Decision.objects.create(batch=batch, kind='mapping', proposal={'source': meta['source'], 'parser_version': VERSION},
        question=f"{meta['source']}の列変換を確認してください。")
  batch.proposed_changes.update(manifest=manifest,
    added_records=batch.proposed_changes.get('added_records', 0)+added,
    input_records=batch.occurrences.values('raw_record_id').distinct().count())
  batch.save(update_fields=['proposed_changes'])
  Decision.objects.create(batch=batch, kind='import_extension', status='confirmed', before=before,
    after=batch.proposed_changes, proposal={'new_files': [f['original_name'] for f in additions],
      'added_records': added, 'backup': saved},
    reason='ユーザーが追加したCSVを確認中の更新へ登録。既存承認を維持し、新しい取引は未承認として保存。', confirmed_at=timezone.now())
  return batch


def validate_plan(plan):
  operation = plan.get('operation')
  if operation == 'ignore':
    if not plan.get('raw_ids') or not plan.get('reason'):
      raise ValueError('計上しない理由と対象元行が必要です。')
    return
  if operation == 'delete':
    if not plan.get('key') or not plan.get('reason'):
      raise ValueError('削除対象と理由が必要です。')
    return
  if operation != 'upsert' or plan.get('kind') not in {'expense', 'income', 'transfer', 'opening'}:
    raise ValueError('取引内容が未確定です。')
  day(plan['date'])
  if not plan.get('key') or not plan.get('title') or plan.get('currency') != 'JPY':
    raise ValueError('取引キー・タイトル・円通貨の指定が必要です。')
  total = money(plan['amount'])
  zero_receipt = plan['kind'] in {'expense', 'income'} and any(money(i.get('amount', 0)) > 0 for i in plan.get('items', [])) and any(money(i.get('amount', 0)) < 0 for i in plan.get('items', []))
  if (not total and plan['kind'] != 'opening' and not zero_receipt) or (plan['kind'] in {'transfer', 'opening'} and total < 0):
    raise ValueError('取引金額が不正です。')
  entries = plan.get('entries', [])
  if len(entries) < 2:
    raise ValueError('仕訳が不足しています。')
  debit = credit = Decimal(0)
  typed = {}
  for e in entries:
    d, c = money(e['debit']), money(e['credit'])
    if not ((d > 0 and c == 0) or (c > 0 and d == 0) or (plan['kind'] == 'opening' and total == 0 and d == c == 0)):
      raise ValueError('仕訳は借方・貸方の一方だけを正数にします。')
    if not e.get('account') or e.get('account_type') not in {'asset', 'liability', 'equity', 'income', 'expense'}:
      raise ValueError('勘定と区分を指定してください。')
    if e['account'] in typed and typed[e['account']] != e['account_type']:
      raise ValueError('同じ勘定の区分が一致しません。')
    typed[e['account']] = e['account_type']
    debit += d
    credit += c
  if debit != credit:
    raise ValueError('借方・貸方が一致しません。')
  if plan['kind'] in {'transfer', 'opening'} and debit != abs(total):
    raise ValueError('振替・開始残高の仕訳と取引金額が一致しません。')
  allowed_types = {'expense': {'expense', 'asset', 'liability'}, 'income': {'income', 'asset', 'liability'},
    'transfer': {'asset', 'liability'}, 'opening': {'asset', 'liability', 'equity'}}[plan['kind']]
  if not set(typed.values()) <= allowed_types:
    raise ValueError('取引の種類と勘定区分が一致しません。')
  if plan['kind'] == 'opening' and ('equity' not in typed.values() or not set(typed.values()) & {'asset', 'liability'}):
    raise ValueError('開始残高には資産・負債と純資産の勘定が必要です。')
  items = plan.get('items', [])
  if plan['kind'] in {'income', 'expense'}:
    if not items or sum((money(i['amount']) for i in items), Decimal(0)) != total:
      raise ValueError('内訳の合計と取引金額が一致しません。')
    by_category = defaultdict(Decimal)
    for item in items:
      name = category_name(item.get('category', ''))
      if not name or name in {'未分類', '未照合', '用途未確認', '振替'}:
        raise ValueError('未分類の内訳は確定できません。')
      if name == '不明' and plan.get('unknown_category_authorized') is not True:
        raise ValueError('不明カテゴリはユーザーが明示的に許可した取引だけ使用できます。')
      by_category[name] += money(item['amount'])
    for name, amount in by_category.items():
      e = [e for e in entries if e['account'] == category_account_name(name, plan['kind']) and e['account_type'] == plan['kind']]
      signed = sum((money(x['debit'])-money(x['credit']) for x in e), Decimal(0))
      if signed != (amount if plan['kind'] == 'expense' else -amount):
        raise ValueError('カテゴリ別の内訳と仕訳が一致しません。')
    used_categories = {'不明' if e['account'] == '不明（収入）' else e['account']
      for e in entries if e['account_type'] == plan['kind']}
    if used_categories-set(by_category) or {name for name, value in by_category.items() if value}-used_categories:
      raise ValueError('内訳にない収益・費用勘定が含まれています。')
  elif items:
    raise ValueError('振替・開始残高には収支内訳を登録しません。')
  source_ids = [s['raw_record_id'] for s in plan.get('sources', [])]
  declared = set(plan.get('raw_ids', []))
  if not set(source_ids) <= declared:
    raise ValueError('対応元行がraw_idsにありません。')
  if len(source_ids) != len(set(source_ids)):
    raise ValueError('1取引に同じ元行が重複しています。')
  if RawRecord.objects.filter(pk__in=declared).count() != len(declared):
    raise ValueError('存在しない元行です。')
  for item in items:
    if item.get('source_raw_record_id') and item['source_raw_record_id'] not in source_ids:
      raise ValueError('品目の元行が対応表にありません。')
  for s in plan.get('sources', []):
    if s.get('role') not in {'payment', 'detail', 'transfer_in', 'transfer_out', 'bill_detail'}:
      raise ValueError('対応元行の役割が不正です。')
    money(s['linked_amount'])


def check_review_mode(item, proposal, cutoff):
  if item.get('approval_mode') != 'rule' or not cutoff:
    return
  if proposal.get('date', '') >= cutoff or RawRecord.objects.filter(
      pk__in=proposal.get('raw_ids', []), transaction_date__gte=cutoff).exists():
    raise ValueError('この日付以降の取引には個別確認が必要です。同種ルールだけでは承認できません。')


def apply_review(batch_id, document):
  if document.get('preview_only') or document.get('authorization') or 'proposals' in document:
    raise ValueError('参考案や一括委任の記録は承認として適用できません。照合・分類についてユーザーの回答を指定してください。')
  policy_path = settings.BASE_DIR / 'review_policy.json'
  policy = json.loads(policy_path.read_text()) if policy_path.exists() else {}
  cutoff = policy.get('rules', {}).get('explicitReviewFrom')
  with writer_lock(), db_transaction.atomic():
    batch = ImportBatch.objects.get(pk=batch_id)
    if batch.status != 'review':
      raise ValueError('確認中の更新だけ変更できます。')
    for answer in document.get('answers', []):
      decision = batch.decisions.get(pk=answer['decision_id'])
      if not answer.get('reason') or not answer.get('answer'):
        raise ValueError('判断理由と回答または確認根拠が必要です。')
      if answer.get('expected_digest') != plan_digest(decision.proposal):
        raise ValueError('確認対象の案が変わっています。最新のexportを確認してください。')
      proposal = answer.get('proposal', decision.proposal)
      check_review_mode(answer, proposal, cutoff)
      if decision.kind == 'transaction':
        validate_plan(proposal)
      elif decision.kind == 'missing_row':
        if proposal.get('operation') not in {'ignore', 'delete'} or not proposal.get('reason'):
          raise ValueError('欠落行の扱いと理由が必要です。')
        validate_plan(proposal)
      elif decision.kind == 'mapping' and proposal != decision.proposal:
        raise ValueError('列変換はコードの修正と再取り込みが必要です。')
      Decision.objects.create(batch=batch, kind='review_history', status='confirmed', targets=decision.targets,
        before=decision.proposal, after=proposal, user_answer=answer['answer'], reason=answer['reason'], confirmed_at=timezone.now())
      decision.proposal, decision.status = proposal, 'confirmed'
      decision.targets = [{'table': 'raw_records', 'id': rid} for rid in proposal.get('raw_ids', [])]
      decision.user_answer, decision.reason, decision.confirmed_at = answer['answer'], answer['reason'], timezone.now()
      decision.save()
    for item in document.get('new_plans', []):
      if not item.get('answer') or not item.get('reason'):
        raise ValueError('追加案には回答と理由が必要です。')
      proposal = item['proposal']
      check_review_mode(item, proposal, cutoff)
      validate_plan(proposal)
      if batch.decisions.filter(kind='transaction', proposal__key=proposal.get('key')).exists():
        raise ValueError('同じキーの案が既にあります。既存のdecision_idを指定してください。')
      Decision.objects.create(batch=batch, kind='transaction', status='confirmed', proposal=proposal,
        targets=[{'table': 'raw_records', 'id': rid} for rid in proposal.get('raw_ids', [])],
        reason=item['reason'], user_answer=item['answer'], confirmed_at=timezone.now())
    # 複数案を1件へ統合した際など、残りの案は明示的なignore判断で閉じる。
    return batch


def transaction_state(tx):
  return {'id': tx.pk, 'key': tx.identity_key, 'date': str(tx.date), 'kind': tx.kind,
    'title': tx.title, 'amount': str(tx.amount), 'currency': tx.currency,
    'entries': list(tx.entries.values('account__name', 'account__type', 'debit', 'credit', 'position')),
    'items': list(tx.items.values('category__name', 'name', 'store', 'subcategory', 'amount', 'receipt_amount', 'source_raw_record_id', 'position')),
    'sources': list(tx.sources.values('raw_record_id', 'role', 'linked_amount'))}


def publish_batch(batch_id):
  with writer_lock():
    batch = ImportBatch.objects.get(pk=batch_id)
    if batch.status != 'review' or batch.decisions.exclude(status='confirmed').exists():
      raise ValueError('未確認の判断が残っています。すべて確認してから反映してください。')
    plans = list(batch.decisions.filter(kind='transaction'))
    for decision in plans:
      validate_plan(decision.proposal)
    keys = [d.proposal['key'] for d in plans if d.proposal['operation'] in {'upsert', 'delete'}]
    if len(keys) != len(set(keys)):
      raise ValueError('同じ取引の変更案が複数あります。')
    backup = backup_database()
    with db_transaction.atomic():
      for decision in plans + list(batch.decisions.filter(kind='missing_row')):
        p = decision.proposal
        if p['operation'] == 'ignore':
          continue
        old = Transaction.objects.filter(identity_key=p['key']).first()
        before = transaction_state(old) if old else None
        if p['operation'] == 'delete':
          if not old:
            raise ValueError('削除する取引がありません。')
          old.delete()
          after = None
        else:
          tx, _ = Transaction.objects.update_or_create(identity_key=p['key'], defaults={
            'date': p['date'], 'kind': p['kind'], 'title': p['title'], 'amount': p['amount'],
            'currency': p['currency'], 'last_batch': batch})
          tx.entries.all().delete()
          tx.items.all().delete()
          tx.sources.all().delete()
          accounts = {}
          for i, e in enumerate(p['entries']):
            account, created = Account.objects.get_or_create(name=e['account'], defaults={'type': e['account_type']})
            if account.type != e['account_type']:
              raise ValueError('既存勘定の区分と一致しません。')
            accounts[account.name] = account
            JournalEntry.objects.create(transaction=tx, account=account, debit=e['debit'], credit=e['credit'], position=i)
            if p['kind'] == 'opening' and account.type in {'asset', 'liability'}:
              if Transaction.objects.filter(kind='opening', entries__account=account).exclude(pk=tx.pk).exists():
                raise ValueError('同じ口座に開始仕訳が複数あります。')
              account.balance_start_date = p['date']
              account.save()
          for i, item in enumerate(p.get('items', [])):
            name = category_name(item['category'])
            account_name = category_account_name(name, p['kind'])
            account = accounts.get(account_name)
            if not account:
              # 立替レシートの集計対象外品目も、対応する費用勘定を持つ。
              account, _ = Account.objects.get_or_create(name=account_name, defaults={'type': p['kind']})
            category, _ = Category.objects.get_or_create(name=name, defaults={'color': COLORS.get(name, '#a4a4a4'), 'account': account})
            TransactionItem.objects.create(transaction=tx, category=category, name=item['name'], store=item.get('store', ''),
              subcategory=item.get('subcategory', ''), amount=item['amount'], receipt_amount=item.get('receipt_amount'),
              source_raw_record_id=item.get('source_raw_record_id'), position=i)
          for s in p.get('sources', []):
            TransactionSource.objects.create(transaction=tx, raw_record_id=s['raw_record_id'], role=s['role'], linked_amount=s['linked_amount'])
          after = transaction_state(tx)
        decision.before, decision.after = json_safe(before), json_safe(after)
        decision.save()
      # すべての今回のデータ行に、確定対応または明示的な非計上理由を要求する。
      required = set(batch.occurrences.filter(raw_record__transaction_date__isnull=False).values_list('raw_record_id', flat=True))
      accounted = set(TransactionSource.objects.values_list('raw_record_id', flat=True))
      for d in Decision.objects.filter(status='confirmed').filter(batch__status='published') | batch.decisions.filter(status='confirmed'):
        if d.proposal.get('operation') == 'ignore':
          accounted.update(d.proposal.get('raw_ids', []))
      if required-accounted:
        raise ValueError(f'対応または非計上理由のない元行が{len(required-accounted)}件あります。')
      # 同じ元行の二重計上を、役割ごとに金額で検査する。
      used = defaultdict(Decimal)
      for link in TransactionSource.objects.select_related('raw_record'):
        # 同じ行を役割名だけ変えて重ねて使うことも防ぐ。
        key = link.raw_record_id
        used[key] += abs(link.linked_amount)
        if used[key] > abs(link.raw_record.amount or 0):
          raise ValueError(f'元行{link.raw_record_id}の対応金額が元金額を超えています。')
      for account in Account.objects.filter(type__in=['asset', 'liability']):
        dates = list(Transaction.objects.filter(kind='opening', entries__account=account).values_list('date', flat=True).distinct())
        if len(dates) > 1:
          raise ValueError('同じ口座に開始仕訳が複数あります。')
        account.balance_start_date = dates[0] if dates else None
        account.save(update_fields=['balance_start_date'])
      batch.status, batch.published_at, batch.backup_path = 'published', timezone.now(), str(backup)
      batch.save()
    return batch


def export_review(batch_id, folder=None):
  batch = ImportBatch.objects.get(pk=batch_id)
  folder = Path(folder or settings.BASE_DIR / 'review/generated' / f'batch-{batch.pk}')
  folder.mkdir(parents=True, exist_ok=True)
  counts = Counter()
  readable = [f'# 更新{batch.pk}の確認事項', '',
    '未確認の判断を全件掲載する。複数の候補は同じ決済とは限らない。元資料を見てCodexセッションで確認する。', '',
    '最初にcolumn_mapping.mdとmapping_examples.jsonで各サービスの列対応を確認する。', '']
  with (folder / 'questions.jsonl').open('w') as handle:
    for d in batch.decisions.order_by('id'):
      counts[f'{d.kind}:{d.status}'] += 1
      if d.status == 'confirmed':
        continue
      ids = [t['id'] for t in d.targets if t.get('table') == 'raw_records']
      references = [r for rid in ids for r in source_refs(rid)]
      handle.write(json.dumps({'decision_id': d.pk, 'kind': d.kind, 'question': d.question,
        'expected_digest': plan_digest(d.proposal), 'references': references,
        'proposal': d.proposal}, ensure_ascii=False)+'\n')
      readable += [f'## Q{d.pk}：{d.kind}', '', d.question, '',
        ' / '.join(f"{r['file']}：{r['line']}行目" for r in references) or 'サービス共通の変換ルール。', '',
        '```json', json.dumps(d.proposal, ensure_ascii=False, indent=2), '```', '']
  (folder / 'summary.json').write_text(json.dumps({'batch_id': batch.pk, 'status': batch.status,
    'counts': dict(counts), 'import': batch.proposed_changes}, ensure_ascii=False, indent=2)+'\n')
  (folder / 'answers.template.json').write_text(json.dumps({'batch_id': batch.pk, 'answers': []}, indent=2)+'\n')
  (folder / 'questions.md').write_text('\n'.join(readable)+'\n')
  # 同日同額の候補と、連続するZaim品目群の合計候補を提示するだけで確定しない。
  raws = list(RawRecord.objects.filter(transaction_date__isnull=False).order_by('id'))
  by_amount = defaultdict(list)
  for r in raws:
    by_amount[abs(r.amount or 0)].append(r)
  candidates = []
  for raw in raws:
    matches = [r.pk for r in by_amount[abs(raw.amount or 0)] if r.source != raw.source
      and abs((r.transaction_date-raw.transaction_date).days) <= 3]
    if matches:
      candidates.append({'raw_ids': [raw.pk], 'candidate_ids': matches, 'basis': '日付差3日以内・同額。未確定。'})
  zaim = sorted((r for r in raws if r.source == 'zaim'), key=lambda r: r.pk)
  groups = []
  for raw in zaim:
    if not groups or (groups[-1][-1].transaction_date, groups[-1][-1].store, groups[-1][-1].direction) != (raw.transaction_date, raw.store, raw.direction):
      groups.append([])
    groups[-1].append(raw)
  for group in groups:
    if len(group) < 2:
      continue
    value = abs(sum((r.amount or Decimal(0) for r in group), Decimal(0)))
    matches = [r.pk for r in by_amount[value] if r.source != 'zaim' and abs((r.transaction_date-group[0].transaction_date).days) <= 3]
    candidates.append({'raw_ids': [r.pk for r in group], 'total': str(value), 'candidate_ids': matches,
      'basis': '連続する同日・同店・同方法のZaim行の合計。レシートの区切りは未確定。'})
  (folder / 'matching_candidates.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2)+'\n')
  samples = {}
  for o in batch.occurrences.filter(raw_record__transaction_date__isnull=False).select_related('raw_record', 'import_file').order_by('id'):
    signature = (o.raw_record.source, len(o.raw_record.raw_data['values']))
    if signature not in samples:
      samples[signature] = {'file': o.import_file.original_name, 'line_start': o.line_start, 'line_end': o.line_end,
        'raw': o.raw_record.raw_data, 'converted': {f.name: getattr(o.raw_record, f.name) for f in RawRecord._meta.fields if f.name != 'raw_data'}}
  (folder / 'mapping_examples.json').write_text(json.dumps(list(samples.values()), ensure_ascii=False, indent=2, default=str)+'\n')
  return folder, dict(counts)
