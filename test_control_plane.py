import json
import os
import tempfile
import unittest
from pathlib import Path

os.environ["COMMERCE_MODE"] = "catalog"
os.environ["COMMERCE_BASE"] = tempfile.mkdtemp(prefix="evez-commerce-test-")

from utm import campaign_url


class ControlPlaneTests(unittest.TestCase):
    def test_catalog_has_six_products_and_integer_prices(self):
        catalog = json.loads(Path("catalog.json").read_text())
        self.assertEqual(len(catalog["products"]), 6)
        self.assertTrue(all(isinstance(product["price_cents"], int) for product in catalog["products"]))
        self.assertEqual(len({product["id"] for product in catalog["products"]}), 6)

    def test_utm_link_is_canonical_and_measurable(self):
        result = campaign_url("https://catalog.example", "research-agent", "linkedin", "organic", "evez-first-use-case", "evidence")
        self.assertTrue(result.startswith("https://catalog.example/product/research-agent?"))
        self.assertIn("utm_source=linkedin", result)
        self.assertIn("utm_content=evidence", result)


if __name__ == "__main__":
    unittest.main()
