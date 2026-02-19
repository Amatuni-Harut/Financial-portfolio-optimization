#!/usr/bin/env python
"""
Скрипт для загрузки исторических данных по акциям в базу данных
"""
import sys
import yfinance as yf
from datetime import datetime, timedelta
from pathlib import Path

# Добавляем путь к app
sys.path.append(str(Path(__file__).parent))

from app.database import SessionLocal
from app.models.stock import Stock, StockPrice


def load_stock_data(ticker: str, name: str, sector: str = None, years: int = 5):
    """
    Загружает данные по акции из Yahoo Finance
    
    Args:
        ticker: Тикер акции
        name: Название компании
        sector: Сектор экономики
        years: Количество лет истории для загрузки
    """
    db = SessionLocal()
    
    try:
        print(f"📥 Загрузка {ticker} ({name})...")
        
        # Проверяем, есть ли уже акция в БД
        existing_stock = db.query(Stock).filter(Stock.ticker == ticker).first()
        if existing_stock:
            print(f"  ℹ️  Акция {ticker} уже существует, обновляем данные...")
        else:
            # Добавляем новую акцию
            stock = Stock(ticker=ticker, name=name, sector=sector)
            db.add(stock)
            db.commit()
            print(f"  ✓ Акция {ticker} добавлена в базу")
        
        # Загружаем исторические данные
        end_date = datetime.now()
        start_date = end_date - timedelta(days=years*365)
        
        print(f"  📊 Загрузка данных с {start_date.date()} по {end_date.date()}...")
        data = yf.download(ticker, start=start_date, end=end_date, progress=False)
        
        if data.empty:
            print(f"  ⚠️  Нет данных для {ticker}")
            return False
        
        # Удаляем старые данные за этот период (для обновления)
        db.query(StockPrice).filter(
            StockPrice.ticker == ticker,
            StockPrice.date >= start_date.date(),
            StockPrice.date <= end_date.date()
        ).delete()
        
        # Добавляем новые данные
        count = 0
        for date, row in data.iterrows():
            try:
                price = StockPrice(
                    ticker=ticker,
                    date=date.date(),
                    open_price=float(row['Open']),
                    high_price=float(row['High']),
                    low_price=float(row['Low']),
                    close_price=float(row['Close']),
                    adj_close=float(row['Adj Close']) if 'Adj Close' in row else float(row['Close']),
                    volume=int(row['Volume']) if row['Volume'] > 0 else None
                )
                db.add(price)
                count += 1
            except Exception as e:
                print(f"  ⚠️  Ошибка в данных для {date}: {e}")
                continue
        
        db.commit()
        print(f"  ✅ Загружено {count} записей для {ticker}")
        return True
        
    except Exception as e:
        print(f"  ❌ Ошибка при загрузке {ticker}: {e}")
        db.rollback()
        return False
    finally:
        db.close()


