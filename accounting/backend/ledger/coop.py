"""生協決済と商品内訳の照合候補。元行・承認状態は変更しない。"""
from collections import defaultdict, Counter
from datetime import datetime
from decimal import Decimal
import re
from .models import ImportBatch, RawRecord, RawOccurrence
from .parsers import normalize


def store_key(value):
  return re.sub(r'（.*?）|\(.*?\)|\s+', '', normalize(value))


def timestamp(raw):
  return datetime.strptime(raw.raw_data['values'][0], '%Y-%m-%d %H:%M:%S')


def preview(batch_id):
  batch = ImportBatch.objects.get(pk=batch_id)
  ids = batch.occurrences.values_list('raw_record_id', flat=True)
  rows = list(RawRecord.objects.filter(pk__in=ids, source='univ_coop', transaction_date__isnull=False).order_by('transaction_date', 'pk'))
  refs = defaultdict(list)
  for occurrence in RawOccurrence.objects.filter(batch=batch, raw_record__in=rows).select_related('import_file'):
    refs[occurrence.raw_record_id].append({'file': occurrence.import_file.original_name,
      'line': occurrence.line_start, 'line_end': occurrence.line_end})
  groups = defaultdict(list)
  for row in rows:
    if row.dedupe_scope == 'univ_coop:items':
      groups[(timestamp(row), store_key(row.store))].append(row)
  payments, charges, points = [], [], []
  for row in rows:
    if row.dedupe_scope != 'univ_coop:money':
      continue
    values = row.raw_data['values']
    base = {'raw_id': row.pk, 'date_time': values[0], 'store': row.store,
      'amount': str(row.amount), 'references': refs[row.pk]}
    if row.memo == 'ポイント':
      points.append(base)
    elif row.memo == 'チャージ':
      candidates = RawRecord.objects.filter(pk__in=ids, source__in=['Vpass', 'Rakuten_Card'],
        transaction_date=row.transaction_date, amount=row.amount, direction='out')
      base['card_candidates'] = [{'raw_id': card.pk, 'memo': card.memo,
        'references': [{'file': o.import_file.original_name, 'line': o.line_start}
          for o in card.occurrences.filter(batch=batch).select_related('import_file')]}
        for card in candidates if '大学生協電子マネー入金サイト' in normalize(card.memo)]
      base['funding_confirmed'] = False
      charges.append(base)
    else:
      candidates = []
      for (time, store), items in groups.items():
        delta = abs((timestamp(row)-time).total_seconds())
        if store != store_key(row.store) or delta > 15:
          continue
        total = sum((item.amount for item in items), Decimal(0))
        candidates.append({'raw_ids': [item.pk for item in items], 'seconds_apart': delta,
          'items_total': str(total), 'difference': str(total-row.amount),
          'items': [{'name': item.item_name, 'amount': str(item.amount),
            'quantity': item.raw_data['values'][3], 'unit_price': item.raw_data['values'][4],
            'references': refs[item.pk]} for item in items]})
      base.update(points_inside=values[6], points_awarded_column=values[7],
        candidates=sorted(candidates, key=lambda x: (x['seconds_apart'], x['raw_ids'])),
        amount_meaning_confirmed=False)
      payments.append(base)
  candidate_counts = Counter(rid for p in payments for candidate in p['candidates'] for rid in candidate['raw_ids'])
  for payment in payments:
    payment['ambiguous'] = len(payment['candidates']) > 1 or any(candidate_counts[rid] > 1
      for candidate in payment['candidates'] for rid in candidate['raw_ids'])
  return {'batch_id': batch_id, 'preview_only': True,
    'summary': {'payments': len(payments), 'charges': len(charges), 'point_events': len(points),
      'item_rows': sum(len(group) for group in groups.values()), 'item_groups': len(groups),
      'payments_with_unique_equal_items': sum(not p['ambiguous'] and len(p['candidates']) == 1
        and Decimal(p['candidates'][0]['difference']) == 0 for p in payments),
      'payments_without_items': sum(not p['candidates'] for p in payments)},
    'payments': payments, 'charges': charges, 'point_events': points,
    'unmatched_item_ids': [row.pk for row in rows if row.dedupe_scope == 'univ_coop:items' and row.pk not in candidate_counts],
    'note': '照合候補のみ。ポイント欄の意味、差額、資金元を断定しない。開始残高は不明。'}
