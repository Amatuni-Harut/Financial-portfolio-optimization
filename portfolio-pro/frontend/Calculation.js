// ============================================
// STATE MANAGEMENT
// ============================================
const AppState = {
    assets: [],
    results: null,
    charts: { weights: null, risk: null },
    cache: { enabled: true, hits: 0 }
};

const API_URL = 'http://localhost:8000/api';

// ============================================
// INITIALIZATION
// ============================================
document.addEventListener('DOMContentLoaded', () => {
    initDates();
    bindEvents();
    updateUI();
});

function initDates() {
    const end = new Date();
    const start = new Date();
    start.setFullYear(end.getFullYear() - 3);
    document.getElementById('endDate').valueAsDate = end;
    document.getElementById('startDate').valueAsDate = start;
}

function bindEvents() {
    const search = document.getElementById('searchInput');
    let timeout;
    search.addEventListener('input', (e) => {
        clearTimeout(timeout);
        timeout = setTimeout(() => handleSearch(e.target.value), 300);
    });
    search.addEventListener('blur', () => setTimeout(hideSearch, 200));

    document.getElementById('optimizeBtn').addEventListener('click', optimize);
    document.getElementById('frontierBtn').addEventListener('click', showFrontier);
    document.getElementById('clearCacheBtn').addEventListener('click', clearCache);
}

// ============================================
// API LAYER
// ============================================
async function apiCall(endpoint, options = {}) {
    try {
        const response = await fetch(`${API_URL}${endpoint}`, {
            headers: { 'Content-Type': 'application/json' },
            ...options
        });
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API Error');
        }
        return await response.json();
    } catch (err) {
        console.error('API Error:', err);
        alert(`Error: ${err.message}`);
        throw err;
    }
}

// ============================================
// SEARCH
// ============================================
async function handleSearch(query) {
    if (query.length < 2) {
        hideSearch();
        return;
    }

    const results = await apiCall(`/stocks/search?query=${query}`);
    displaySearch(results);
}

function displaySearch(stocks) {
    const container = document.getElementById('searchResults');
    if (!stocks.length) {
        container.innerHTML = '<div class="search-item">No results found</div>';
    } else {
        container.innerHTML = stocks.map(s => `
                    <div class="search-item" onclick="addAsset('${s.ticker}', '${s.name}', '${s.sector || ''}')">
                        <div>
                            <span class="search-ticker">${s.ticker}</span>
                            <span class="search-name">${s.name}</span>
                        </div>
                        ${s.sector ? `<span class="search-sector">${s.sector}</span>` : ''}
                    </div>
                `).join('');
    }
    container.classList.add('active');
}

function hideSearch() {
    document.getElementById('searchResults').classList.remove('active');
}

// ============================================
// ASSET MANAGEMENT
// ============================================
function addAsset(ticker, name, sector) {
    if (AppState.assets.some(a => a.ticker === ticker)) {
        alert('Asset already added!');
        return;
    }
    AppState.assets.push({ ticker, name, sector });
    document.getElementById('searchInput').value = '';
    updateUI();
}

function removeAsset(ticker) {
    AppState.assets = AppState.assets.filter(a => a.ticker !== ticker);
    updateUI();
}

function updateUI() {
    const container = document.getElementById('assetList');
    const badge = document.getElementById('assetBadge');
    const count = document.getElementById('assetCount');

    badge.textContent = `${AppState.assets.length} SELECTED`;
    count.textContent = `Assets: ${AppState.assets.length}`;

    if (!AppState.assets.length) {
        container.innerHTML = `
                    <div class="empty-state">
                        <div class="empty-icon">📈</div>
                        <p>Add minimum 2 assets to begin optimization</p>
                    </div>
                `;
    } else {
        container.innerHTML = AppState.assets.map(a => `
                    <div class="asset-card">
                        <div class="asset-info">
                            <div class="asset-ticker">${a.ticker}</div>
                            <div class="asset-name">${a.name}</div>
                        </div>
                        <button class="btn btn-danger" onclick="removeAsset('${a.ticker}')">✕</button>
                    </div>
                `).join('');
    }
}

// ============================================
// OPTIMIZATION
// ============================================
async function optimize() {
    if (AppState.assets.length < 2) {
        alert('Add minimum 2 assets!');
        return;
    }

    const loader = document.getElementById('loader');
    const results = document.getElementById('results');

    loader.classList.add('active');
    results.style.display = 'none';

    try {
        const payload = {
            assets: AppState.assets.map(a => ({ ticker: a.ticker, allocation: 0 })),
            start_date: document.getElementById('startDate').value,
            end_date: document.getElementById('endDate').value,
            optimization_goal: document.getElementById('algorithm').value,
            risk_free_rate: parseFloat(document.getElementById('riskFreeRate').value) / 100
        };

        const data = await apiCall('/optimize', {
            method: 'POST',
            body: JSON.stringify(payload)
        });

        AppState.results = data;
        displayResults(data);
    } finally {
        loader.classList.remove('active');
    }
}

function displayResults(data) {
    document.getElementById('metricReturn').textContent = data.expected_return.toFixed(2) + '%';
    document.getElementById('metricVol').textContent = data.expected_volatility.toFixed(2) + '%';
    document.getElementById('metricSharpe').textContent = data.sharpe_ratio.toFixed(3);
    document.getElementById('metricSortino').textContent = data.metrics.sortino_ratio.toFixed(3);
    document.getElementById('metricDiv').textContent = data.diversification_ratio.toFixed(3);
    document.getElementById('metricCVaR').textContent = data.metrics.cvar_95.toFixed(2) + '%';

    createCharts(data);

    document.getElementById('results').style.display = 'block';
    document.getElementById('results').scrollIntoView({ behavior: 'smooth' });
}

function createCharts(data) {
    const tickers = Object.keys(data.optimized_weights);
    const weights = Object.values(data.optimized_weights);

    // Weights Chart
    if (AppState.charts.weights) AppState.charts.weights.destroy();
    AppState.charts.weights = new Chart(document.getElementById('weightsChart'), {
        type: 'doughnut',
        data: {
            labels: tickers,
            datasets: [{
                data: weights,
                backgroundColor: ['#58a6ff', '#7ee787', '#d29922', '#f85149', '#a371f7', '#ffa657']
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#c9d1d9', font: { family: 'JetBrains Mono' } }
                }
            }
        }
    });

    // Risk Chart
    if (AppState.charts.risk) AppState.charts.risk.destroy();
    AppState.charts.risk = new Chart(document.getElementById('riskChart'), {
        type: 'bar',
        data: {
            labels: ['Return', 'Volatility', 'Sharpe', 'Sortino', 'Diversification'],
            datasets: [{
                label: 'Metrics',
                data: [
                    data.expected_return,
                    data.expected_volatility,
                    data.sharpe_ratio * 10,
                    data.metrics.sortino_ratio * 10,
                    data.diversification_ratio * 100
                ],
                backgroundColor: '#58a6ff'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                y: {
                    ticks: { color: '#8b949e' },
                    grid: { color: '#30363d' }
                },
                x: {
                    ticks: { color: '#8b949e' },
                    grid: { display: false }
                }
            }
        }
    });
}

async function showFrontier() {
    alert('Efficient Frontier visualization - Coming soon!');
}

async function clearCache() {
    await apiCall('/cache/clear', { method: 'POST' });
    document.getElementById('cacheStatus').textContent = 'Cache: Cleared';
    setTimeout(() => {
        document.getElementById('cacheStatus').textContent = 'Cache: Ready';
    }, 2000);
}