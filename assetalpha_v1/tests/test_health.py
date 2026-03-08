"""
test_health.py — Тесты системных эндпоинтов (/health, /cache).
"""


class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_health_has_required_fields(self, client):
        data = client.get("/health").json()
        assert "status" in data
        assert "db_connected" in data
        assert "version" in data

    def test_health_status_ok(self, client):
        data = client.get("/health").json()
        assert data["status"] == "ok"

    def test_health_version(self, client):
        data = client.get("/health").json()
        assert data["version"] == "2.0.0"

    def test_health_db_connected_is_bool(self, client):
        data = client.get("/health").json()
        assert isinstance(data["db_connected"], bool)

    def test_clear_cache_returns_200(self, client):
        r = client.delete("/cache")
        assert r.status_code == 200

    def test_clear_cache_message(self, client):
        data = client.delete("/cache").json()
        assert "message" in data
