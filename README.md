# ERPNext #42807 — MSME statutory due dates

A contribution to [frappe/erpnext#42807](https://github.com/frappe/erpnext/issues/42807),
*"Add Due Date Calculation for MSME Suppliers Based on Finance Act 43B(H)"* — open since
17 August 2024, no comments, no PR.

**→ [Read the redline](https://drakeshnag-rjo.github.io/erpnext-msme-due-date/)** — the
three specification corrections, with the corrected rules runnable in the page.

## The short version

The feature request is right: ERPNext has no way to run a payment term from the date goods
were received, and India's MSMED Act requires exactly that. The specification in the issue
is wrong in three places, each of which would ship a non-compliant implementation.

| # | The issue says | The Act says | Cost of the error |
|---|---|---|---|
| 1 | 45 days | 45 days **with a written agreement**, 15 days without (s.15) | Due date up to **30 days late** on informal purchases |
| 2 | Flag suppliers as "MSME" | Micro and **small only** — medium are excluded (s.2(n)) | **Voids valid contract terms** for medium suppliers |
| 3 | Clock starts at receipt | Clock starts at **acceptance**, deferred by a written objection within 15 days (s.2(b)) | **Overstates interest** on disputed deliveries |

Worked against a 1 April 2026 acceptance, the issue's logic and the Act diverge on three of
four ordinary cases — by −30, −15 and **+45** days.

## What is proposed

**In core** — a generic hook, not Indian law. `erpnext/regional/` has no India directory,
because India compliance lives in the separate `india_compliance` app. What core is actually
missing is a payment term that runs from receipt, which is not an Indian idea: the EU Late
Payment Directive 2011/7/EU runs from receipt of the goods too.

```
erpnext/accounts/services/payment_schedule.py      +49 −11
erpnext/accounts/doctype/payment_term/…json         +4 −4
erpnext/accounts/doctype/payment_terms_template_detail/…json   +4 −4
erpnext/accounts/doctype/payment_schedule/…json     +4 −4
erpnext/accounts/doctype/payment_terms_template/test_…py       +57
```

- Adds `Day(s) after receipt date` to `due_date_based_on` — and deliberately **not** to
  `discount_validity_based_on`, which stays invoice-based.
- Resolves the receipt date from the submitted Purchase Receipts behind the invoice, taking
  the **earliest**, so a buyer cannot stretch the clock by invoicing late.
- Falls back to the invoice date when nothing has been received, so the term can never
  produce a null due date.

**Outside core** — `msmed/due_date.py`, a framework-free reference implementation of s.15,
s.2(b) and s.43B(h), for whoever implements the compliance layer.

## Layout

```
patch/            The core patch, verified to `git apply` cleanly against 1f83906.
msmed/due_date.py Reference implementation. Pure Python, no framework import.
msmed/test_due_date.py        20 tests, runnable with plain `python -m unittest`.
msmed/generate_vectors.py     Emits the shared conformance vectors.
verify_erpnext_patch.py       Executes ERPNext's real patched source, frappe stubbed.
src/msmed.js      JS port that drives the page, held to the Python by vectors.json.
web/ · build.js · docs/       The redline page, inlined into one self-contained file.
test/             18 tests: 288-vector conformance, plus the page executed headlessly.
```

## Running it

```sh
python -m unittest discover -s msmed -v   # 20 — the statute
python verify_erpnext_patch.py            # 11 — ERPNext's real patched function
python msmed/generate_vectors.py          # regenerate the 288 vectors
node --test "test/*.test.js"              # 18 — parity + the page
node build.js                             # -> docs/index.html
```

## How it was verified

- **The statute, in isolation.** 20 tests on the reference implementation, in a plain Python
  process. Boundaries are asserted on both sides: day 45 is not capped, day 46 is; the 15-day
  objection window includes day 15 and excludes day 16.
- **ERPNext's actual code.** `verify_erpnext_patch.py` stubs `frappe` and loads the patched
  `payment_schedule.py` straight off disk, so the new branch is executed rather than eyeballed.
  Four of its eleven tests pin the three pre-existing options, so the change cannot regress
  them.
- **Cross-language conformance.** The Python module emits 288 vectors across every combination
  of period, agreement, category, registration and three acceptance dates including a leap
  day. The JavaScript port that drives the page is asserted against all of them, so the page
  cannot describe rules the mergeable module does not implement.
- **The patch applies.** Confirmed clean against `1f83906` on `develop`.

**Not verified:** ERPNext's own suite needs bench, MariaDB and Redis, none of which were
available. The two tests added to `test_payment_terms_template.py` follow that file's
existing DB-free pattern, but have not been run inside a live instance. They should be before
any PR is opened.

## Sources

MSMED Act 2006 ss.2(b), 2(n), 15, 16. Income Tax Act 1961 s.43B(h), inserted by the Finance
Act 2023, effective AY 2024–25, reaching micro and small enterprises only and excluding
traders. Classification per notification S.O. 1364(E) of 21 March 2025, in force 1 April
2025, on composite criteria. Verified August 2026.

Not legal advice — a specification review offered to an open source project.
