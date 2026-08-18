"""Execute ERPNext's patched get_due_date outside a bench.

A full ERPNext test run needs bench, MariaDB and Redis, none of which are
available here. But get_due_date is nearly pure -- it touches only frappe.utils
date helpers -- so stubbing the framework lets the real, unmodified source be
imported and the new branch actually exercised rather than merely eyeballed.

Run: python verify_erpnext_patch.py
"""

import sys
import types
import unittest
from calendar import monthrange
from datetime import date, datetime, timedelta

ERPNEXT = r"C:\Claude_Code\erpnext-work"

# --------------------------------------------------------------------------
# Minimal frappe stand-in: only what payment_schedule.py touches at import time.
# --------------------------------------------------------------------------


def _to_date(value):
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()


class _dict(dict):
    def __getattr__(self, key):
        try:
            return self[key]
        except KeyError:
            return None

    def __setattr__(self, key, value):
        self[key] = value


frappe = types.ModuleType("frappe")
frappe._ = lambda s, *a, **k: s
frappe._dict = _dict
frappe.whitelist = lambda *a, **k: (lambda fn: fn)
frappe.get_doc = lambda *a, **k: None
frappe.get_cached_doc = lambda *a, **k: None
frappe.get_all = lambda *a, **k: []
frappe.get_value = lambda *a, **k: None
frappe.get_single_value = lambda *a, **k: 0
frappe.throw = lambda *a, **k: (_ for _ in ()).throw(Exception(a[0] if a else "throw"))
frappe.db = types.SimpleNamespace(get_value=lambda *a, **k: None)

utils = types.ModuleType("frappe.utils")
utils.DateTimeLikeObject = object
utils.getdate = _to_date
utils.add_days = lambda d, n: _to_date(d) + timedelta(days=int(n or 0))
utils.cint = lambda v: int(v or 0)
utils.flt = lambda v, p=None: float(v or 0)


def _add_months(d, n):
    d = _to_date(d)
    month = d.month - 1 + int(n or 0)
    year = d.year + month // 12
    month = month % 12 + 1
    return date(year, month, min(d.day, monthrange(year, month)[1]))


utils.add_months = _add_months
utils.get_last_day = lambda d: (
    lambda x: date(x.year, x.month, monthrange(x.year, x.month)[1])
)(_to_date(d))
frappe.utils = utils

party = types.ModuleType("erpnext.accounts.party")
party.get_party_account_currency = lambda *a, **k: None

for name, mod in {
    "frappe": frappe,
    "frappe.utils": utils,
    "erpnext": types.ModuleType("erpnext"),
    "erpnext.accounts": types.ModuleType("erpnext.accounts"),
    "erpnext.accounts.party": party,
}.items():
    sys.modules.setdefault(name, mod)

# Load the real, patched source straight off disk. Going through the package
# would drag in erpnext/__init__.py and the rest of the framework; this pulls in
# exactly the one file under test.
import importlib.util  # noqa: E402
import os  # noqa: E402

_target = os.path.join(ERPNEXT, "erpnext", "accounts", "services", "payment_schedule.py")
_spec = importlib.util.spec_from_file_location("_patched_payment_schedule", _target)
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
get_due_date = _mod.get_due_date

# --------------------------------------------------------------------------


def term(**kw):
    base = {"due_date_based_on": None, "credit_days": 0, "credit_months": 0}
    base.update(kw)
    return _dict(base)


class TestExistingBehaviourUnchanged(unittest.TestCase):
    """The patch must not disturb the three options that already shipped."""

    def test_days_after_invoice_date(self):
        t = term(due_date_based_on="Day(s) after invoice date", credit_days=30)
        self.assertEqual(get_due_date(t, "2026-05-29"), date(2026, 6, 28))

    def test_days_after_end_of_invoice_month(self):
        t = term(due_date_based_on="Day(s) after the end of the invoice month", credit_days=10)
        # May ends on the 31st; +10 days = 10 June.
        self.assertEqual(get_due_date(t, "2026-05-29"), date(2026, 6, 10))

    def test_months_after_end_of_invoice_month(self):
        t = term(due_date_based_on="Month(s) after the end of the invoice month", credit_months=2)
        # Two months on from May is July, whose last day is the 31st.
        self.assertEqual(get_due_date(t, "2026-05-29"), date(2026, 7, 31))

    def test_unknown_basis_still_returns_none(self):
        self.assertIsNone(get_due_date(term(due_date_based_on="Something else"), "2026-05-29"))


class TestNewReceiptBasis(unittest.TestCase):
    """The branch this patch adds."""

    BASIS = "Day(s) after receipt date"

    def test_runs_from_the_receipt_not_the_invoice(self):
        t = term(due_date_based_on=self.BASIS, credit_days=45)
        due = get_due_date(t, "2026-05-29", receipt_date="2026-05-15")
        # 15 May + 45 days = 29 June.
        self.assertEqual(due, date(2026, 6, 29))

    def test_a_late_invoice_cannot_stretch_the_clock(self):
        # The point of the whole change: whenever the buyer gets round to
        # invoicing, the due date is pinned to the receipt.
        t = term(due_date_based_on=self.BASIS, credit_days=45)
        early = get_due_date(t, "2026-05-20", receipt_date="2026-05-15")
        late = get_due_date(t, "2026-08-20", receipt_date="2026-05-15")
        self.assertEqual(early, late)

    def test_falls_back_to_the_invoice_date_when_nothing_received(self):
        t = term(due_date_based_on=self.BASIS, credit_days=30)
        self.assertEqual(get_due_date(t, "2026-05-29"), date(2026, 6, 28))
        self.assertIsNotNone(get_due_date(t, "2026-05-29"))

    def test_bill_date_still_wins_over_posting_date_for_the_fallback(self):
        t = term(due_date_based_on=self.BASIS, credit_days=10)
        self.assertEqual(get_due_date(t, "2026-05-29", bill_date="2026-05-01"), date(2026, 5, 11))

    def test_zero_credit_days_means_due_on_receipt(self):
        t = term(due_date_based_on=self.BASIS, credit_days=0)
        self.assertEqual(get_due_date(t, "2026-05-29", receipt_date="2026-05-15"), date(2026, 5, 15))

    def test_month_end_and_leap_day_receipts(self):
        t = term(due_date_based_on=self.BASIS, credit_days=45)
        self.assertEqual(get_due_date(t, "2028-03-01", receipt_date="2028-02-29"), date(2028, 4, 14))


class TestAgainstTheStatute(unittest.TestCase):
    """The patched ERPNext branch must agree with the standalone statutory module."""

    def test_matches_the_msmed_module_for_a_45_day_written_term(self):
        sys.path.insert(0, "msmed")
        from due_date import statutory_due_date  # noqa: E402

        accepted = date(2026, 4, 1)
        statutory = statutory_due_date(accepted, agreed_days=90, has_written_agreement=True)
        erp = get_due_date(
            term(due_date_based_on="Day(s) after receipt date", credit_days=statutory.allowed_days),
            "2026-06-30",
            receipt_date=accepted,
        )
        self.assertEqual(erp, statutory.due_date)
        self.assertEqual(erp, date(2026, 5, 16))


if __name__ == "__main__":
    unittest.main(verbosity=2)
