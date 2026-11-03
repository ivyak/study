import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

  initial = True

  dependencies = [
  ]

  operations = [
    migrations.CreateModel(
      name='Account',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('name', models.CharField(max_length=160, unique=True)),
        ('type', models.CharField(choices=[('asset', 'asset'), ('liability', 'liability'), ('equity', 'equity'), ('income', 'income'), ('expense', 'expense')], max_length=16)),
        ('currency', models.CharField(default='JPY', max_length=8)),
        ('balance_start_date', models.DateField(null=True)),
      ],
      options={
        'db_table': 'accounts',
      },
    ),
    migrations.CreateModel(
      name='ImportBatch',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('status', models.CharField(default='review', max_length=24)),
        ('started_at', models.DateTimeField(auto_now_add=True)),
        ('published_at', models.DateTimeField(null=True)),
        ('proposed_changes', models.JSONField(default=dict)),
        ('backup_path', models.TextField(blank=True)),
        ('error_message', models.TextField(blank=True)),
      ],
      options={
        'db_table': 'import_batches',
      },
    ),
    migrations.CreateModel(
      name='RawRecord',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('source', models.CharField(max_length=80)),
        ('dedupe_scope', models.CharField(max_length=160)),
        ('dedupe_key', models.CharField(max_length=100, unique=True)),
        ('occurrence_number', models.PositiveIntegerField()),
        ('source_transaction_id', models.CharField(blank=True, max_length=160)),
        ('raw_data', models.JSONField()),
        ('transaction_date', models.DateField(db_index=True, null=True)),
        ('amount', models.DecimalField(decimal_places=2, max_digits=18, null=True)),
        ('currency', models.CharField(default='JPY', max_length=8)),
        ('direction', models.CharField(default='unknown', max_length=16)),
        ('account_hint', models.CharField(blank=True, max_length=160)),
        ('counterparty_hint', models.CharField(blank=True, max_length=160)),
        ('store', models.TextField(blank=True)),
        ('memo', models.TextField(blank=True)),
        ('item_name', models.TextField(blank=True)),
        ('category_name', models.CharField(blank=True, max_length=120)),
        ('subcategory_name', models.CharField(blank=True, max_length=160)),
        ('billing_month', models.CharField(blank=True, max_length=7)),
        ('balance', models.DecimalField(decimal_places=2, max_digits=18, null=True)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
      ],
      options={
        'db_table': 'raw_records',
      },
    ),
    migrations.CreateModel(
      name='Category',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('name', models.CharField(max_length=120, unique=True)),
        ('color', models.CharField(default='#a4a4a4', max_length=7)),
        ('position', models.PositiveIntegerField(default=0)),
        ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ledger.account')),
      ],
      options={
        'db_table': 'categories',
      },
    ),
    migrations.CreateModel(
      name='Decision',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('kind', models.CharField(max_length=32)),
        ('status', models.CharField(default='proposed', max_length=16)),
        ('targets', models.JSONField(default=list)),
        ('proposal', models.JSONField(default=dict)),
        ('reason', models.TextField(blank=True)),
        ('question', models.TextField(blank=True)),
        ('user_answer', models.TextField(blank=True)),
        ('before', models.JSONField(null=True)),
        ('after', models.JSONField(null=True)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('confirmed_at', models.DateTimeField(null=True)),
        ('batch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='decisions', to='ledger.importbatch')),
      ],
      options={
        'db_table': 'decisions',
      },
    ),
    migrations.CreateModel(
      name='ImportFile',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('source', models.CharField(max_length=80)),
        ('original_name', models.TextField()),
        ('file_hash', models.CharField(max_length=64)),
        ('encoding', models.CharField(max_length=24)),
        ('parser_version', models.CharField(max_length=32)),
        ('imported_at', models.DateTimeField(auto_now_add=True)),
      ],
      options={
        'db_table': 'import_files',
        'constraints': [models.UniqueConstraint(fields=('source', 'file_hash', 'original_name'), name='unique_source_file')],
      },
    ),
    migrations.CreateModel(
      name='Transaction',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('identity_key', models.CharField(max_length=160, unique=True)),
        ('date', models.DateField(db_index=True)),
        ('kind', models.CharField(choices=[('expense', 'expense'), ('income', 'income'), ('transfer', 'transfer'), ('opening', 'opening')], max_length=16)),
        ('title', models.TextField()),
        ('amount', models.DecimalField(decimal_places=2, max_digits=18)),
        ('currency', models.CharField(default='JPY', max_length=8)),
        ('created_at', models.DateTimeField(auto_now_add=True)),
        ('updated_at', models.DateTimeField(auto_now=True)),
        ('last_batch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ledger.importbatch')),
      ],
      options={
        'db_table': 'transactions',
      },
    ),
    migrations.CreateModel(
      name='TransactionItem',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('name', models.TextField()),
        ('store', models.TextField(blank=True)),
        ('subcategory', models.CharField(blank=True, max_length=160)),
        ('amount', models.DecimalField(decimal_places=2, max_digits=18)),
        ('receipt_amount', models.DecimalField(decimal_places=2, max_digits=18, null=True)),
        ('position', models.PositiveIntegerField(default=0)),
        ('category', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ledger.category')),
        ('source_raw_record', models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT, to='ledger.rawrecord')),
        ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='items', to='ledger.transaction')),
      ],
      options={
        'db_table': 'transaction_items',
      },
    ),
    migrations.CreateModel(
      name='RawOccurrence',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('line_start', models.PositiveIntegerField()),
        ('line_end', models.PositiveIntegerField()),
        ('batch', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='occurrences', to='ledger.importbatch')),
        ('import_file', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='occurrences', to='ledger.importfile')),
        ('raw_record', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='occurrences', to='ledger.rawrecord')),
      ],
      options={
        'db_table': 'raw_occurrences',
        'constraints': [models.UniqueConstraint(fields=('batch', 'import_file', 'line_start'), name='unique_batch_file_line')],
      },
    ),
    migrations.CreateModel(
      name='JournalEntry',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('debit', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
        ('credit', models.DecimalField(decimal_places=2, default=0, max_digits=18)),
        ('position', models.PositiveIntegerField(default=0)),
        ('account', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to='ledger.account')),
        ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='entries', to='ledger.transaction')),
      ],
      options={
        'db_table': 'journal_entries',
        'constraints': [models.CheckConstraint(condition=models.Q(models.Q(('credit', 0), ('debit__gt', 0)), models.Q(('credit__gt', 0), ('debit', 0)), _connector='OR'), name='one_positive_journal_side')],
      },
    ),
    migrations.CreateModel(
      name='TransactionSource',
      fields=[
        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
        ('role', models.CharField(max_length=32)),
        ('linked_amount', models.DecimalField(decimal_places=2, max_digits=18)),
        ('raw_record', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name='links', to='ledger.rawrecord')),
        ('transaction', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sources', to='ledger.transaction')),
      ],
      options={
        'db_table': 'transaction_sources',
        'constraints': [models.UniqueConstraint(fields=('transaction', 'raw_record', 'role'), name='unique_transaction_source_role')],
      },
    ),
  ]
