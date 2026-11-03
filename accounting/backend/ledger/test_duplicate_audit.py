from copy import deepcopy
from decimal import Decimal
from django.test import SimpleTestCase
from .duplicate_audit import detect, subsets, similarity


class DuplicateAuditTests(SimpleTestCase):
  def row(self, pk, amount, receipt=False, merchant='店A', kind='expense', source=None):
    return {'id': pk, 'date': '2026-03-02', 'amount': str(amount), 'kind': kind,
      'receipt_only': receipt, 'has_financial_source': not receipt,
      'merchants': [merchant], 'items': [{'amount': str(amount)}], 'personal_payment': False,
      'external_ids': [], 'source_names': [source or ('zaim' if receipt else 'Vpass')]}

  def test_split_payments_and_coverage_do_not_mutate_rows(self):
    rows = [self.row(1,11640,merchant='京都大学生協 時計台旅行センター'),
      self.row(2,25180,merchant='京都大学生協 時計台旅行センター'),
      self.row(3,36820,True,'京大生協 キャリア・トラベル'), self.row(4,100,kind='transfer')]
    before = deepcopy(rows)
    result = detect(rows)
    merged = [c for c in result['candidates'] if c['type'] == 'multiple_payments_one_receipt']
    self.assertEqual(len(merged),1)
    self.assertEqual(set(merged[0]['transaction_ids']),{1,2,3})
    self.assertEqual(result['transactions_checked'],4)
    self.assertEqual(rows,before)

  def test_subsets_never_use_same_payment_twice_and_mark_ambiguity(self):
    self.assertEqual(subsets([{'id':1,'amount':'5'}],Decimal(10)),[])
    self.assertEqual(subsets([{'id':1,'amount':'5'},{'id':2,'amount':'5'}],Decimal(10)),[(1,2)])
    self.assertEqual(len(subsets([{'id':i,'amount':'5'} for i in [1,2,3]],Decimal(10))),2)

  def test_points_compare_original_purchase_amount_and_receipt_item(self):
    payment = self.row(1,254)
    payment['payment_gross_amounts'] = ['258']
    receipt = self.row(2,288,True)
    receipt['items'] = [{'amount':'258'},{'amount':'30'}]
    result = detect([payment,receipt])
    self.assertTrue(any(c['type']=='receipt_item_matches_payment' for c in result['candidates']))

  def test_multiple_receipts_and_financial_sources_are_checked(self):
    rows = [self.row(1,500),self.row(2,200,True),self.row(3,300,True),
      self.row(4,500,source='PayPay_Corporation')]
    types = {c['type'] for c in detect(rows)['candidates']}
    self.assertIn('multiple_receipts_one_payment',types)
    self.assertIn('financial_sources_same_payment',types)

  def test_blank_names_and_different_chains_are_not_merchant_evidence(self):
    self.assertEqual(similarity({'merchants':['-','_']},{'merchants':['-','_']}),0)
    self.assertEqual(similarity({'merchants':['ローソン百万遍店']},{'merchants':['松屋百万遍店']}),0)

  def test_refund_and_card_settlement_are_not_purchase_duplicates(self):
    rows=[self.row(1,100),self.row(2,-100,True),self.row(3,100,True,kind='transfer')]
    self.assertEqual(detect(rows)['candidates'],[])

  def test_existing_attached_receipt_is_also_audited(self):
    row = self.row(1,500)
    row['financial_raws'] = [{'id':1,'date':'2026-03-02','store':'ユーネクスト','personal_payment':False}]
    row['linked_receipts'] = [{'id':2,'date':'2026-03-02','store':'MOVIX京都'}]
    result = detect([row])
    self.assertEqual(result['existing_receipt_links_checked'],1)
    self.assertEqual(result['candidates'][0]['type'],'existing_link_needs_review')
