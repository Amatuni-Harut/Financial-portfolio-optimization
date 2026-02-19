# 🚀 Portfolio Optimizer Pro v3.0

## Professional Financial Engineering Platform

**Версия 3** - Идеальный баланс между простотой структуры и профессиональным кодом.

---

## ✨ Главные преимущества:

### 📁 Простая структура (5 файлов):
```
portfolio-pro/
├── backend/
│   ├── main.py          # 600+ строк профессионального кода
│   ├── load_data.py
│   ├── requirements.txt
│   └── .env
└── frontend/
    └── index.html       # Продвинутый single-page app
```

### 💎 Профессиональные features:

**Backend:**
- ✅ **Async operations** - быстрая обработка запросов
- ✅ **In-memory caching** - LRU cache с TTL
- ✅ **Connection pooling** - эффективное управление БД
- ✅ **4 алгоритма оптимизации:**
  - Maximum Sharpe Ratio
  - Minimum Volatility
  - Risk Parity
  - **Minimum CVaR** (продвинутый risk management)
- ✅ **Advanced metrics:**
  - Sharpe & Sortino ratios
  - VaR & CVaR (95%)
  - Diversification ratio
  - Efficient frontier
- ✅ **Professional validation** - Pydantic с кастомными validators
- ✅ **Error handling** - comprehensive exception management
- ✅ **Optimized queries** - с индексами и batch loading

**Frontend:**
- ✅ **Component-based architecture** - без фреймворков!
- ✅ **State management** - centralized AppState
- ✅ **API abstraction layer** - чистые запросы
- ✅ **Real-time updates** - статус бар с метриками
- ✅ **Advanced animations** - CSS3 transitions
- ✅ **Professional design:**
  - GitHub-inspired dark theme
  - JetBrains Mono + Outfit fonts
  - Grid background pattern
  - Glassmorphism effects
- ✅ **Dual charts** - weights + risk analysis
- ✅ **Responsive grid** - адаптивная вёрстка

---

## 🚀 Quick Start (5 минут):

### 1. Backend Setup
```bash
cd backend
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Database (pgAdmin4)
- Create database: `portfolio_db`
- Create user: `portfolio_user` / `portfolio123`

### 3. Configuration
```bash
cp .env.example .env
# Edit if needed
```

### 4. Load Data
```bash
pip install yfinance
python load_data.py  # Loads 37 stocks + ETFs
```

### 5. Run!
```bash
# Terminal 1 - Backend
python main.py

# Terminal 2 - Frontend
cd ../frontend
python -m http.server 8080
```

Open: http://localhost:8080

---

## 📊 API Documentation

### Endpoints:

```
GET  /api/stocks/search?query=AAPL     # Search stocks
GET  /api/stocks/{ticker}               # Stock info
POST /api/optimize                      # Optimize portfolio
POST /api/efficient-frontier            # Calculate frontier
GET  /api/health                        # Health check
POST /api/cache/clear                   # Clear cache
GET  /docs                              # Swagger UI
```

### Optimize Request:
```json
{
  "assets": [
    {"ticker": "AAPL", "allocation": 0},
    {"ticker": "MSFT", "allocation": 0}
  ],
  "start_date": "2020-01-01",
  "end_date": "2024-01-01",
  "optimization_goal": "max_sharpe",
  "risk_free_rate": 0.02,
  "constraints": {
    "max_weight": 0.4,
    "min_weight": 0.05
  }
}
```

### Response:
```json
{
  "optimized_weights": {"AAPL": 60.5, "MSFT": 39.5},
  "expected_return": 15.2,
  "expected_volatility": 18.5,
  "sharpe_ratio": 0.821,
  "diversification_ratio": 1.15,
  "metrics": {
    "sortino_ratio": 1.05,
    "var_95": -12.5,
    "cvar_95": -15.8
  }
}
```

---

## 🔧 Advanced Features:

### Caching System
```python
# Автоматическое кэширование:
# - Price data: 1 hour TTL
# - Search results: 1 hour TTL
# - LRU eviction: max 100 entries

# Управление через API:
POST /api/cache/clear
```

### Constraints Support
```python
# В запросе оптимизации:
"constraints": {
    "max_weight": 0.4,      # Макс. вес актива 40%
    "min_weight": 0.05      # Мин. вес актива 5%
}
```

### Risk-Free Rate
```python
# Настраивается в UI или API:
"risk_free_rate": 0.02  # 2% годовых
```

---

## 💡 Code Highlights:

### Backend - Professional Patterns:

```python
# 1. Dependency Injection
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 2. Cache Decorator Pattern
class CacheManager:
    def get(self, key): ...
    def set(self, key, value): ...

