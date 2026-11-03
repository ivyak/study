from django.urls import path
from ledger.views import AccountingView

urlpatterns = [
  path('api/accounting/<str:resource>', AccountingView.as_view()),
  path('api/accounting/transactions/<int:transaction_id>', AccountingView.as_view(), {'resource': 'detail'}),
]
