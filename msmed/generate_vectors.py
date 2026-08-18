# Emits the shared conformance vectors.
#
# The Python module is the reference implementation -- it is the one an ERPNext
# or india_compliance maintainer would merge. The JavaScript port that drives the
# published page is tested against these, so the page can never quietly disagree
# with the module it documents.
#
# Run: python msmed/generate_vectors.py

import json
import os
from datetime import date

from due_date import MEDIUM, MICRO, SMALL, statutory_due_date

ACCEPTANCE_DATES = [date(2026, 4, 1), date(2026, 12, 15), date(2028, 2, 29)]
AGREED_DAYS = [0, 15, 30, 45, 46, 60, 90, 120]
CATEGORIES = [MICRO, SMALL, MEDIUM]

vectors = []
for accepted in ACCEPTANCE_DATES:
    for agreed in AGREED_DAYS:
        for written in (True, False):
            for category in CATEGORIES:
                for udyam in (True, False):
                    r = statutory_due_date(
                        acceptance_date=accepted,
                        agreed_days=agreed,
                        has_written_agreement=written,
                        category=category,
                        udyam_registered=udyam,
                    )
                    vectors.append(
                        {
                            "input": {
                                "acceptanceDate": accepted.isoformat(),
                                "agreedDays": agreed,
                                "hasWrittenAgreement": written,
                                "category": category,
                                "udyamRegistered": udyam,
                            },
                            "expected": {
                                "protected": r.protected,
                                "allowedDays": r.allowed_days,
                                "dueDate": r.due_date.isoformat(),
                                "appointedDate": r.appointed_date.isoformat() if r.appointed_date else None,
                                "capped": r.capped,
                                "voidedDays": r.voided_days,
                            },
                        }
                    )

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "vectors.json")
with open(os.path.normpath(out), "w", encoding="utf-8") as fh:
    json.dump(vectors, fh, indent=1)
    fh.write("\n")

print(f"wrote {len(vectors)} vectors to vectors.json")
