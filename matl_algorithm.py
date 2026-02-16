import numpy as np

def calculate_volatility_sigma(returns_list):
    """
    Математика: Стандартное отклонение доходностей, приведенное к году.
    Input: список или массив дневных доходностей.
    """
    daily_sigma = np.std(returns_list)
    return daily_sigma * np.sqrt(252)

def calculate_sharpe_ratio(returns_list, risk_free_rate=0.03):
    """
    Математика: (Средняя доходность - Безрисковая ставка) / Волатильность.
    Input: список доходностей, безрисковая ставка (0.03 = 3%).
    """
    volatility = calculate_volatility_sigma(returns_list)
    if volatility == 0: return 0
    annual_return = np.mean(returns_list) * 252
    return (annual_return - risk_free_rate) / volatility

def calculate_beta(stock_returns, market_returns):
    """
    Математика: Ковариация(акция, рынок) / Дисперсия(рынок).
    Input: доходности акции, доходности индекса (S&P500).
    """
    covariance = np.cov(stock_returns, market_returns)[0][1]
    market_variance = np.var(market_returns)
    return covariance / market_variance if market_variance != 0 else 0
def calculate_pe_ratio(current_price, eps):
    """
    Input: текущая цена, прибыль на акцию (EPS).
    """
    return current_price / eps if eps != 0 else None

def calculate_ps_ratio(market_cap, total_revenue):
    """
    Input: капитализация, общая выручка.
    """
    return market_cap / total_revenue if total_revenue != 0 else None

def calculate_peg_ratio(pe_ratio, earnings_growth_rate):
    """
    Математика: P/E деленный на темп роста прибыли (в целых числах, например 15 для 15%).
    Input: коэффициент P/E, ожидаемый рост прибыли.
    """
    return pe_ratio / earnings_growth_rate if earnings_growth_rate != 0 else None
def calculate_roe(net_income, total_equity):
    """
    Input: чистая прибыль, собственный капитал.
    """
    return net_income / total_equity if total_equity != 0 else None

def calculate_eps(net_income, shares_outstanding):
    """
    Input: чистая прибыль, количество акций в обращении.
    """
    return net_income / shares_outstanding if shares_outstanding != 0 else None

def calculate_growth_rate(current_value, previous_value):
    """
    Математика: (V_now - V_prev) / |V_prev|.
    Input: значение текущего периода, значение прошлого периода.
    """
    if previous_value is None or previous_value == 0:
        return None
    return (current_value - previous_value) / abs(previous_value)