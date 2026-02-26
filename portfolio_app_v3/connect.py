import yfinance as yf
import pandas as pd
from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()
engine = create_engine(os.getenv("DB_URL"))

TICKERS_DEFAULT = ["AAPL", "AMGN", "HON", "MSFT", "NVDA"]

def process_data(tickers_to_download=None):
    # Если нам передали список — используем его, если нет — стандартный
    list_to_process = tickers_to_download if tickers_to_download is not None else TICKERS_DEFAULT
    
    all_data = []
    total = len(list_to_process)
    
    for index, symbol in enumerate(list_to_process, 1):
        print(f"[{index}/{total}] --- ЗАГРУЗКА: {symbol} ---")
        try:
            hist = yf.Ticker(symbol).history(period="5y")
            if hist.empty:
                print(f"(!) Данные для {symbol} не найдены")
                continue

            hist.reset_index(inplace=True)
            hist['Date'] = hist['Date'].dt.tz_localize(None)
            
            df = hist[['Date', 'Open', 'High', 'Low', 'Close']].copy()
            df['Ticker'] = symbol
            all_data.append(df)

        except Exception as e:
            print(f"(!) Ошибка {symbol}: {e}")

    if all_data:
        final_df = pd.concat(all_data)
        print(f"[OK] Данные обновлены в public.prices. Строк: {len(final_df)}")
        
        # Явно указываем схему 'public', чтобы избежать ошибки InvalidSchemaName
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS public"))
            conn.commit()

        print("--- СОХРАНЕНИЕ В БАЗУ ДАННЫХ ---")
        final_df.to_sql("prices", engine, schema='public', if_exists='replace', index=False)
        
        # Создаем индексы для ускорения работы
        with engine.connect() as conn:
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_ticker ON public.prices (\"Ticker\")"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_date ON public.prices (\"Date\")"))
            conn.commit()

        print(f"[OK] Данные обновлены в public.prices. Строк: {len(final_df)}")

if __name__ == "__main__":
    process_data()