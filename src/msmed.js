// JavaScript port of msmed/due_date.py.
//
// Same statute, same rules, same results — enforced by a shared vector file that
// both implementations are tested against, so the page cannot quietly drift from
// the module a maintainer would actually merge.
//
// MSMED Act 2006 ss.2(b), 2(n), 15; IT Act 1961 s.43B(h); S.O. 1364(E) of
// 21 March 2025.

export const MAX_AGREED_DAYS = 45;
export const NO_AGREEMENT_DAYS = 15;
export const OBJECTION_WINDOW_DAYS = 15;

export const MICRO = 'Micro';
export const SMALL = 'Small';
export const MEDIUM = 'Medium';
export const LARGE = 'Large';

export const CLASSIFICATION_LIMITS = [
  { label: MICRO, investmentCr: 2.5, turnoverCr: 10 },
  { label: SMALL, investmentCr: 25, turnoverCr: 100 },
  { label: MEDIUM, investmentCr: 125, turnoverCr: 500 },
];

/* ---------- dates, in UTC so nothing drifts with the host timezone ---------- */

export function toDate(value) {
  if (value instanceof Date) {
    return new Date(Date.UTC(value.getUTCFullYear(), value.getUTCMonth(), value.getUTCDate()));
  }
  const [y, m, d] = String(value).slice(0, 10).split('-').map(Number);
  return new Date(Date.UTC(y, m - 1, d));
}

export function addDays(value, days) {
  const out = new Date(toDate(value).getTime());
  out.setUTCDate(out.getUTCDate() + days);
  return out;
}

export function isoDate(value) {
  return toDate(value).toISOString().slice(0, 10);
}

export function daysBetween(from, to) {
  return Math.round((toDate(to).getTime() - toDate(from).getTime()) / 86400000);
}

/* ---------- the rules ---------- */

/** S.O. 1364(E). Composite criteria: breaching either ceiling moves the tier. */
export function classifyEnterprise(investmentCr, turnoverCr) {
  for (const tier of CLASSIFICATION_LIMITS) {
    if (investmentCr <= tier.investmentCr && turnoverCr <= tier.turnoverCr) return tier.label;
  }
  return LARGE;
}

/** s.2(n): only a micro or small enterprise with a filed memorandum is a "supplier". */
export function isProtectedSupplier(category, udyamRegistered) {
  return (category === MICRO || category === SMALL) && Boolean(udyamRegistered);
}

/** s.43B(h) is narrower than s.15 — traders are outside it. */
export function is43BhApplicable(category, udyamRegistered, isTrader) {
  return isProtectedSupplier(category, udyamRegistered) && !isTrader;
}

/** s.15: 45 days where the terms are written, otherwise 15. */
export function statutoryMaxDays(hasWrittenAgreement) {
  return hasWrittenAgreement ? MAX_AGREED_DAYS : NO_AGREEMENT_DAYS;
}

/**
 * s.2(b) explanation (i). Acceptance is delivery, unless the buyer objected in
 * writing within 15 days — then the clock starts when the objection is removed.
 */
export function dayOfAcceptance(deliveryDate, objectionRaisedOn = null, objectionRemovedOn = null) {
  if (!objectionRaisedOn || !objectionRemovedOn) return toDate(deliveryDate);
  const delivery = toDate(deliveryDate);
  const raised = toDate(objectionRaisedOn);
  const windowEnd = addDays(delivery, OBJECTION_WINDOW_DAYS);
  if (raised < delivery || raised > windowEnd) return delivery;
  const removed = toDate(objectionRemovedOn);
  return removed > delivery ? removed : delivery;
}

/**
 * When payment falls due, and from when s.16 interest runs.
 * An agreed period beyond the statutory ceiling is void as to the excess.
 */
export function statutoryDueDate({
  acceptanceDate,
  agreedDays = null,
  hasWrittenAgreement = true,
  category = MICRO,
  udyamRegistered = true,
}) {
  const accepted = toDate(acceptanceDate);
  const protectedSupply = isProtectedSupplier(category, udyamRegistered);
  const notes = [];

  if (!protectedSupply) {
    const allowed = agreedDays == null ? statutoryMaxDays(hasWrittenAgreement) : Number(agreedDays);
    notes.push(
      category === MEDIUM
        ? 'Medium enterprises fall outside the s.2(n) definition of supplier, so the contractual period applies unchanged.'
        : !udyamRegistered
          ? "Without a filed Udyam memorandum the supplier is not a 'supplier' under s.2(n), so the contractual period applies unchanged."
          : 'Outside the delayed-payment provisions; the contractual period applies.',
    );
    return {
      protected: false,
      category,
      acceptanceDate: accepted,
      agreedDays: allowed,
      allowedDays: allowed,
      dueDate: addDays(accepted, allowed),
      appointedDate: null,
      capped: false,
      voidedDays: 0,
      basis: 'contract',
      notes,
    };
  }

  const ceiling = statutoryMaxDays(hasWrittenAgreement);
  const requested = agreedDays == null ? ceiling : Number(agreedDays);
  let allowed;
  let basis;

  if (!hasWrittenAgreement) {
    allowed = NO_AGREEMENT_DAYS;
    basis = 's.15 — no written agreement, 15 days';
    if (requested > allowed) {
      notes.push(
        `A ${requested}-day period was recorded, but with no written agreement s.15 allows only ${NO_AGREEMENT_DAYS} days.`,
      );
    }
  } else {
    allowed = Math.min(requested, ceiling);
    basis = 's.15 — written agreement, capped at 45 days';
    if (requested > ceiling) {
      notes.push(
        `The agreed period of ${requested} days exceeds the s.15 ceiling. The agreement is void as to the additional ${requested - ceiling} days.`,
      );
    }
  }

  const dueDate = addDays(accepted, allowed);
  return {
    protected: true,
    category,
    acceptanceDate: accepted,
    agreedDays: requested,
    allowedDays: allowed,
    dueDate,
    appointedDate: addDays(dueDate, 1), // s.2(b): interest runs from the day after
    capped: requested > allowed,
    voidedDays: Math.max(0, requested - allowed),
    basis,
    notes,
  };
}
