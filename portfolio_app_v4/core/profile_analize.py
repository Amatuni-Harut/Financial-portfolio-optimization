# profile_analize.py — Анализ и оптимизация портфеля
import pandas as pd
import numpy as np
import math
from dataclasses import dataclass
from typing import List, Dict, Optional

# --- ЛОГИЧЕСКАЯ СВЯЗЬ ---
import connect
from data import load_all_tickers

# ------------------------

# ===============================================================
# 1. СТРУКТУРЫ ДАННЫХ
# ===============================================================


@dataclass
class PortfolioMetrics:
    budget: float  # общий бюджет ($)
    monthly_profit: float  # абсолютная прибыль в месяц ($)
    monthly_risk: float  # абсолютный риск в месяц ($)
    sharpe: float  # коэффициент Шарпа (месячный)
    payback_months: float  # окупаемость (месяцев)
    return_pct: float  # относительная доходность (%)

    def print(self, label: str = ""):
        tag = f"[{label}] " if label else ""
        print(f"  {tag}Бюджет:          {self.budget:>12.2f} $")
        print(f"  {tag}Прибыль/мес:     {self.monthly_profit:>12.2f} $")
        print(f"  {tag}Риск/мес:        {self.monthly_risk:>12.2f} $")
        print(f"  {tag}Шарп (месяч.):   {self.sharpe:>12.4f}")
        print(f"  {tag}Окупаемость:     {self.payback_months:>12.1f} мес")
        print(f"  {tag}Доходность:      {self.return_pct:>12.4f} %/мес")


# ===============================================================
# НАСТРОЙКИ
# ===============================================================

OUTPUT_FILE = "portfolio_analysis.csv"

# Тикеры
MAIN_TICKERS = ["AAPL", "MSFT", "GOOGL", "JPM", "XOM"]
RESERVE_TICKERS = ["NVDA", "AMZN", "TSLA", "META", "BRK-B"]
ALL_REQUIRED = list(set(MAIN_TICKERS + RESERVE_TICKERS))

RISK_FREE_ANNUAL = 0.02
RISK_FREE_MONTHLY = RISK_FREE_ANNUAL / 12

MC_ITERATIONS = 10_000
MC_SEED = 42

# ===============================================================
# ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ===============================================================


def sep(char="=", n=70):
    print(char * n)


def header(title: str):
    sep()
    print(f" {title} ".center(70, "="))
    sep()


def calculate_portfolio_performance(weights, mean_returns, cov_matrix):
    port_return = np.sum(mean_returns * weights)
    port_std = np.sqrt(np.dot(weights.T, np.dot(cov_matrix, weights)))
    sharpe = (port_return - RISK_FREE_MONTHLY) / port_std if port_std != 0 else 0
    return port_return, port_std, sharpe


