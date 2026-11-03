from decimal import Decimal
from django.test import SimpleTestCase
from .cash_review import needs_review


class CashPurposeReviewTests(SimpleTestCase):
  def test_threshold_is_inclusive_and_confirmed_purposes_are_not_reasked(self):
    self.assertFalse(needs_review(Decimal(9999),'awaiting_user'))
    self.assertTrue(needs_review(Decimal(10000),'awaiting_user'))
    self.assertTrue(needs_review(Decimal(100000),'candidate_only'))
    self.assertFalse(needs_review(Decimal(10000),'confirmed'))
    self.assertFalse(needs_review(Decimal(10000),'reviewed_unknown'))
