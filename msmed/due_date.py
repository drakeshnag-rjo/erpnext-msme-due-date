# Statutory payment due dates for Indian micro and small enterprise suppliers.
#
# Deliberately free of any framework import. The law is fiddly and the framework
# is heavy; keeping the two apart means this can be unit-tested in a plain Python
# process, reviewed by an accountant who does not read Frappe, and reused by
# either erpnext or the india_compliance app.
#
# Statutory basis, verified 2026-08:
#
#   MSMED Act 2006 s.2(n)  A "supplier" is a MICRO or SMALL enterprise that has
#                          filed a memorandum (Udyam). Medium enterprises are
#                          outside the delayed-payment provisions entirely.
#   MSMED Act 2006 s.2(b)  The "appointed day" is the day following expiry of the
#                          agreed period, counted from the day of acceptance.
#   MSMED Act 2006 s.2(b)  "Day of acceptance" is the day of actual delivery, or,
#     explanation (i)      where the buyer objects in writing within 15 days of
#                          delivery, the day the objection is removed.
#   MSMED Act 2006 s.15    Payment falls due on the agreed date, which may not
#                          exceed 45 days from acceptance. With no written
#                          agreement the period is 15 days.
#   IT Act 1961 s.43B(h)   A sum payable to a micro or small enterprise beyond the
#                          s.15 period is deductible only in the year of actual
#                          payment. Traders are outside it.
#   S.O. 1364(E) 21-3-2025 Revised classification thresholds, in force 1-4-2025.
#
# Note on the common misreading: 45 days is a CEILING, not the rule. Where the
# parties have no written agreement the period is 15 days, and an implementation
# that hardcodes 45 will under-report the buyer's exposure by a month.

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, timedelta

MAX_AGREED_DAYS = 45  # s.15 ceiling where a written agreement exists
NO_AGREEMENT_DAYS = 15  # s.15 default
OBJECTION_WINDOW_DAYS = 15  # s.2(b) explanation (i)

MICRO = "Micro"
SMALL = "Small"
MEDIUM = "Medium"
LARGE = "Large"

# (label, investment ceiling in crore, turnover ceiling in crore)
CLASSIFICATION_LIMITS = (
    (MICRO, 2.5, 10.0),
    (SMALL, 25.0, 100.0),
    (MEDIUM, 125.0, 500.0),
)


def classify_enterprise(investment_cr: float, turnover_cr: float) -> str:
    """Classify against S.O. 1364(E).

    The criteria are composite: an enterprise must sit within BOTH ceilings.
    Breaching either one moves it up a tier, which is how a low-investment,
    high-turnover trading business ends up outside the protection it assumed it
    had.
    """
    for label, investment_limit, turnover_limit in CLASSIFICATION_LIMITS:
        if investment_cr <= investment_limit and turnover_cr <= turnover_limit:
            return label
    return LARGE


def is_protected_supplier(category: str, udyam_registered: bool) -> bool:
    """Whether s.15 and s.16 reach this supplier at all (s.2(n))."""
    return category in (MICRO, SMALL) and bool(udyam_registered)


def is_43bh_applicable(category: str, udyam_registered: bool, is_trader: bool) -> bool:
    """Whether the buyer's deduction is at risk under s.43B(h).

    Narrower than s.15: traders are excluded, per the MSME Ministry's
    clarification that traders may register on Udyam for priority-sector lending
    only.
    """
    return is_protected_supplier(category, udyam_registered) and not is_trader


def statutory_max_days(has_written_agreement: bool) -> int:
    """s.15: 45 days where the terms are in writing, otherwise 15."""
    return MAX_AGREED_DAYS if has_written_agreement else NO_AGREEMENT_DAYS


def day_of_acceptance(
    delivery_date: date,
    objection_raised_on: date | None = None,
    objection_removed_on: date | None = None,
) -> date:
    """s.2(b) explanation (i).

    Acceptance is delivery, unless the buyer objected in writing within 15 days
    of delivery — in which case the clock starts only when the supplier removes
    the objection. An objection raised late, or never resolved, does not move the
    date.
    """
    if objection_raised_on is None or objection_removed_on is None:
        return delivery_date
    if not (delivery_date <= objection_raised_on <= delivery_date + timedelta(days=OBJECTION_WINDOW_DAYS)):
        # Outside the 15-day window, so it does not defer acceptance.
        return delivery_date
    return max(delivery_date, objection_removed_on)


@dataclass(frozen=True)
class DueDateResult:
    """The statutory position on one supply."""

    protected: bool
    category: str
    acceptance_date: date
    agreed_days: int
    allowed_days: int
    due_date: date
    appointed_date: date | None
    capped: bool
    voided_days: int
    basis: str
    notes: tuple[str, ...] = field(default=())


def statutory_due_date(
    acceptance_date: date,
    agreed_days: int | None = None,
    has_written_agreement: bool = True,
    category: str = MICRO,
    udyam_registered: bool = True,
) -> DueDateResult:
    """When payment actually falls due, and from when interest runs.

    Where the supplier is protected, an agreed period longer than the statutory
    ceiling is not honoured: s.15 caps it, and the agreement is void as to the
    excess. Where the supplier is not protected the contract simply stands.
    """
    protected = is_protected_supplier(category, udyam_registered)
    notes: list[str] = []

    if not protected:
        allowed = int(agreed_days if agreed_days is not None else statutory_max_days(has_written_agreement))
        if category == MEDIUM:
            notes.append(
                "Medium enterprises fall outside the s.2(n) definition of supplier, "
                "so the contractual period applies unchanged."
            )
        elif not udyam_registered:
            notes.append(
                "Without a filed Udyam memorandum the supplier is not a 'supplier' "
                "under s.2(n), so the contractual period applies unchanged."
            )
        else:
            notes.append("Outside the delayed-payment provisions; the contractual period applies.")
        due = acceptance_date + timedelta(days=allowed)
        return DueDateResult(
            protected=False,
            category=category,
            acceptance_date=acceptance_date,
            agreed_days=allowed,
            allowed_days=allowed,
            due_date=due,
            appointed_date=None,
            capped=False,
            voided_days=0,
            basis="contract",
            notes=tuple(notes),
        )

    ceiling = statutory_max_days(has_written_agreement)

    if not has_written_agreement:
        # s.15 gives 15 days regardless of what was said verbally.
        allowed = NO_AGREEMENT_DAYS
        requested = int(agreed_days) if agreed_days is not None else NO_AGREEMENT_DAYS
        capped = requested > allowed
        basis = "s.15 — no written agreement, 15 days"
        if capped:
            notes.append(
                f"A {requested}-day period was recorded, but with no written agreement "
                f"s.15 allows only {NO_AGREEMENT_DAYS} days."
            )
    else:
        requested = int(agreed_days) if agreed_days is not None else ceiling
        allowed = min(requested, ceiling)
        capped = requested > ceiling
        basis = "s.15 — written agreement, capped at 45 days"
        if capped:
            notes.append(
                f"The agreed period of {requested} days exceeds the s.15 ceiling. "
                f"The agreement is void as to the additional {requested - ceiling} days."
            )

    due = acceptance_date + timedelta(days=allowed)
    return DueDateResult(
        protected=True,
        category=category,
        acceptance_date=acceptance_date,
        agreed_days=requested,
        allowed_days=allowed,
        due_date=due,
        # s.2(b): interest runs from the day AFTER the period expires.
        appointed_date=due + timedelta(days=1),
        capped=capped,
        voided_days=max(0, requested - allowed),
        basis=basis,
        notes=tuple(notes),
    )
