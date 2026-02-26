/**
 * market.js — логика страницы скринера рынка.
 * Зависит от: appState.js, api.js
 */

let fullMarketData = [];  // кэш данных для фильтрации без повторных запросов
let detailChart = null;

document.addEventListener('DOMContentLoaded', () => {
    loadMarketData();
    initModalClose();
});

/* -----------------------------------------------
   Загрузка и отрисовка таблицы
----------------------------------------------- */
async function loadMarketData() {
    try {
        const response = await fetchMarketData();
        fullMarketData = response.data || [];
        renderTable(fullMarketData);
        renderTrending(fullMarketData.slice(0, 5));
    } catch (err) {
        console.error('Ошибка загрузки скринера:', err.message);
        document.getElementById('marketTableBody').innerHTML =
            '<tr><td colspan="6" class="table-error">Ошибка загрузки данных. Попробуйте позже.</td></tr>';
    }
}

function renderTable(data) {
    const tbody = document.getElementById('marketTableBody');

    if (!data.length) {
        tbody.innerHTML = '<tr><td colspan="6" class="table-empty">Ничего не найдено</td></tr>';
        return;
    }

    tbody.innerHTML = data.map((item, i) => `
        <tr>
            <td><span class="coin-rank">${i + 1}</span></td>
            <td>
                <div class="coin-cell" onclick="openAssetModal('${item.symbol}', '${item.name}')" style="cursor:pointer;">
                    <div class="coin-icon">${item.symbol[0]}</div>
                    <div>
                        <div class="coin-name">${item.name}</div>
                        <div class="coin-symbol">${item.symbol}</div>
                    </div>
                </div>
            </td>
            <td class="text-right price-cell">${item.price}</td>
            <td class="text-right change-cell ${item.change >= 0 ? 'positive' : 'negative'}">
                ${item.change >= 0 ? '+' : ''}${item.change}%
            </td>
            <td class="text-right volume-cell">${item.marketCap}</td>
            <td>
                <button class="btn-icon star-btn" title="Добавить в избранное">☆</button>
            </td>
        </tr>
    `).join('');

    // Звёздочки — избранное
    tbody.querySelectorAll('.star-btn').forEach((btn, i) => {
        btn.addEventListener('click', () => {
            const isFav = btn.textContent === '★';
            btn.textContent = isFav ? '☆' : '★';
            btn.classList.toggle('active', !isFav);
        });
    });
}

function renderTrending(stocks) {
    const container = document.getElementById('topStocksContainer');
    if (!container || !stocks.length) return;

    container.innerHTML = stocks.map((s, i) => `
        <div class="trending-item">
            <div class="trending-rank">${i + 1}</div>
            <div class="trending-coin">
                <div class="trending-icon">${s.symbol[0]}</div>
                <div>
                    <div class="trending-name">${s.name}</div>
                    <div class="trending-symbol">${s.symbol}</div>
                </div>
            </div>
            <div class="trending-change ${s.change >= 0 ? 'positive' : 'negative'}">
                ${s.change >= 0 ? '+' : ''}${s.change}%
            </div>
        </div>
    `).join('');
}

/* -----------------------------------------------
   Поиск (локальный, без лишних запросов)
----------------------------------------------- */
document.getElementById('marketSearch')?.addEventListener('input', (e) => {
    const q = e.target.value.toLowerCase().trim();
    const filtered = q
        ? fullMarketData.filter(item =>
            item.symbol.toLowerCase().includes(q) ||
            item.name.toLowerCase().includes(q))
        : fullMarketData;
    renderTable(filtered);
});

/* -----------------------------------------------
   Модальное окно с деталями актива
----------------------------------------------- */
async function openAssetModal(symbol, name) {
    const modal = document.getElementById('assetModal');
    modal.style.display = 'flex';

    document.getElementById('modalAssetTitle').textContent = `${name} (${symbol})`;
    document.getElementById('modalAssetIcon').textContent = symbol[0];
    document.getElementById('modalAssetPrice').textContent = '...';
    document.getElementById('modalAssetChange').textContent = '...';

    try {
        const data = await fetchAssetDetails(symbol);

        document.getElementById('modalAssetPrice').textContent = data.price;

        const changeEl = document.getElementById('modalAssetChange');
        changeEl.textContent = data.change;
        changeEl.className = `metric-value ${data.change.includes('+') ? 'positive' : 'negative'}`;

        renderDetailChart(data.history);
    } catch (err) {
        console.error('Ошибка загрузки деталей:', err.message);
        document.getElementById('modalAssetPrice').textContent = 'Ошибка';
    }
}

function renderDetailChart(historyData) {
    const ctx = document.getElementById('assetDetailChart').getContext('2d');
    if (detailChart) detailChart.destroy();

    detailChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: historyData.map(d => d.date),
            datasets: [{
                label: 'Цена',
                data: historyData.map(d => d.price),
                borderColor: '#A1A364',
                backgroundColor: 'rgba(161, 163, 100, 0.1)',
                borderWidth: 2,
                fill: true,
                tension: 0.4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { ticks: { color: 'var(--text-secondary)' }, grid: { color: 'var(--border)' } },
                x: { ticks: { color: 'var(--text-secondary)' }, grid: { display: false } }
            }
        }
    });
}

function initModalClose() {
    const modal = document.getElementById('assetModal');
    const closeBtn = document.getElementById('closeModalBtn');

    closeBtn?.addEventListener('click', () => modal.style.display = 'none');
    modal?.addEventListener('click', (e) => {
        if (e.target === modal) modal.style.display = 'none';
    });
}

/* -----------------------------------------------
   Добавление актива в портфель (через localStorage)
----------------------------------------------- */
function addAssetToAnalysis(symbol) {
    const selected = JSON.parse(localStorage.getItem('selectedAssets') || '[]');
    if (!selected.includes(symbol)) {
        selected.push(symbol);
        localStorage.setItem('selectedAssets', JSON.stringify(selected));
        alert(`${symbol} добавлен в список для анализа`);
    }
}
