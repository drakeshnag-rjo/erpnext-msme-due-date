# Run: python -m unittest discover -s msmed -v
#
# Nothing here asserts against the module's own output. Every expected date is
# worked out in the comment above it, and the statutory boundaries are tested on
# both sides.

import unittest
from datetime import date, timedelta

from due_date import (  # noqa: E402
    LARGE,
    MAX_AGREED_DAYS,
    MEDIUM,
    MICRO,
    NO_AGREEMENT_DAYS,
    SMALL,
    classify_enterprise,
    day_of_acceptance,
    is_43bh_applicable,
    is_protected_supplier,
    statutory_due_date,
    statutory_max_days,
)


class TestClassification(unittest.TestCase):
    """S.O. 1364(E), in force 1 April 2025."""

    def test_sits_exactly_on_the_thresholds(self):
        self.assertEqual(classify_enterprise(2.5, 10), MICRO)
        self.assertEqual(classify_enterprise(25, 100), SMALL)
        self.assertEqual(classify_enterprise(125, 500), MEDIUM)
        self.assertEqual(classify_enterprise(125.01, 500), LARGE)

    def test_breaching_either_ceiling_moves_the_tier(self):
        # The trap for a trading business: tiny investment, large turnover.
        self.assertEqual(classify_enterprise(0.5, 60), SMALL)
        self.assertEqual(classify_enterprise(0.5, 300), MEDIUM)
        self.assertEqual(classify_enterprise(0.5, 900), LARGE)
        # And the mirror case.
        self.assertEqual(classify_enterprise(40, 1), MEDIUM)


class TestWhoIsProtected(unittest.TestCase):
    def test_medium_enterprises_are_not_suppliers_under_s2n(self):
        self.assertFalse(is_protected_supplier(MEDIUM, udyam_registered=True))
        self.assertFalse(is_43bh_applicable(MEDIUM, True, is_trader=False))

    def test_udyam_registration_is_required(self):
        self.assertTrue(is_protected_supplier(SMALL, udyam_registered=True))
        self.assertFalse(is_protected_supplier(SMALL, udyam_registered=False))

    def test_a_trader_keeps_s15_but_loses_s43bh(self):
        self.assertTrue(is_protected_supplier(SMALL, True))
        self.assertFalse(is_43bh_applicable(SMALL, True, is_trader=True))
        self.assertTrue(is_43bh_applicable(SMALL, True, is_trader=False))


class TestStatutoryPeriod(unittest.TestCase):
    def test_the_ceiling_depends_on_whether_terms_are_written(self):
        self.assertEqual(statutory_max_days(True), MAX_AGREED_DAYS)
        self.assertEqual(statutory_max_days(False), NO_AGREEMENT_DAYS)
        self.assertEqual(statutory_max_days(True), 45)
        self.assertEqual(statutory_max_days(False), 15)


class TestDayOfAcceptance(unittest.TestCase):
    """s.2(b) explanation (i)."""

    def test_acceptance_is_delivery_when_nobody_objects(self):
        self.assertEqual(day_of_acceptance(date(2026, 4, 1)), date(2026, 4, 1))

    def test_a_timely_objection_defers_acceptance_to_its_removal(self):
        # Objection raised on day 10 of the 15-day window, removed on 25 April.
        self.assertEqual(
            day_of_acceptance(date(2026, 4, 1), date(2026, 4, 11), date(2026, 4, 25)),
            date(2026, 4, 25),
        )

    def test_the_objection_window_boundary(self):
        delivery = date(2026, 4, 1)
        removed = date(2026, 5, 20)
        # Day 15 is inside the window.
        self.assertEqual(day_of_acceptance(delivery, delivery + timedelta(days=15), removed), removed)
        # Day 16 is outside it, so acceptance stays at delivery.
        self.assertEqual(day_of_acceptance(delivery, delivery + timedelta(days=16), removed), delivery)

    def test_an_unresolved_objection_does_not_move_the_date(self):
        self.assertEqual(
            day_of_acceptance(date(2026, 4, 1), date(2026, 4, 5), None), date(2026, 4, 1)
        )


