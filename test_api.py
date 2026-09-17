import os
import tempfile
from pathlib import Path

os.environ["COMMERCE_MODE"] = "catalog"
os.environ["COMMERCE_BASE"] = str(Path(__file__).resolve().parent)
os.environ["COMMERCE_DB"] = str(Path(tempfile.mkdtemp(prefix="evez-commerce-api-")) / "commerce.db")

from fastapi.testclient import TestClient
from server import app

client = TestClient(app)
health = client.get("/health")
assert health.status_code == 200, health.text
assert health.json()["commerce_mode"] == "catalog"
assert health.json()["stripe_ready"] is False
products = client.get("/products")
assert products.status_code == 200, products.text
assert products.json()["count"] == 6
checkout = client.post("/checkout", json={"product_id": "research-agent"})
assert checkout.status_code == 503, checkout.text
print("catalog mode API checks passed")
