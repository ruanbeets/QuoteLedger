"""Small, clearly fictional demo data."""

from .extraction import extract
from .storage import create_quote, create_request, list_requests

SAMPLES = [
    """Supplier: Boxline Packaging
Product: 300 x 220 x 110 mm single-wall mailer box
Currency: ZAR
Price per box: R 12.40
MOQ: 500
Lead time: 7 business days
Transport: R 850.00
Payment terms: 30 days from invoice
Valid until: 2026-12-31""",
    """Supplier: CartonWorks
Product: 300 x 220 x 110 mm single-wall mailer box
Currency: ZAR
Price: R 115.00
Price unit: pack
Pack size: 10
MOQ: 1200
Lead time: 12 business days
Transport: R 1200.00
Payment terms: 50% deposit, balance on delivery
Exceptions: Die tooling charged separately
Valid until: 2026-12-15""",
    """Supplier: RapidPack
Product: 300 x 220 x 110 mm single-wall mailer box
Currency: ZAR
Price per 100: R 1320.00
MOQ: 100
Lead time: 4 business days
Transport: R 0.00
Payment terms: EFT before dispatch
Valid until: 2026-11-30""",
]


def seed(db):
    if list_requests(db):
        return
    request = create_request(db, "Q4 mailer box replenishment",
                             "300 × 220 × 110 mm, single-wall kraft mailer box; plain print; delivered to Johannesburg",
                             1000)
    for index, text in enumerate(SAMPLES, 1):
        fields, evidence = extract(text)
        create_quote(db, request["id"], f"sample-quote-{index}.txt", text, None, fields, evidence)