class TestStatutoryDueDate(unittest.TestCase):
    ACCEPTED = date(2026, 4, 1)

    def test_net_90_is_void_beyond_day_45(self):
        # 1 April + 45 days = 16 May. Interest runs from 17 May.
        r = statutory_due_date(self.ACCEPTED, agreed_days=90, has_written_agreement=True)
        self.assertTrue(r.protected)
        self.assertEqual(r.allowed_days, 45)
        self.assertTrue(r.capped)
        self.assertEqual(r.voided_days, 45)
        self.assertEqual(r.due_date, date(2026, 5, 16))
        self.assertEqual(r.appointed_date, date(2026, 5, 17))
        self.assertIn("void as to the additional 45 days", " ".join(r.notes))

    def test_a_term_inside_the_ceiling_stands_as_agreed(self):
        # 1 April + 30 days = 1 May.
        r = statutory_due_date(self.ACCEPTED, agreed_days=30, has_written_agreement=True)
        self.assertEqual(r.allowed_days, 30)
        self.assertFalse(r.capped)
        self.assertEqual(r.voided_days, 0)
        self.assertEqual(r.due_date, date(2026, 5, 1))

    def test_THE_CORRECTION_no_written_agreement_means_15_days_not_45(self):
        # This is the case an implementation that hardcodes 45 gets wrong, by a
        # full month. 1 April + 15 days = 16 April.
        r = statutory_due_date(self.ACCEPTED, agreed_days=45, has_written_agreement=False)
        self.assertEqual(r.allowed_days, 15)
        self.assertTrue(r.capped)
        self.assertEqual(r.due_date, date(2026, 4, 16))
        self.assertEqual(r.appointed_date, date(2026, 4, 17))
        self.assertIn("no written agreement", " ".join(r.notes))

    def test_the_45_day_boundary_is_not_off_by_one(self):
        exactly = statutory_due_date(self.ACCEPTED, agreed_days=45, has_written_agreement=True)
        self.assertFalse(exactly.capped)
        self.assertEqual(exactly.allowed_days, 45)
        one_more = statutory_due_date(self.ACCEPTED, agreed_days=46, has_written_agreement=True)
        self.assertTrue(one_more.capped)
        self.assertEqual(one_more.voided_days, 1)
        # Both land on the same date, which is the whole point of the cap.
        self.assertEqual(exactly.due_date, one_more.due_date)

    def test_THE_CORRECTION_a_medium_supplier_keeps_its_contract(self):
        # Applying 45 days to a medium enterprise is the second common error:
        # the Act does not reach them, so Net 90 stands.
        r = statutory_due_date(self.ACCEPTED, agreed_days=90, category=MEDIUM)
        self.assertFalse(r.protected)
        self.assertEqual(r.allowed_days, 90)
        self.assertFalse(r.capped)
        self.assertEqual(r.due_date, date(2026, 6, 30))
        self.assertIsNone(r.appointed_date)
        self.assertIn("outside the s.2(n) definition", " ".join(r.notes))

    def test_an_unregistered_micro_supplier_is_not_protected(self):
        r = statutory_due_date(self.ACCEPTED, agreed_days=90, udyam_registered=False)
        self.assertFalse(r.protected)
        self.assertEqual(r.allowed_days, 90)
        self.assertIn("Udyam", " ".join(r.notes))

    def test_defaults_to_the_statutory_ceiling_when_no_period_is_recorded(self):
        written = statutory_due_date(self.ACCEPTED, agreed_days=None, has_written_agreement=True)
        self.assertEqual(written.allowed_days, 45)
        self.assertFalse(written.capped)
        unwritten = statutory_due_date(self.ACCEPTED, agreed_days=None, has_written_agreement=False)
        self.assertEqual(unwritten.allowed_days, 15)
        self.assertFalse(unwritten.capped)

    def test_interest_always_starts_the_day_after_the_due_date(self):
        for agreed, written in ((10, True), (45, True), (90, True), (5, False), (60, False)):
            r = statutory_due_date(self.ACCEPTED, agreed_days=agreed, has_written_agreement=written)
            self.assertEqual(r.appointed_date, r.due_date + timedelta(days=1))

    def test_the_allowed_period_never_exceeds_the_ceiling_for_a_protected_supply(self):
        for agreed in range(0, 200, 7):
            for written in (True, False):
                r = statutory_due_date(self.ACCEPTED, agreed_days=agreed, has_written_agreement=written)
                self.assertLessEqual(r.allowed_days, statutory_max_days(written))
                self.assertEqual(r.due_date, self.ACCEPTED + timedelta(days=r.allowed_days))

    def test_acceptance_deferral_pushes_the_whole_clock(self):
        accepted = day_of_acceptance(date(2026, 4, 1), date(2026, 4, 10), date(2026, 4, 20))
        r = statutory_due_date(accepted, agreed_days=45, has_written_agreement=True)
        self.assertEqual(accepted, date(2026, 4, 20))
        # 20 April + 45 days = 4 June.
        self.assertEqual(r.due_date, date(2026, 6, 4))


if __name__ == "__main__":
    unittest.main(verbosity=2)
