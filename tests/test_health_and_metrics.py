from starlette.testclient import TestClient
from app.main import app


client = TestClient(app)


def test_health_ok():
   r = client.get("/health")
   assert r.status_code == 200
   assert r.json().get("status") == "ok"

def test_metrics_available():
   # trigger a simple request first so metrics have something to expose
   _ = client.get("/health")
   r = client.get("/metrics")
   assert r.status_code == 200
   assert "http_requests_total" in r.text
