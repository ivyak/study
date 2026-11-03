from django.db import migrations, models


class Migration(migrations.Migration):

  dependencies = [
    ('ledger', '0001_initial'),
  ]

  operations = [
    migrations.RemoveConstraint(
      model_name='journalentry',
      name='one_positive_journal_side',
    ),
    migrations.AddConstraint(
      model_name='journalentry',
      constraint=models.CheckConstraint(condition=models.Q(models.Q(('credit', 0), ('debit__gt', 0)), models.Q(('credit__gt', 0), ('debit', 0)), models.Q(('credit', 0), ('debit', 0)), _connector='OR'), name='nonnegative_journal_side'),
    ),
  ]
