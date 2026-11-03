import json
from pathlib import Path
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, connections, transaction
from django.db.migrations.executor import MigrationExecutor
from ledger.backup import backup_database, restore_database, writer_lock
from ledger.models import Decision, ImportBatch, RawRecord, Transaction
from ledger.services import apply_review, export_review, publish_batch, stage_import
from ledger.reconciliation import Reconciler


class Command(BaseCommand):
  help = '家計の取り込み、セッション確認、確定、バックアップ。HTTPからの書き込みは行いません。'

  def add_arguments(self, parser):
    actions = parser.add_subparsers(dest='action', required=True)
    ingest = actions.add_parser('ingest')
    ingest.add_argument('--root')
    ingest.add_argument('--legacy-snapshot')
    ingest.add_argument('--extend-review', type=int)
    for name in ['export', 'publish', 'abandon']:
      sub = actions.add_parser(name)
      sub.add_argument('batch', type=int)
    review = actions.add_parser('review')
    review.add_argument('file')
    reconcile = actions.add_parser('reconcile')
    reconcile.add_argument('batch', type=int)
    coop = actions.add_parser('coop-preview')
    coop.add_argument('batch', type=int)
    actions.add_parser('status')
    actions.add_parser('audit-duplicates')
    actions.add_parser('cash-withdrawals')
    actions.add_parser('backup')
    actions.add_parser('migrate-safe')
    restore = actions.add_parser('restore')
    restore.add_argument('file')
    restore.add_argument('--server-stopped', action='store_true', required=True)

  def handle(self, *args, **options):
    try:
      action = options['action']
      if action == 'ingest':
        batch, created = stage_import(options['root'], options['legacy_snapshot'], options['extend_review'])
        folder, counts = export_review(batch.pk)
        result = {'batch': batch.pk, 'new_batch': created, 'review_folder': str(folder), 'counts': counts}
      elif action == 'cash-withdrawals':
        from ledger.cash_review import withdrawals
        rows = withdrawals()
        result = {'minimum_amount':10000,'withdrawals':rows,'questions_needed':sum(r['needs_user_answer'] for r in rows)}
      elif action == 'audit-duplicates':
        from django.conf import settings
        from ledger.duplicate_audit import audit
        with transaction.atomic():
          document = audit()
        folder = settings.BASE_DIR / 'review/generated/duplicate-audits'
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / 'latest.json'
        path.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n')
        result = {'path': str(path), 'read_only': True,
          **{k: document[k] for k in ['transactions_checked', 'candidate_count', 'candidate_types', 'integrity_errors']}}
      elif action == 'export':
        folder, counts = export_review(options['batch'])
        result = {'folder': str(folder), 'counts': counts}
      elif action == 'review':
        document = json.loads(Path(options['file']).read_text())
        batch = apply_review(document['batch_id'], document)
        folder, counts = export_review(batch.pk)
        result = {'batch': batch.pk, 'folder': str(folder), 'counts': counts}
      elif action == 'publish':
        batch = publish_batch(options['batch'])
        result = {'batch': batch.pk, 'status': batch.status, 'backup': batch.backup_path}
      elif action == 'reconcile':
        document = Reconciler(options['batch']).build()
        from django.conf import settings
        folder = settings.BASE_DIR / 'review/generated' / f"batch-{options['batch']}"
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / 'reconciliation_proposals.json'
        output.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n')
        result = {'batch': options['batch'], 'status': 'preview_only', 'path': str(output), 'summary': document['reconciliation_summary']}
      elif action == 'coop-preview':
        from django.conf import settings
        from ledger.coop import preview
        document = preview(options['batch'])
        folder = settings.BASE_DIR / 'review/generated' / f"batch-{options['batch']}"
        folder.mkdir(parents=True, exist_ok=True)
        output = folder / 'coop_preview.json'
        output.write_text(json.dumps(document, ensure_ascii=False, indent=2)+'\n')
        result = {'path': str(output), 'summary': document['summary'], 'preview_only': True}
      elif action == 'abandon':
        with writer_lock(), transaction.atomic():
          batch = ImportBatch.objects.get(pk=options['batch'])
          if batch.status != 'review':
            raise ValueError('確認中の更新だけ中止できます。')
          batch.status, batch.error_message = 'failed', 'セッションで更新を中止。元資料・判断履歴は保持。'
          batch.save()
        result = {'batch': batch.pk, 'status': batch.status}
      elif action == 'backup':
        with writer_lock():
          result = {'backup': str(backup_database('manual'))}
      elif action == 'restore':
        with writer_lock():
          connections.close_all()
          restore_database(options['file'])
        result = {'restored': options['file']}
      elif action == 'migrate-safe':
        with writer_lock():
          executor = MigrationExecutor(connection)
          pending = executor.migration_plan(executor.loader.graph.leaf_nodes())
          tables = set(connection.introspection.table_names())
          saved = str(backup_database('before-migrate')) if pending and 'transactions' in tables else None
          call_command('migrate', interactive=False, verbosity=0)
        result = {'schema': 'current', 'backup': saved}
      else:
        latest = ImportBatch.objects.order_by('-id').first()
        result = {'raw_records': RawRecord.objects.count(), 'published_transactions': Transaction.objects.count(),
          'latest_batch': latest.pk if latest else None, 'status': latest.status if latest else None,
          'pending_decisions': latest.decisions.exclude(status='confirmed').count() if latest else 0}
      self.stdout.write(json.dumps(result, ensure_ascii=False, indent=2))
    except (ValueError, KeyError, OSError, ImportBatch.DoesNotExist, Decision.DoesNotExist) as error:
      raise CommandError(str(error)) from error
