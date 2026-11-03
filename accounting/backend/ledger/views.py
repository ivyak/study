from collections import defaultdict
import re
from django.db import transaction
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Category
from .reporting import balances, publication_state, serialize_transactions, snapshot, summary, transaction_queryset


class AccountingView(APIView):
  http_method_names = ['get', 'head', 'options']

  def get(self, request, resource, transaction_id=None):
    month = request.query_params.get('month')
    year = request.query_params.get('year')
    if month and not re.fullmatch(r'\d{4}-(0[1-9]|1[0-2])', month):
      return Response({'error': '月はYYYY-MM形式で指定してください。'}, status=400)
    if year and not re.fullmatch(r'\d{4}', year):
      return Response({'error': '年はYYYY形式で指定してください。'}, status=400)
    if month and year:
      return Response({'error': '月または年のどちらかを指定してください。'}, status=400)
    if (month and not 1 <= int(month[:4]) <= 9998) or (year and not 1 <= int(year) <= 9998):
      return Response({'error': '年は0001〜9998で指定してください。'}, status=400)
    with transaction.atomic():
      if resource == 'status':
        return Response(publication_state())
      if resource in {'snapshot', 'coverage'}:
        data = snapshot()
        return Response(data.get('coverage', {}) if resource == 'coverage' else data)
      if resource == 'categories':
        return Response(list(Category.objects.order_by('position', 'id').values('id', 'name', 'color')))
      if resource == 'bs':
        if not month and not year:
          return Response({'error': 'monthまたはyearを指定してください。'}, status=400)
        return Response(balances(month=month, year=year))
      queryset = transaction_queryset()
      if month:
        queryset = queryset.filter(date__year=int(month[:4]), date__month=int(month[5:]))
      elif year:
        queryset = queryset.filter(date__year=int(year))
      kind, category = request.query_params.get('kind'), request.query_params.get('category')
      if kind:
        if kind not in {'expense', 'income', 'transfer', 'opening'}:
          return Response({'error': '種類が不正です。'}, status=400)
        queryset = queryset.filter(kind=kind)
      if category:
        queryset = queryset.filter(items__category__name=category).distinct()
      if resource == 'detail':
        tx = queryset.filter(pk=transaction_id).first()
        return Response(serialize_transactions([tx])[0] if tx else {'error': '取引がありません。'}, status=200 if tx else 404)
      if resource == 'transactions':
        try:
          limit, offset = int(request.query_params.get('limit', 100)), int(request.query_params.get('offset', 0))
          if not 1 <= limit <= 1000 or offset < 0:
            raise ValueError()
        except ValueError:
          return Response({'error': '取得件数・開始位置が不正です。'}, status=400)
        return Response({'count': queryset.count(), 'results': serialize_transactions(queryset[offset:offset+limit])})
      rows = serialize_transactions(queryset)
      if resource in {'summary', 'pl'}:
        return Response(summary(rows))
      if resource == 'journal':
        return Response([{'transactionId': r['id'], 'date': r['date'], **line} for r in rows for line in r['journalEntries']])
      if resource == 'calendar':
        groups = defaultdict(list)
        for row in rows:
          groups[row['date']].append(row)
        return Response([{'date': day, **summary(items), 'transfer': sum(r['amount'] for r in items if r['kind'] == 'transfer'),
          'transactionIds': [r['id'] for r in items]} for day, items in sorted(groups.items())])
      return Response({'error': 'APIがありません。'}, status=404)
