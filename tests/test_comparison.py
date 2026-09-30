import unittest

from quoteledger.comparison import compare, evaluate, validate_fields
from quoteledger.extraction import extract


class ComparisonTests(unittest.TestCase):
    def quote(self, **changes):
        fields = dict(supplier="Acme", product="Mailer", currency="ZAR", unit_price="115",
                      price_unit="pack", pack_size="10", moq="1200", lead_days="7",
                      transport_cost="1200", payment_terms="30 days", exceptions="",
                      fx_to_zar="", fx_source="", valid_until="")
        fields.update(changes)
        return dict(id=1, status="reviewed", fields=fields)

    def test_pack_price_moq_and_transport(self):
        result = evaluate(dict(quantity=1000), self.quote())
        self.assertEqual(result["unit_price_zar"], "11.50")
        self.assertEqual(result["order_quantity"], 1200)
        self.assertEqual(result["landed_total_zar"], "15000.00")
        self.assertEqual(result["effective_per_requested_box_zar"], "15.00")
        self.assertIn("MOQ exceeds request by 200 boxes", result["issues"])

    def test_foreign_currency_requires_sourced_rate(self):
        result = evaluate(dict(quantity=1000), self.quote(currency="USD", price_unit="each", unit_price="1", moq="100", transport_cost="20"))
        self.assertFalse(result["comparable"])
        self.assertIn("Exchange rate and source required", result["issues"])
        result = evaluate(dict(quantity=1000), self.quote(currency="USD", price_unit="each", unit_price="1", moq="100", transport_cost="20", fx_to_zar="18", fx_source="Bank quote 2026-09-30"))
        self.assertEqual(result["landed_total_zar"], "18360.00")

    def test_pack_order_rounds_to_full_packs(self):
        result = evaluate(dict(quantity=1003), self.quote(moq="500", transport_cost="0"))
        self.assertEqual(result["order_quantity"], 1010)
        self.assertEqual(result["landed_total_zar"], "11615.00")
        self.assertIn("Order rounded up to full packs", result["issues"])

    def test_only_reviewed_complete_quote_can_be_lowest(self):
        request = dict(quantity=1000)
        draft = self.quote(unit_price="1", price_unit="each", pack_size="", moq="1000", transport_cost="0")
        draft["status"] = "needs_review"
        reviewed = self.quote(unit_price="2", price_unit="each", pack_size="", moq="1000", transport_cost="0")
        reviewed["id"] = 2
        rows = compare(request, [draft, reviewed])
        self.assertFalse(rows[0]["lowest_reviewed"])
        self.assertTrue(rows[1]["lowest_reviewed"])

    def test_invalid_values_rejected(self):
        with self.assertRaises(ValueError):
            validate_fields({"unit_price": "-1"})
        with self.assertRaises(ValueError):
            validate_fields({"moq": "1.5"})

    def test_extraction_keeps_evidence(self):
        fields, evidence = extract("Supplier: Boxline\nPrice per box: R 12.40\nMOQ: 500\nTransport: R 0.00")
        self.assertEqual(fields["unit_price"], "12.40")
        self.assertEqual(fields["price_unit"], "each")
        self.assertEqual(fields["transport_cost"], "0.00")
        self.assertEqual(evidence["unit_price"], "Price per box: R 12.40")


if __name__ == "__main__":
    unittest.main()