def load_default_stocks():
    """Загружает набор популярных акций и ETF по умолчанию"""
    
    # Список акций для загрузки
    stocks_to_load = [
        # Технологические компании
        ('AAPL', 'Apple Inc.', 'Technology'),
        ('MSFT', 'Microsoft Corporation', 'Technology'),
        ('GOOGL', 'Alphabet Inc.', 'Technology'),
        ('AMZN', 'Amazon.com Inc.', 'Consumer Cyclical'),
        ('META', 'Meta Platforms Inc.', 'Technology'),
        ('NVDA', 'NVIDIA Corporation', 'Technology'),
        ('TSLA', 'Tesla Inc.', 'Automotive'),
        
        # Финансы
        ('JPM', 'JPMorgan Chase & Co.', 'Financial Services'),
        ('V', 'Visa Inc.', 'Financial Services'),
        ('MA', 'Mastercard Inc.', 'Financial Services'),
        ('BAC', 'Bank of America Corp.', 'Financial Services'),
        
        # Здравоохранение
        ('JNJ', 'Johnson & Johnson', 'Healthcare'),
        ('UNH', 'UnitedHealth Group Inc.', 'Healthcare'),
        ('PFE', 'Pfizer Inc.', 'Healthcare'),
        
        # Потребительский сектор
        ('WMT', 'Walmart Inc.', 'Consumer Defensive'),
        ('PG', 'Procter & Gamble Co.', 'Consumer Defensive'),
        ('KO', 'Coca-Cola Company', 'Consumer Defensive'),
        ('PEP', 'PepsiCo Inc.', 'Consumer Defensive'),
        
        # Энергетика
        ('XOM', 'Exxon Mobil Corporation', 'Energy'),
        ('CVX', 'Chevron Corporation', 'Energy'),
        
        # ETF - Широкий рынок
        ('SPY', 'SPDR S&P 500 ETF', 'ETF'),
        ('QQQ', 'Invesco QQQ Trust', 'ETF'),
        ('DIA', 'SPDR Dow Jones Industrial Average ETF', 'ETF'),
        ('IWM', 'iShares Russell 2000 ETF', 'ETF'),
        ('VTI', 'Vanguard Total Stock Market ETF', 'ETF'),
        
        # ETF - Международные
        ('EFA', 'iShares MSCI EAFE ETF', 'ETF'),
        ('EEM', 'iShares MSCI Emerging Markets ETF', 'ETF'),
        ('VEA', 'Vanguard FTSE Developed Markets ETF', 'ETF'),
        
        # ETF - Облигации
        ('AGG', 'iShares Core US Aggregate Bond ETF', 'ETF'),
        ('BND', 'Vanguard Total Bond Market ETF', 'ETF'),
        ('TLT', 'iShares 20+ Year Treasury Bond ETF', 'ETF'),
        
        # ETF - Секторальные
        ('XLF', 'Financial Select Sector SPDR Fund', 'ETF'),
        ('XLK', 'Technology Select Sector SPDR Fund', 'ETF'),
        ('XLE', 'Energy Select Sector SPDR Fund', 'ETF'),
        ('XLV', 'Health Care Select Sector SPDR Fund', 'ETF'),
        
        # Commodities
        ('GLD', 'SPDR Gold Shares', 'Commodity'),
        ('SLV', 'iShares Silver Trust', 'Commodity'),
    ]
    
    print("=" * 60)
    print("🚀 ЗАГРУЗКА ДАННЫХ В БАЗУ")
    print("=" * 60)
    print(f"Будет загружено {len(stocks_to_load)} активов\n")
    
    success_count = 0
    fail_count = 0
    
    for ticker, name, sector in stocks_to_load:
        if load_stock_data(ticker, name, sector):
            success_count += 1
        else:
            fail_count += 1
        print()  # Пустая строка между акциями
    
    print("=" * 60)
    print("📊 ИТОГИ ЗАГРУЗКИ")
    print("=" * 60)
    print(f"✅ Успешно загружено: {success_count}")
    print(f"❌ Ошибок: {fail_count}")
    print(f"📈 Всего обработано: {len(stocks_to_load)}")
    print("=" * 60)


def load_custom_stocks(tickers: list):
    """
    Загружает пользовательский список тикеров
    
    Args:
        tickers: Список тикеров для загрузки
    """
    print(f"🔄 Загрузка {len(tickers)} пользовательских тикеров...\n")
    
    for ticker in tickers:
        # Получаем информацию о тикере
        try:
            stock_info = yf.Ticker(ticker)
            info = stock_info.info
            name = info.get('longName', ticker)
            sector = info.get('sector', 'Unknown')
            load_stock_data(ticker, name, sector)
        except Exception as e:
            print(f"❌ Не удалось загрузить {ticker}: {e}")
        print()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Загрузка данных по акциям в БД')
    parser.add_argument(
        '--tickers',
        nargs='+',
        help='Список тикеров для загрузки (например: AAPL MSFT GOOGL)'
    )
    parser.add_argument(
        '--years',
        type=int,
        default=5,
        help='Количество лет истории для загрузки (по умолчанию: 5)'
    )
    
    args = parser.parse_args()
    
    if args.tickers:
        # Загружаем пользовательские тикеры
        load_custom_stocks(args.tickers)
    else:
        # Загружаем стандартный набор
        load_default_stocks()
    
    print("\n✨ Готово! Данные загружены в базу данных.")
    print("🚀 Теперь можно запустить приложение: uvicorn app.main:app --reload")
