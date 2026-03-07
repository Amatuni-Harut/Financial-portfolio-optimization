"""
test_assets.py — Тесты эндпоинтов поиска активов (/api/stocks/search, /api/assets/{ticker}/details).
"""
import pytest
from unittest.mock import patch


class TestStockSearch:
    def test_search_returns_200(self, client):
        r = client.get("/api/stocks/search?query=AAPL")
        assert r.status_code == 200

    def test_search_returns_list(self, client):
        data = client.get("/api/stocks/search?query=AAPL").json()
        assert isinstance(data, list)

    def test_search_result_has_required_fields(self, client):
        data = client.get("/api/stocks/search?query=AAPL").json()
        if data:
            item = data[0]
            assert "ticker" in item
            assert "name" in item
            assert "sector" in item

    def test_search_case_insensitive(self, client):
        """Поиск нечувствителен к регистру."""
        lower = client.get("/api/stocks/search?query=aapl").json()
        upper = client.get("/api/stocks/search?query=AAPL").json()
        assert lower == upper

    def test_search_empty_query_returns_422(self, client):
        """Пустой query → ошибка валидации."""
        r = client.get("/api/stocks/search?query=")
        assert r.status_code == 422

    def test_search_no_query_param_returns_422(self, client):
        """Отсутствие query → 422."""
        r = client.get("/api/stocks/search")
        assert r.status_code == 422

    def test_search_returns_max_10_results(self, client):
        """Результатов должно быть не больше 10."""
        data = client.get("/api/stocks/search?query=A").json()
        assert len(data) <= 10


class TestAssetDetails:
    def test_details_returns_200(self, client):
        r = client.get("/api/assets/AAPL/details")
        assert r.status_code == 200

    def test_details_has_required_fields(self, client):
        data = client.get("/api/assets/AAPL/details").json()
        required = {"ticker", "name", "price", "change", "sharpe", "history"}
        assert required.issubset(data.keys())

    def test_details_ticker_uppercase(self, client):
        """Тикер должен нормализоваться в uppercase."""
        data = client.get("/api/assets/aapl/details").json()
        assert data.get("ticker", "").upper() == "AAPL"

    def test_details_price_default_currency_usd(self, client):
        """По умолчанию цена в USD (символ $)."""
        data = client.get("/api/assets/AAPL/details").json()
        assert "$" in data.get("price", "")

    def test_details_unknown_ticker_returns_404(self, client):
        """Несуществующий тикер → 404."""
        with patch(
            "app.services.data_service.get_asset_details",
            side_effect=ValueError("Тикер не найден"),
        ):
            r = client.get("/api/assets/UNKNOWN_TICKER_XYZ/details")
            assert r.status_code == 404
