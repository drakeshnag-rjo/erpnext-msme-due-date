### What problem this solves

Payment terms can only be dated from the invoice today. `due_date_based_on` offers three
options, and all three count from the invoice date or its month end.

Several jurisdictions run the payment clock from **receipt of the goods** instead:

- India's MSMED Act 2006 s.15 counts from acceptance of the supply, and s.16 charges
  compound interest at three times the RBI bank rate once that period expires.
- The EU Late Payment Directive 2011/7/EU likewise counts from receipt of the goods.

Neither can be expressed in ERPNext, so users either mis-date the payment schedule or
maintain the due date by hand. This adds the missing basis.

Refs #42807.

### What this does

- Adds `Day(s) after receipt date` to `due_date_based_on` on **Payment Term**, **Payment
  Terms Template Detail** and **Payment Schedule**, and includes it in the `credit_days`
  `depends_on` so the field shows for the new option.
- Adds `get_receipt_date(doc)`, which resolves the date from the **submitted** Purchase
  Receipts behind a Purchase Invoice. Where an invoice draws on several receipts the
  **earliest** governs, so a buyer cannot stretch the clock by invoicing late.
- Threads an optional `receipt_date` through `get_payment_terms` and
  `get_payment_term_details` to `get_due_date`. The parameter is optional and defaults to
  `None`, so every existing caller is unaffected.
- Falls back to the invoice date when nothing has been received, so a term of this kind can
  never produce a null due date on an invoice raised ahead of delivery.

`discount_validity_based_on` is deliberately **left invoice-based** — only the due date has
a receipt-side meaning.

### What this deliberately does not do

#42807 also asks for an MSME flag on the Supplier master, conditional calculation for such
suppliers, and reporting and notifications. I have not included those, because
`erpnext/regional/` has no India directory — India compliance lives in the separate
`india_compliance` app. What core is genuinely missing is the jurisdiction-neutral hook, and
that is all this PR adds. **This advances #42807 rather than closing it.**

For anyone picking up the compliance layer, three points in the issue's specification do not
match the Act, and would ship a non-compliant implementation:

1. **45 days is a ceiling for written terms, not a default.** s.15 allows 15 days where there
   is no written agreement. Hardcoding 45 reports a due date up to 30 days late.
2. **s.2(n) covers micro and small only.** Medium enterprises are excluded from the
   delayed-payment provisions, and from s.43B(h). A single "is MSME" checkbox voids valid
   contractual terms for them.
3. **The clock starts at acceptance, not receipt.** Under s.2(b) explanation (i), a written
   objection within 15 days defers acceptance until the objection is removed.

A worked redline of those three points, with the corrected rules runnable in the page, is at
https://drakeshnag-rjo.github.io/erpnext-msme-due-date/ — and a framework-free reference
implementation with 288 conformance vectors is at
https://github.com/drakeshnag-rjo/erpnext-msme-due-date. Both are offered as background for
whoever implements the compliance side; nothing from either is proposed for core.

### Testing

**What I ran:**

- `ruff check` and `ruff format --check` pass on both changed Python files.
- 11 unit tests executing this patched `get_due_date` directly, with `frappe` stubbed so the
  function can run outside a bench. Four of them pin the three pre-existing options
  (`Day(s) after invoice date`, `Day(s) after the end of the invoice month`, `Month(s) after
  the end of the invoice month`) so this change cannot regress them; the rest cover the new
  branch, the fallback, `bill_date` precedence, zero credit days and a leap-day receipt. The
  harness is
  [here](https://github.com/drakeshnag-rjo/erpnext-msme-due-date/blob/main/verify_erpnext_patch.py).
- Two tests added to `test_payment_terms_template.py`, following that file's existing
  DB-free pattern.

**What I could not run, and why this is a draft:** I do not have a bench, MariaDB or Redis
available, so ERPNext's own suite has not been run and the two tests added to
`test_payment_terms_template.py` are unexecuted in a live instance. I would rather say that
plainly than tick the checklist. Happy to iterate if a maintainer thinks the approach is
worth pursuing.

### Screenshots

None — the visible change is one additional entry in an existing Select field, and I could
not produce a screenshot without a running instance.
