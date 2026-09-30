import io
import json
import os
import unittest
from unittest.mock import patch

from quoteledger.ai import enrich
from quoteledger.extraction import extract


class AiTests(unittest.TestCase):
    def test_model_fills_only_missing_fields_with_real_source_lines(self):
        text = "Supplier: PackRight\nWe can deliver 750 boxes in 9 business days.\nNo quote for shipping yet."
        fields, evidence = extract(text)
        reply = {"response": json.dumps({"fields": {"lead_days": "9", "transport_cost": "0", "moq": "750"},
                                          "evidence": {"lead_days": "We can deliver 750 boxes in 9 business days.",
                                                       "transport_cost": "Invented source line",
                                                       "moq": "We can deliver 750 boxes in 9 business days."}})}
        with patch.dict(os.environ, {"QUOTELEDGER_OLLAMA_URL": "http://localhost:11434"}):
            with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(reply).encode())):
                fields, evidence = enrich(text, fields, evidence)
        self.assertEqual(fields["supplier"], "PackRight")
        self.assertEqual(fields["lead_days"], "9")
        self.assertEqual(fields["moq"], "750")
        self.assertEqual(fields["transport_cost"], "")
        self.assertIn("Ollama", evidence["_engine"])


if __name__ == "__main__":
    unittest.main()
