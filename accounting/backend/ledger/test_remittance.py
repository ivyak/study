from decimal import Decimal
from types import SimpleNamespace
from django.test import SimpleTestCase
from .remittance import adjustments, eligible_amounts, eligible_breakdown


class RemittanceDisplayTests(SimpleTestCase):
  def row(self, day, kind, category, amount, eligible=None):
    return {'date': day, 'kind': kind, 'categoryAmounts': [{'category': category, 'amount': amount}],
      'remittanceEligibleAmounts': eligible or {}}

  def test_monthly_pool_has_no_cross_month_offset_or_income_double_count(self):
    rows = [self.row('2026-10-25', 'income', '仕送り', 100000),
      self.row('2026-10-30', 'income', '給与', 50000),
      self.row('2026-10-27', 'expense', '住まい', 63330, {'住まい': 63330}),
      self.row('2026-10-02', 'expense', '教育・教養', 2970, {'教育・教養': 2970}),
      self.row('2026-09-25', 'income', '仕送り', 100000),
      self.row('2026-11-01', 'expense', '住まい', 63330, {'住まい': 63330})]
    self.assertEqual(adjustments(rows), {'2026-10': {'amount': 66300,
      'expenseByCategory': {'住まい': 63330, '教育・教養': 2970},
      'expenseByPurpose': {'住まい': 63330, '教育・教養': 2970}}})

  def test_insufficient_support_is_capped_and_refunds_reduce_target(self):
    rows = [self.row('2026-01-01', 'income', '仕送り', 100),
      self.row('2026-01-02', 'expense', '住まい', 200, {'住まい': 200}),
      self.row('2026-01-03', 'expense', '交通', 200, {'交通': 200}),
      self.row('2026-01-04', 'expense', '交通', -100, {'交通': -100})]
    result = adjustments(rows)['2026-01']
    self.assertEqual(result['amount'], 100)
    self.assertEqual(sum(Decimal(str(v)) for v in result['expenseByCategory'].values()), Decimal(100))
    self.assertLessEqual(result['expenseByCategory']['住まい'], 200)
    self.assertLessEqual(result['expenseByCategory']['交通'], 100)

  def test_purposes_separate_reference_books_and_driving_camp_in_same_category(self):
    def item(name, amount):
      return SimpleNamespace(name=name, category=SimpleNamespace(name='教育・教養'), amount=Decimal(amount))
    items = [item('免許合宿代', 30000), item('財務会計講義の教科書', 3000), item('ポイント値引き', -300)]
    detail = eligible_breakdown(items, '')
    self.assertEqual({d['purpose'] for d in detail}, {'免許合宿代', '参考書代'})
    self.assertEqual(sum(Decimal(str(d['amount'])) for d in detail), Decimal(32700))
    income = self.row('2026-07-01', 'income', '仕送り', 20000)
    expense = self.row('2026-07-02', 'expense', '教育・教養', 32700, {'教育・教養': 32700})
    expense['remittanceEligibleBreakdown'] = detail
    result = adjustments([income, expense])['2026-07']
    self.assertEqual(set(result['expenseByPurpose']), {'免許合宿代', '参考書代'})
    self.assertEqual(sum(Decimal(str(v)) for v in result['expenseByPurpose'].values()), Decimal(20000))

  def test_only_target_items_are_eligible_with_discounts_and_self_paid_amounts(self):
    def item(name, category, amount):
      return SimpleNamespace(name=name, category=SimpleNamespace(name=category), amount=Decimal(amount))
    items = [item('ゼミナール コーポレートファイナンス', '教育・教養', '3000'),
      item('ポイント値引き', '教育・教養', '-30'), item('新幹線改札内店のお茶', '食費', '100'),
      item('サークル合宿代', '大型出費/旅行', '10000'), item('簿記受験料', '教育・教養', '3850')]
    self.assertEqual(eligible_amounts(items, '書籍と日用品'), {'教育・教養': Decimal(3000)})
    self.assertEqual(eligible_amounts(items[:2], '書籍'), {'教育・教養': Decimal(2970)})
    target = [item('スマートＥＸ', '交通', '20000'), item('免許合宿代', '教育・教養', '300000'),
      item('コンタクト代', '医療・保険', '15000'), item('家賃', '住まい', '60000')]
    self.assertEqual(sum(eligible_amounts(target, '').values()), Decimal(395000))
    target[1].category.name = 'クルマ'
    self.assertEqual(eligible_amounts(target, '')['クルマ'], Decimal(300000))