def fill_budget_to_limit(shares_dict, latest_prices, budget_limit):
    current_cost = sum(shares_dict[t] * latest_prices[t] for t in shares_dict)
    remaining = budget_limit - current_cost
    sorted_tickers = sorted(latest_prices.keys(), key=lambda t: latest_prices[t])
    for t in sorted_tickers:
        p = latest_prices[t]
        if p <= remaining:
            can_buy = int(remaining // p)
            shares_dict[t] += can_buy
            remaining -= can_buy * p
    return shares_dict


# ===============================================================
# БЛОК 1 — ЗАГРУЗКА ДАННЫХ
# ===============================================================


def load_data(tickers: List[str]):
    header("БЛОК 1: ПОЛУЧЕНИЕ ДАННЫХ")

    # 1. Обновляем БД через connect
    connect.process_data(tickers)

    # 2. Загружаем из БД через data
    raw_dict = load_all_tickers(tickers)

    all_frames = []
    for t_symbol, data in raw_dict.items():
        temp_df = pd.DataFrame(
            {
                "date": pd.to_datetime(data["date"]),
                "close": data["close"],
                "ticker": t_symbol,
            }
        )
        all_frames.append(temp_df)

    df = pd.concat(all_frames)
    df["year_month"] = df["date"].dt.to_period("M")

    # Сводная таблица цен
    monthly_close = (
        df.sort_values("date")
        .groupby(["ticker", "year_month"])["close"]
        .last()
        .unstack(level=0)
    )

    # Доходности
    returns_wide = monthly_close.pct_change().dropna()
    active_tickers = returns_wide.columns.tolist()

    latest_prices = {t: monthly_close[t].iloc[-1] for t in active_tickers}

    print(f"\n[*] Доступно тикеров: {len(active_tickers)}")
    return returns_wide, latest_prices, active_tickers


# ===============================================================
# МЕТОДЫ ОПТИМИЗАЦИИ
# ===============================================================


def monte_carlo_optimization(
    tickers, returns, latest_prices, budget
) -> PortfolioMetrics:
    mean_ret = returns[tickers].mean()
    cov_mat = returns[tickers].cov()

    np.random.seed(MC_SEED)
    best_sharpe = -1
    best_weights = None

    for _ in range(MC_ITERATIONS):
        w = np.random.dirichlet(np.ones(len(tickers)))
        _, _, sh = calculate_portfolio_performance(w, mean_ret, cov_mat)
        if sh > best_sharpe:
            best_sharpe = sh
            best_weights = w

    shares = {
        t: int((best_weights[i] * budget) // latest_prices[t])
        for i, t in enumerate(tickers)
    }
    shares = fill_budget_to_limit(shares, latest_prices, budget)

    total_val = sum(shares[t] * latest_prices[t] for t in tickers)
    w_act = np.array([(shares[t] * latest_prices[t]) / total_val for t in tickers])
    p_ret, p_std, p_sh = calculate_portfolio_performance(w_act, mean_ret, cov_mat)

    return PortfolioMetrics(
        budget=total_val,
        monthly_profit=p_ret * total_val,
        monthly_risk=p_std * total_val,
        sharpe=p_sh,
        payback_months=1 / p_ret if p_ret > 0 else 999,
        return_pct=p_ret * 100,
    )


def greedy_optimization(tickers, returns, latest_prices, budget) -> PortfolioMetrics:
    mean_ret = returns[tickers].mean()
    cov_mat = returns[tickers].cov()

    shares = {t: 0 for t in tickers}
    current_cost = 0

    while True:
        best_t = None
        best_sh = -1
        for t in tickers:
            if current_cost + latest_prices[t] <= budget:
                temp_shares = shares.copy()
                temp_shares[t] += 1
                v = sum(temp_shares[i] * latest_prices[i] for i in tickers)
                w = np.array([(temp_shares[i] * latest_prices[i]) / v for i in tickers])
                _, _, sh = calculate_portfolio_performance(w, mean_ret, cov_mat)
                if sh > best_sh:
                    best_sh = sh
                    best_t = t
        if best_t:
            shares[best_t] += 1
            current_cost += latest_prices[best_t]
        else:
            break

    total_val = sum(shares[t] * latest_prices[t] for t in tickers)
    w_act = np.array([(shares[t] * latest_prices[t]) / total_val for t in tickers])
    p_ret, p_std, p_sh = calculate_portfolio_performance(w_act, mean_ret, cov_mat)
    return PortfolioMetrics(
        total_val,
        p_ret * total_val,
        p_std * total_val,
        p_sh,
        1 / p_ret if p_ret > 0 else 999,
        p_ret * 100,
    )


# ===============================================================
# БЛОК 2 — МЕТРИКИ КАЖДОЙ АКЦИИ
# ===============================================================


def analyze_stocks(returns_wide: pd.DataFrame, latest_prices: Dict[str, float]):
    header("БЛОК 2: АНАЛИЗ КАЖДОЙ АКЦИИ")

    tickers = list(returns_wide.columns)
    stats = []

    print(
        f"  {'Тикер':<6} {'Ср.Цена($)':>10} {'Дох/мес($)':>11} "
        f"{'Риск/мес($)':>12} {'Дох%/мес':>10} {'Риск%/мес':>10} {'Шарп(мес)':>10}"
    )
    sep("-")

    for t in tickers:
        rets = returns_wide[t].dropna()
        price = latest_prices[t]

        # ПУНКТ 3: Средняя доходность и риск — АБСОЛЮТНО ($)
        mean_ret_pct = rets.mean()  # средняя месячная доходность (доля)
        std_ret_pct = rets.std()  # риск (std) в долях

        abs_profit = mean_ret_pct * price  # прибыль в $ на 1 акцию за месяц
        abs_risk = std_ret_pct * price  # риск в $ на 1 акцию за месяц

        # ПУНКТ 4: Коэффициент Шарпа — МЕСЯЧНЫЙ
        if std_ret_pct > 0:
            monthly_sharpe = (mean_ret_pct - RISK_FREE_MONTHLY) / std_ret_pct
        else:
            monthly_sharpe = 0.0

        stats.append(
            {
                "ticker": t,
                "price": price,
                "mean_ret_pct": mean_ret_pct,
                "std_ret_pct": std_ret_pct,
                "abs_profit": abs_profit,
                "abs_risk": abs_risk,
                "sharpe": monthly_sharpe,
            }
        )

        marker = "  ← ОТРИЦАТЕЛЬНАЯ" if mean_ret_pct < 0 else ""
        print(
            f"  {t:<6} {price:>10.2f} {abs_profit:>+11.4f} "
            f"{abs_risk:>12.4f} {mean_ret_pct*100:>+9.4f}% "
            f"{std_ret_pct*100:>9.4f}% {monthly_sharpe:>10.4f}{marker}"
        )

    sep("-")

    # Матрица ковариации
    cov_matrix = returns_wide[tickers].cov().values
    print(f"\n  Матрица ковариации ({len(tickers)}×{len(tickers)}):")
    cov_df = pd.DataFrame(np.round(cov_matrix, 6), index=tickers, columns=tickers)
    print(cov_df.to_string())

    # Матрица корреляций
    corr_matrix = returns_wide[tickers].corr()
    print(f"\n  Матрица корреляций:")
    print(corr_matrix.round(4).to_string())

    sep("-")
    return stats, cov_matrix


# ===============================================================
# БЛОК 3 — ФУНКЦИЯ РАСЧЁТА МЕТРИК ПОРТФЕЛЯ
# ===============================================================


def calc_portfolio_metrics(
    shares_vector: np.ndarray,
    tickers: List[str],
    latest_prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
) -> PortfolioMetrics:
    """
    Рассчитывает метрики портфеля по вектору количества акций.
    Все денежные метрики — АБСОЛЮТНЫЕ ($) за МЕСЯЦ.
    """
    prices = np.array([latest_prices[t] for t in tickers])

    # Бюджет
    budget = float(np.sum(shares_vector * prices))
    if budget <= 0:
        return PortfolioMetrics(0, 0, 0, 0, float("inf"), 0)

    # Веса
    weights = (shares_vector * prices) / budget

    # Относительные метрики
    ret_rel = float(np.dot(weights, mean_returns))  # ожидаемая доходность (доля)
    var_rel = float(weights @ cov_matrix @ weights)  # дисперсия
    risk_rel = math.sqrt(max(var_rel, 0))  # риск (std) в долях

    # АБСОЛЮТНЫЕ метрики ($) за МЕСЯЦ
    abs_profit = ret_rel * budget
    abs_risk = risk_rel * budget

    # Месячный Sharpe
    if risk_rel > 0:
        sharpe = (ret_rel - RISK_FREE_MONTHLY) / risk_rel
    else:
        sharpe = 0.0

    # Окупаемость
    if abs_profit > 0:
        payback = budget / abs_profit
    else:
        payback = float("inf")

    return PortfolioMetrics(
        budget=round(budget, 4),
        monthly_profit=round(abs_profit, 4),
        monthly_risk=round(abs_risk, 4),
        sharpe=round(sharpe, 6),
        payback_months=round(payback, 2),
        return_pct=round(ret_rel * 100, 6),
    )


def fill_budget_to_limit(
    shares: np.ndarray,
    tickers: List[str],
    latest_prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    target_budget: float,
) -> np.ndarray:
    """
    После основной оптимизации добирает акции в пределах target_budget.
    Стратегия: на каждом шаге покупает акцию с наибольшим приростом Sharpe.
    Гарантирует что итоговый бюджет портфеля <= target_budget.
    """
    prices = np.array([latest_prices[t] for t in tickers])
    shares = shares.copy()
    spent = float(np.sum(shares * prices))
    remaining = target_budget - spent
    fill_steps = 0

    print(
        f"\n  [Добор до бюджета] Потрачено: {spent:.2f}$ | "
        f"Остаток: {remaining:.2f}$ | Бюджет: {target_budget:.2f}$"
    )

    while remaining > min(prices):
        current_sharpe = calc_portfolio_metrics(
            shares, tickers, latest_prices, mean_returns, cov_matrix
        ).sharpe

        best_delta = -float("inf")
        best_idx = -1
        best_new_sharpe = current_sharpe

        for i in range(len(tickers)):
            if prices[i] > remaining:
                continue
            test = shares.copy()
            test[i] += 1
            m = calc_portfolio_metrics(
                test, tickers, latest_prices, mean_returns, cov_matrix
            )
            delta = m.sharpe - current_sharpe
            if delta > best_delta:
                best_delta = delta
                best_idx = i
                best_new_sharpe = m.sharpe

        if best_idx == -1:
            break

        shares[best_idx] += 1
        spent += prices[best_idx]
        remaining = target_budget - spent
        fill_steps += 1

        print(
            f"  [Добор #{fill_steps:>3}] +1 {tickers[best_idx]:<6} | "
            f"ΔSharpe: {best_delta:>+8.4f} | "
            f"Шарп: {best_new_sharpe:.4f} | "
            f"Потрачено: {spent:>10.2f}$ | "
            f"Остаток: {remaining:>8.2f}$"
        )

    if fill_steps == 0:
        print(
            f"  [Добор] Ничего не куплено — остаток {remaining:.2f}$ "
            f"меньше стоимости любой акции."
        )
    else:
        print(
            f"  [Добор] Куплено {fill_steps} акций. "
            f"Итоговый бюджет: {spent:.2f}$ "
            f"(неиспользованный остаток: {remaining:.2f}$)"
        )

    return shares


def print_portfolio_composition(
    shares_vector: np.ndarray,
    tickers: List[str],
    latest_prices: Dict[str, float],
    label: str = "Состав портфеля",
):
    print(f"\n  {label}:")
    prices = np.array([latest_prices[t] for t in tickers])
    budget = float(np.sum(shares_vector * prices))
    print(
        f"  {'Тикер':<6} {'Кол-во':>7} {'Цена($)':>9} {'Стоимость($)':>13} {'Доля%':>8}"
    )
    sep("-", 55)
    for t, s, p in zip(tickers, shares_vector, prices):
        cost = s * p
        share_pct = cost / budget * 100 if budget > 0 else 0
        print(f"  {t:<6} {int(s):>7} {p:>9.2f} {cost:>13.2f} {share_pct:>7.1f}%")
    sep("-", 55)
    print(f"  {'ИТОГО':<6} {'':>7} {'':>9} {budget:>13.2f} {'100.0%':>8}")


# ===============================================================
# БЛОК 4 — ПСЕВДО-ПОРТФЕЛЬ
# ===============================================================


def generate_pseudo_portfolio(
    tickers: List[str],
    latest_prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
) -> tuple:
    header("БЛОК 4: ПСЕВДО-ПОРТФЕЛЬ (исходный портфель для оптимизации)")

    np.random.seed(MC_SEED)
    shares = np.random.randint(5, 20, size=len(tickers)).astype(float)

    print(f"  Random seed: {MC_SEED}")
    print(f"  Псевдо-портфель имитирует ИСХОДНЫЙ портфель инвестора.")
    print(f"  Его бюджет становится ЖЁСТКИМ ОГРАНИЧЕНИЕМ для всех оптимизаций.")
    print(f"  Все 3 оптимизированных портфеля должны уложиться в этот бюджет.")
    print()
    print_portfolio_composition(shares, tickers, latest_prices, "Случайный состав")

    metrics = calc_portfolio_metrics(
        shares, tickers, latest_prices, mean_returns, cov_matrix
    )
    print()
    metrics.print("Псевдо")

    target_budget = metrics.budget
    print(
        f"\n  >>> Бюджет псевдо-портфеля = {target_budget:.2f}$ — используется как ограничение"
    )
    sep("-")
    return shares, metrics, target_budget


# ===============================================================
# БЛОК 5 — МОНТЕ-КАРЛО (максимизация Sharpe)
# ===============================================================


def monte_carlo_optimization(
    tickers: List[str],
    latest_prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    target_budget: float,
    n_iter: int = MC_ITERATIONS,
    seed: int = MC_SEED,
) -> tuple:
    header("БЛОК 5: МОНТЕ-КАРЛО (максимизация Sharpe)")

    print(f"  Итераций:      {n_iter:,}")
    print(f"  Бюджет макс:   {target_budget:.2f} $")
    print(f"  Random seed:   {seed}")
    sep("-")

    prices = np.array([latest_prices[t] for t in tickers])
    n = len(tickers)
    np.random.seed(seed)

    best_sharpe = -float("inf")
    best_shares = np.zeros(n)
    valid_count = 0

    progress_steps = [n_iter // 10 * i for i in range(1, 11)]

    for step in range(1, n_iter + 1):

        # Генерация: случайные веса → конвертация в количество акций
        weights = np.random.dirichlet(np.ones(n))  # равномерно на симплексе
        budget_alloc = weights * target_budget
        shares = np.floor(budget_alloc / prices).astype(float)
        shares = np.maximum(shares, 0)

        # Проверка бюджета
        if np.sum(shares * prices) > target_budget:
            continue

        # Хотя бы 1 акция у каждого тикера не обязательна — 0 допустимо
        metrics = calc_portfolio_metrics(
            shares, tickers, latest_prices, mean_returns, cov_matrix
        )

        if metrics.budget > 0:
            valid_count += 1
            if metrics.sharpe > best_sharpe:
                best_sharpe = metrics.sharpe
                best_shares = shares.copy()

        # Прогресс каждые 10%
        if step in progress_steps:
            pct = step / n_iter * 100
            print(
                f"  [{pct:>5.1f}%] Итераций: {step:>6,} | "
                f"Валидных: {valid_count:>6,} | "
                f"Лучший Шарп: {best_sharpe:>8.4f}"
            )

    sep("-")
    print(f"  Всего валидных портфелей: {valid_count:,} из {n_iter:,}")

    # --- Добираем до бюджета псевдо-портфеля ---
    best_shares = fill_budget_to_limit(
        best_shares, tickers, latest_prices, mean_returns, cov_matrix, target_budget
    )

    best_metrics = calc_portfolio_metrics(
        best_shares, tickers, latest_prices, mean_returns, cov_matrix
    )
    print_portfolio_composition(
        best_shares, tickers, latest_prices, "Лучший портфель МК (после добора)"
    )
    print()
    best_metrics.print("МонтеКарло")
    sep("-")
    return best_shares, best_metrics


# ===============================================================
# БЛОК 6 — ЖАДНЫЙ АЛГОРИТМ
# ===============================================================


def greedy_optimization(
    tickers: List[str],
    latest_prices: Dict[str, float],
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    target_budget: float,
) -> tuple:
    header("БЛОК 6: ЖАДНЫЙ АЛГОРИТМ (пошаговый подбор)")

    print(f"  Стратегия: на каждом шаге добавляем акцию")
    print(f"  с максимальным приростом Sharpe")
    print(f"  Бюджет: {target_budget:.2f} $")
    sep("-")

    prices = np.array([latest_prices[t] for t in tickers])
    n = len(tickers)
    shares = np.zeros(n)
    spent = 0.0
    step = 1

    print(
        f"  {'Шаг':>4} | {'Тикер':<6} | {'ΔSharpe':>9} | "
        f"{'Шарп':>8} | {'Потрачено':>11} | {'Остаток':>10}"
    )
    sep("-")

    while True:
        best_delta_sharpe = -float("inf")
        best_idx = -1
        best_new_sharpe = -float("inf")

        current_metrics = calc_portfolio_metrics(
            shares, tickers, latest_prices, mean_returns, cov_matrix
        )
        current_sharpe = current_metrics.sharpe

        for i in range(n):
            # Проверяем что хватает бюджета на ещё 1 акцию
            if spent + prices[i] > target_budget:
                continue

            test_shares = shares.copy()
            test_shares[i] += 1
            m = calc_portfolio_metrics(
                test_shares, tickers, latest_prices, mean_returns, cov_matrix
            )

            delta = m.sharpe - current_sharpe
            if delta > best_delta_sharpe:
                best_delta_sharpe = delta
                best_idx = i
                best_new_sharpe = m.sharpe

        if best_idx == -1:
            remaining = target_budget - spent
            print(f"\n  СТОП: Остаток {remaining:.2f}$ меньше стоимости любой акции.")
            break
        shares[best_idx] += 1
        spent += prices[best_idx]

        print(
            f"  {step:>4} | {tickers[best_idx]:<6} | "
            f"{best_delta_sharpe:>+9.4f} | "
            f"{best_new_sharpe:>8.4f} | "
            f"{spent:>10.2f}$ | "
            f"{target_budget - spent:>9.2f}$"
        )
        step += 1

    sep("-")
    # Жадный сам расходует бюджет до упора, но на случай мелкого остатка — добираем дешёвые акции
    shares = fill_budget_to_limit(
        shares, tickers, latest_prices, mean_returns, cov_matrix, target_budget
    )
    greedy_metrics = calc_portfolio_metrics(
        shares, tickers, latest_prices, mean_returns, cov_matrix
    )
    print_portfolio_composition(
        shares, tickers, latest_prices, "Итоговый жадный портфель (после добора)"
    )
    print()
    greedy_metrics.print("Жадный")
    sep("-")
    return shares, greedy_metrics


# ===============================================================
# БЛОК 7 — ЗАМЕНА ОТРИЦАТЕЛЬНЫХ + МОНТЕ-КАРЛО
# ===============================================================


def optimized_with_replacement(
    main_tickers: List[str],
    reserve_tickers: List[str],
    all_returns_wide: pd.DataFrame,
    all_latest_prices: Dict[str, float],
    pseudo_shares: np.ndarray,
    mean_returns_main: np.ndarray,
    cov_matrix_main: np.ndarray,
    target_budget: float,
) -> tuple:
    header("БЛОК 7: ЗАМЕНА ОТРИЦАТЕЛЬНЫХ АКЦИЙ + МОНТЕ-КАРЛО")

    # --- Шаг 7.1: Найти отрицательные тикеры ---
    mean_rets = {
        t: all_returns_wide[t].mean()
        for t in main_tickers
        if t in all_returns_wide.columns
    }

    print("  Средняя месячная доходность основных тикеров:")
    negative_tickers = []
    positive_tickers = []
    for t, r in mean_rets.items():
        marker = " ← ОТРИЦАТЕЛЬНАЯ" if r < 0 else ""
        print(f"    {t}: {r*100:>+8.4f}%{marker}")
        if r < 0:
            negative_tickers.append(t)
        else:
            positive_tickers.append(t)

    print(f"\n  Тикеры с отрицательной доходностью: {negative_tickers}")

    if not negative_tickers:
        print("  Нет отрицательных тикеров — замена не нужна.")
        print("  Используем тот же состав что и в блоке 5.")
        return monte_carlo_optimization(
            main_tickers,
            all_latest_prices,
            mean_returns_main,
            cov_matrix_main,
            target_budget,
        )

    # --- Шаг 7.2: Найти лучшие замены из резервной базы ---
    reserve_rets = {}
    for t in reserve_tickers:
        if t in all_returns_wide.columns:
            r = all_returns_wide[t].mean()
            reserve_rets[t] = r
            print(f"    Резерв {t}: {r*100:>+8.4f}%")
        else:
            print(f"    Резерв {t}: нет данных")

    # Сортируем резерв по убыванию доходности
    reserve_sorted = sorted(reserve_rets.items(), key=lambda x: x[1], reverse=True)
    reserve_positive = [(t, r) for t, r in reserve_sorted if r > 0]

    print(f"\n  Резерв (положительные, по убыванию доходности):")
    for t, r in reserve_positive:
        print(f"    {t}: {r*100:>+8.4f}%")

    # --- Шаг 7.3: Формируем новый состав ---
    new_tickers = list(main_tickers)  # копия

    replacements_done = []
    reserve_iter = iter(reserve_positive)

    for neg_t in negative_tickers:
        replacement = next(reserve_iter, None)
        if replacement is None:
            print(f"  ПРЕДУПРЕЖДЕНИЕ: Нет замены для {neg_t}, оставляем как есть.")
            continue

        repl_t, repl_r = replacement
        idx = new_tickers.index(neg_t)
        new_tickers[idx] = repl_t
        replacements_done.append((neg_t, repl_t))
        print(
            f"\n  ЗАМЕНА: {neg_t} → {repl_t} "
            f"(доходность: {mean_rets[neg_t]*100:+.4f}% → {repl_r*100:+.4f}%)"
        )

    sep("-")
    print(f"  Новый состав тикеров: {new_tickers}")

    # --- Пересчитываем матрицы для нового состава ---
    new_returns = all_returns_wide[
        [t for t in new_tickers if t in all_returns_wide.columns]
    ].dropna()
    available = [t for t in new_tickers if t in new_returns.columns]

    if len(available) < len(new_tickers):
        missing = [t for t in new_tickers if t not in available]
        print(f"  ПРЕДУПРЕЖДЕНИЕ: Нет данных для: {missing}")
        new_tickers = available
        new_returns = new_returns[new_tickers]

    new_mean_returns = new_returns.mean().values
    new_cov_matrix = new_returns.cov().values
    new_prices = {
        t: all_latest_prices[t] for t in new_tickers if t in all_latest_prices
    }

    print(f"\n  Перечитаны матрицы для состава: {new_tickers}")
    print(f"  Средние доходности нового состава:")
    for t, r in zip(new_tickers, new_mean_returns):
        print(f"    {t}: {r*100:>+8.4f}%")

    sep("-")

    # --- Шаг 7.4: Монте-Карло на новом составе ---
    print("  Запускаем Монте-Карло на обновлённом составе...")
    sep("-")

    best_shares, best_metrics = monte_carlo_optimization(
        new_tickers,
        new_prices,
        new_mean_returns,
        new_cov_matrix,
        target_budget,
        n_iter=MC_ITERATIONS,
        seed=MC_SEED + 1,
    )

    print(f"\n  Замены выполнены:")
    for old, new in replacements_done:
        print(f"    {old} → {new}")

    sep("-")
    return best_shares, best_metrics, new_tickers


# ===============================================================
# БЛОК 8 — ИТОГОВОЕ СРАВНЕНИЕ
# ===============================================================


def final_comparison(
    portfolios: Dict[str, dict],
    target_budget: float,
):
    header("БЛОК 8: ИТОГОВОЕ СРАВНЕНИЕ ВСЕХ ПОРТФЕЛЕЙ")

    print(f"  Бюджет псевдо-портфеля (ограничение): {target_budget:.2f} $")
    sep("-")

    # Проверка: все ли портфели уложились в бюджет
    print(f"  Проверка бюджетного ограничения:")
    all_ok = True
    for name, pdata in portfolios.items():
        b = pdata["metrics"].budget
        ok = b <= target_budget + 0.01  # допуск 1 цент на округление
        status = "✓ OK" if ok else "✗ ПРЕВЫШЕНИЕ!"
        utilization = b / target_budget * 100
        print(
            f"    {name:<15} {b:>10.2f}$ / {target_budget:.2f}$  "
            f"({utilization:.1f}% использовано)  {status}"
        )
        if not ok:
            all_ok = False
    if all_ok:
        print(f"  Все портфели уложились в бюджет ✓")
    sep("-")

    # Заголовок таблицы
    names = list(portfolios.keys())
    col_w = 18

    print(f"\n  {'Метрика':<25}", end="")
    for name in names:
        print(f"{name:>{col_w}}", end="")
    print()
    sep("-")

    metrics_labels = [
        ("Бюджет ($)", "budget", ".2f"),
        ("Прибыль/мес ($)", "monthly_profit", ".2f"),
        ("Риск/мес ($)", "monthly_risk", ".2f"),
        ("Шарп (месяч.)", "sharpe", ".4f"),
        ("Окупаемость (мес)", "payback_months", ".1f"),
        ("Доходность (%/мес)", "return_pct", ".4f"),
    ]

    winners = {}
    for label, attr, fmt in metrics_labels:
        print(f"  {label:<25}", end="")
        values = {}
        for name, pdata in portfolios.items():
            val = getattr(pdata["metrics"], attr)
            values[name] = val
            fmt_str = f"{{:>{col_w}{fmt}}}"
            print(fmt_str.format(val), end="")
        print()

        # Определяем победителя (выше = лучше, кроме риска и окупаемости)
        if attr in ("monthly_risk", "payback_months"):
            winner = min(
                values, key=lambda k: values[k] if values[k] != float("inf") else 1e18
            )
        else:
            winner = max(values, key=lambda k: values[k])
        winners[label] = winner

    # Строка использования бюджета
    print(f"  {'Использование бюджета':<25}", end="")
    for name, pdata in portfolios.items():
        utilization = pdata["metrics"].budget / target_budget * 100
        print(f"{utilization:>{col_w - 1}.1f}%", end="")
    print()

    sep("-")

    print(f"\n  Победители по метрикам:")
    for metric, winner in winners.items():
        print(f"    {metric:<25} → {winner}")

    sep("-")

    # Состав всех портфелей
    print(f"\n  Количество акций (состав портфелей):")
    all_tickers = sorted(
        set(t for pdata in portfolios.values() for t in pdata.get("tickers", []))
    )

    print(f"  {'Тикер':<6}", end="")
    for name in names:
        print(f"{name:>{col_w}}", end="")
    print()
    sep("-", 55)

    for t in all_tickers:
        print(f"  {t:<6}", end="")
        for name, pdata in portfolios.items():
            tickers = pdata.get("tickers", [])
            shares = pdata.get("shares", np.zeros(len(tickers)))
            if t in tickers:
                idx = tickers.index(t)
                val = int(shares[idx])
            else:
                val = 0
            print(f"{val:>{col_w}}", end="")
        print()

    sep()

    # Рекомендация
    sharpe_vals = {name: pdata["metrics"].sharpe for name, pdata in portfolios.items()}
    best_by_sharpe = max(sharpe_vals, key=lambda k: sharpe_vals[k])
    print(f"\n  РЕКОМЕНДАЦИЯ: Лучший портфель по Sharpe — [{best_by_sharpe}]")
    print(f"  Sharpe = {sharpe_vals[best_by_sharpe]:.4f}")
    sep()


# ===============================================================
# СОХРАНЕНИЕ В CSV
# ===============================================================


def save_results(portfolios: Dict[str, dict], output_file: str):
    rows = []
    for name, pdata in portfolios.items():
        m = pdata["metrics"]
        rows.append(
            {
                "Портфель": name,
                "Бюджет($)": m.budget,
                "Прибыль/мес($)": m.monthly_profit,
                "Риск/мес($)": m.monthly_risk,
                "Шарп": m.sharpe,
                "Окупаемость(мес)": m.payback_months,
                "Доходность%/мес": m.return_pct,
            }
        )
    pd.DataFrame(rows).to_csv(output_file, index=False)
    print(f"\n  [СОХРАНЕНО] Результаты записаны в: {output_file}")


# ===============================================================
# MAIN
# ===============================================================
# ===============================================================
# ОСНОВНОЙ ЗАПУСК (ИСПРАВЛЕННЫЙ)
# ===============================================================


def main(all_returns_wide, all_latest_prices, active_list):
    print("\n")
    header("АНАЛИЗ И ОПТИМИЗАЦИЯ ПОРТФЕЛЯ")

    # Убрали INPUT_FILE, так как данные из БД
    print(f"  Источник данных:     База данных PostgreSQL")
    print(f"  Доступные тикеры:    {active_list}")

    # Фильтруем основные тикеры, оставляя только те, что реально загрузились
    current_main = [t for t in MAIN_TICKERS if t in active_list]
    current_reserve = [t for t in RESERVE_TICKERS if t in active_list]

    print(f"  Основные тикеры:     {current_main}")
    print(f"  Резервные тикеры:    {current_reserve}")
    print(
        f"  Безриск. ставка:     {RISK_FREE_ANNUAL*100:.1f}%/год "
        f"= {RISK_FREE_MONTHLY*100:.4f}%/мес"
    )
    print(f"  Итераций МК:         {MC_ITERATIONS:,}")
    sep()

    # --- БЛОК 1: Подготовка матриц ---
    # Используем уже переданные данные вместо повторного вызова load_data
    main_returns = all_returns_wide[current_main].dropna()
    mean_returns_main = main_returns.mean().values
    cov_matrix_main = main_returns.cov().values
    prices_main = {t: all_latest_prices[t] for t in current_main}

    # --- БЛОК 2: Анализ каждой акции ---
    stock_stats, _ = analyze_stocks(main_returns, prices_main)

    # --- БЛОК 3: Демонстрация ---
    header("БЛОК 3: ФУНКЦИЯ МЕТРИК — ДЕМОНСТРАЦИЯ")
    demo_shares = np.ones(len(current_main)) * 10
    demo_m = calc_portfolio_metrics(
        demo_shares, current_main, prices_main, mean_returns_main, cov_matrix_main
    )
    print(f"  Пример: равновесный портфель по 10 акций каждой:")
    print_portfolio_composition(demo_shares, current_main, prices_main)
    print()
    demo_m.print("Демо")
    sep("-")

    # --- БЛОК 4: Псевдо-портфель ---
    pseudo_shares, pseudo_metrics, target_budget = generate_pseudo_portfolio(
        current_main, prices_main, mean_returns_main, cov_matrix_main
    )

    # --- БЛОК 5: Монте-Карло ---
    mc_shares, mc_metrics = monte_carlo_optimization(
        current_main, prices_main, mean_returns_main, cov_matrix_main, target_budget
    )

    # --- БЛОК 6: Жадный алгоритм ---
    greedy_shares, greedy_metrics = greedy_optimization(
        current_main, prices_main, mean_returns_main, cov_matrix_main, target_budget
    )

    # --- БЛОК 7: Замена отрицательных + Монте-Карло ---
    result7 = optimized_with_replacement(
        current_main,
        current_reserve,
        all_returns_wide,
        all_latest_prices,
        pseudo_shares,
        mean_returns_main,
        cov_matrix_main,
        target_budget,
    )

    if len(result7) == 3:
        replaced_shares, replaced_metrics, replaced_tickers = result7
    else:
        replaced_shares, replaced_metrics = result7
        replaced_tickers = current_main

    # --- БЛОК 8: Итоговое сравнение ---
    portfolios = {
        "1.Псевдо": {
            "metrics": pseudo_metrics,
            "shares": pseudo_shares,
            "tickers": current_main,
        },
        "2.МонтеКарло": {
            "metrics": mc_metrics,
            "shares": mc_shares,
            "tickers": current_main,
        },
        "3.Жадный": {
            "metrics": greedy_metrics,
            "shares": greedy_shares,
            "tickers": current_main,
        },
        "4.МК+Замена": {
            "metrics": replaced_metrics,
            "shares": replaced_shares,
            "tickers": replaced_tickers,
        },
    }

    final_comparison(portfolios, target_budget)
    save_results(portfolios, OUTPUT_FILE)

    print("\n  Готово. Все расчёты завершены.")
    sep()


if __name__ == "__main__":
    # 1. Загружаем данные один раз
    returns_all, prices_all, active_list = load_data(ALL_REQUIRED)

    # 2. Запускаем main и передаем в него эти данные
    main(returns_all, prices_all, active_list)