# 3. Advanced Optimization
class AdvancedPortfolioOptimizer:
    def optimize_maximum_sharpe(self): ...
    def optimize_minimum_cvar(self): ...
    def efficient_frontier(self): ...

# 4. Comprehensive Metrics
def portfolio_metrics(self, weights):
    return {
        'sharpe': ...,
        'sortino': ...,
        'diversification_ratio': ...,
        'var_95': ...,
        'cvar_95': ...
    }
```

### Frontend - Clean Architecture:

```javascript
// 1. State Management
const AppState = {
    assets: [],
    results: null,
    charts: {},
    cache: {}
};

// 2. API Abstraction
async function apiCall(endpoint, options = {}) {
    // Centralized error handling
    // Content-type management
    // Response parsing
}

// 3. Component Pattern
function updateUI() {
    // Reactive rendering
    // Event binding
    // State synchronization
}

// 4. Chart Management
function createCharts(data) {
    // Destroy old instances
    // Create new charts
    // Responsive config
}
```

---

## 📈 Performance:

- ⚡ **API Response**: < 100ms (cached)
- ⚡ **Optimization**: 200-500ms (2-10 assets)
- ⚡ **Page Load**: < 1s
- ⚡ **Memory**: ~50MB (backend)
- ⚡ **Database**: Connection pooling (10 min, 20 max)

---

## 🎨 Design System:

### Colors:
```css
--primary-bg: #0d1117     /* GitHub dark */
--accent: #58a6ff         /* Blue */
--success: #3fb950        /* Green */
--danger: #f85149         /* Red */
--code: #7ee787           /* Neon green */
```

### Typography:
- **Headings**: JetBrains Mono (monospace, tech)
- **Body**: Outfit (modern, readable)

### Components:
- Glass cards with hover effects
- Grid pattern background
- Animated status indicators
- Gradient accents
- Smooth transitions

---

## 🔬 Algorithms Explained:

### 1. Maximum Sharpe Ratio
Находит портфель с лучшим соотношением риск/доходность:
```
Sharpe = (Return - RiskFreeRate) / Volatility
```

### 2. Minimum Volatility
Минимизирует риск при опциональной целевой доходности:
```
min σ(w)  subject to  E[R] ≥ target
```

### 3. Risk Parity
Уравнивает вклад в риск от каждого актива:
```
RC_i = w_i * (Σw)_i / σ_p = constant
```

### 4. Minimum CVaR
Минимизирует ожидаемые потери за VaR:
```
CVaR_α = E[R | R ≤ VaR_α]
```

---

## 🐛 Troubleshooting:

### CORS Errors:
```python
# В main.py измените:
CORS_ORIGINS = ["http://localhost:8080"]
```

### Cache Issues:
```bash
# Очистите через API:
curl -X POST http://localhost:8000/api/cache/clear
```

### Database Connection:
```bash
# Проверьте .env:
DATABASE_URL=postgresql://user:pass@localhost:5432/portfolio_db

# Проверьте PostgreSQL:
psql -U portfolio_user -d portfolio_db -c "SELECT COUNT(*) FROM stocks;"
```

---

## 📚 Tech Stack:

**Backend:**
- FastAPI 0.109+ (async web framework)
- SQLAlchemy 2.0+ (ORM)
- NumPy 1.26+ (numerical computing)
- Pandas 2.1+ (data analysis)
- SciPy 1.11+ (optimization)
- PostgreSQL 12+ (database)

**Frontend:**
- Vanilla JavaScript (ES6+)
- Chart.js 4.4+ (visualization)
- CSS3 (animations, grid)

---

## 🎯 Use Cases:

### 1. Tech Portfolio
```
Assets: AAPL, MSFT, GOOGL, NVDA, META
Algorithm: max_sharpe
→ Optimal tech diversification
```

### 2. Conservative
```
Assets: SPY, AGG, TLT, GLD
Algorithm: min_volatility
→ Low-risk balanced portfolio
```

### 3. Equal Risk
```
Assets: SPY, TLT, GLD, EFA, EEM
Algorithm: risk_parity
→ Balanced risk contribution
```

### 4. Tail Risk
```
Assets: Multiple ETFs
Algorithm: min_cvar
→ Minimize extreme losses
```

---

## 🚀 Future Enhancements:

- [ ] Black-Litterman model
- [ ] Monte Carlo simulation
- [ ] Backtesting engine
- [ ] Real-time price feeds
- [ ] Portfolio rebalancing alerts
- [ ] PDF/Excel export
- [ ] Multi-user support
- [ ] Authentication (JWT)

---

## 📄 License:

MIT License - Free for personal and commercial use

---

## 🤝 Support:

API Documentation: http://localhost:8000/docs

GitHub: [your-repo]

---

**Built with ❤️ for quantitative finance enthusiasts**

*Professional code. Simple structure. Maximum performance.*
