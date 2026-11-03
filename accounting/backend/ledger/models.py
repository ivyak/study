from django.db import models
from django.db.models import Q


class ImportBatch(models.Model):
  status = models.CharField(max_length=24, default='review')
  started_at = models.DateTimeField(auto_now_add=True)
  published_at = models.DateTimeField(null=True)
  proposed_changes = models.JSONField(default=dict)
  backup_path = models.TextField(blank=True)
  error_message = models.TextField(blank=True)

  class Meta:
    db_table = 'import_batches'


class ImportFile(models.Model):
  source = models.CharField(max_length=80)
  original_name = models.TextField()
  file_hash = models.CharField(max_length=64)
  encoding = models.CharField(max_length=24)
  parser_version = models.CharField(max_length=32)
  imported_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    db_table = 'import_files'
    constraints = [models.UniqueConstraint(fields=['source', 'file_hash', 'original_name'], name='unique_source_file')]


class RawRecord(models.Model):
  source = models.CharField(max_length=80)
  dedupe_scope = models.CharField(max_length=160)
  dedupe_key = models.CharField(max_length=100, unique=True)
  occurrence_number = models.PositiveIntegerField()
  source_transaction_id = models.CharField(max_length=160, blank=True)
  raw_data = models.JSONField()
  transaction_date = models.DateField(null=True, db_index=True)
  amount = models.DecimalField(max_digits=18, decimal_places=2, null=True)
  currency = models.CharField(max_length=8, default='JPY')
  direction = models.CharField(max_length=16, default='unknown')
  account_hint = models.CharField(max_length=160, blank=True)
  counterparty_hint = models.CharField(max_length=160, blank=True)
  store = models.TextField(blank=True)
  memo = models.TextField(blank=True)
  item_name = models.TextField(blank=True)
  category_name = models.CharField(max_length=120, blank=True)
  subcategory_name = models.CharField(max_length=160, blank=True)
  billing_month = models.CharField(max_length=7, blank=True)
  balance = models.DecimalField(max_digits=18, decimal_places=2, null=True)
  created_at = models.DateTimeField(auto_now_add=True)

  class Meta:
    db_table = 'raw_records'


class RawOccurrence(models.Model):
  batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name='occurrences')
  import_file = models.ForeignKey(ImportFile, on_delete=models.PROTECT, related_name='occurrences')
  raw_record = models.ForeignKey(RawRecord, on_delete=models.PROTECT, related_name='occurrences')
  line_start = models.PositiveIntegerField()
  line_end = models.PositiveIntegerField()

  class Meta:
    db_table = 'raw_occurrences'
    constraints = [models.UniqueConstraint(fields=['batch', 'import_file', 'line_start'], name='unique_batch_file_line')]


class Account(models.Model):
  name = models.CharField(max_length=160, unique=True)
  type = models.CharField(max_length=16, choices=[(x, x) for x in ['asset', 'liability', 'equity', 'income', 'expense']])
  currency = models.CharField(max_length=8, default='JPY')
  balance_start_date = models.DateField(null=True)

  class Meta:
    db_table = 'accounts'


class Category(models.Model):
  name = models.CharField(max_length=120, unique=True)
  color = models.CharField(max_length=7, default='#a4a4a4')
  account = models.ForeignKey(Account, on_delete=models.PROTECT)
  position = models.PositiveIntegerField(default=0)

  class Meta:
    db_table = 'categories'


class Transaction(models.Model):
  identity_key = models.CharField(max_length=160, unique=True)
  date = models.DateField(db_index=True)
  kind = models.CharField(max_length=16, choices=[(x, x) for x in ['expense', 'income', 'transfer', 'opening']])
  title = models.TextField()
  amount = models.DecimalField(max_digits=18, decimal_places=2)
  currency = models.CharField(max_length=8, default='JPY')
  last_batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT)
  created_at = models.DateTimeField(auto_now_add=True)
  updated_at = models.DateTimeField(auto_now=True)

  class Meta:
    db_table = 'transactions'


class TransactionItem(models.Model):
  transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='items')
  category = models.ForeignKey(Category, on_delete=models.PROTECT)
  source_raw_record = models.ForeignKey(RawRecord, null=True, on_delete=models.PROTECT)
  name = models.TextField()
  store = models.TextField(blank=True)
  subcategory = models.CharField(max_length=160, blank=True)
  amount = models.DecimalField(max_digits=18, decimal_places=2)
  receipt_amount = models.DecimalField(max_digits=18, decimal_places=2, null=True)
  position = models.PositiveIntegerField(default=0)

  class Meta:
    db_table = 'transaction_items'


class JournalEntry(models.Model):
  transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='entries')
  account = models.ForeignKey(Account, on_delete=models.PROTECT)
  debit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
  credit = models.DecimalField(max_digits=18, decimal_places=2, default=0)
  position = models.PositiveIntegerField(default=0)

  class Meta:
    db_table = 'journal_entries'
    constraints = [models.CheckConstraint(condition=(Q(debit__gt=0, credit=0) | Q(credit__gt=0, debit=0) | Q(debit=0, credit=0)), name='nonnegative_journal_side')]


class TransactionSource(models.Model):
  transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='sources')
  raw_record = models.ForeignKey(RawRecord, on_delete=models.PROTECT, related_name='links')
  role = models.CharField(max_length=32)
  linked_amount = models.DecimalField(max_digits=18, decimal_places=2)

  class Meta:
    db_table = 'transaction_sources'
    constraints = [models.UniqueConstraint(fields=['transaction', 'raw_record', 'role'], name='unique_transaction_source_role')]


class Decision(models.Model):
  batch = models.ForeignKey(ImportBatch, on_delete=models.PROTECT, related_name='decisions')
  kind = models.CharField(max_length=32)
  status = models.CharField(max_length=16, default='proposed')
  targets = models.JSONField(default=list)
  proposal = models.JSONField(default=dict)
  reason = models.TextField(blank=True)
  question = models.TextField(blank=True)
  user_answer = models.TextField(blank=True)
  before = models.JSONField(null=True)
  after = models.JSONField(null=True)
  created_at = models.DateTimeField(auto_now_add=True)
  confirmed_at = models.DateTimeField(null=True)

  class Meta:
    db_table = 'decisions'
