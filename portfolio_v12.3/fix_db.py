#!/usr/bin/env python3
"""
fix_db.py — Запустите ОДИН РАЗ перед стартом uvicorn.

Что делает:
  1. Удаляет дубликаты из таблицы prices
  2. Добавляет PRIMARY KEY (Ticker, Date) если его нет
  3. Создаёт индексы
  4. Показывает сколько тикеров в DB

Запуск:
  python fix_db.py
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from config import get_settings
from app.database import init_engine, get_engine, dispose_engine
from sqlalchemy import text

def main():
    settings = get_settings()
    print(f"Подключаемся к DB: {settings.db_url[:40]}...")
    init_engine(settings.db_url)
    engine = get_engine()

    if engine is None:
        print("ОШИБКА: не удалось подключиться к DB")
        sys.exit(1)

    with engine.connect() as conn:
        # 1. Проверяем существует ли таблица
        r = conn.execute(text("""
            SELECT COUNT(*) FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'prices'
        """))
        exists = r.scalar() > 0

        if not exists:
            print("Таблица prices не существует — создаём...")
            conn.execute(text("""
                CREATE TABLE public.prices (
                    "Ticker" TEXT        NOT NULL,
                    "Date"   TIMESTAMP   NOT NULL,
                    "Open"   DOUBLE PRECISION,
                    "High"   DOUBLE PRECISION,
                    "Low"    DOUBLE PRECISION,
                    "Close"  DOUBLE PRECISION,
                    PRIMARY KEY ("Ticker", "Date")
                )
            """))
            conn.commit()
            print("Таблица создана с PRIMARY KEY.")
        else:
            print("Таблица prices существует.")

            # 2. Считаем строки и тикеры
            r = conn.execute(text('SELECT COUNT(*) FROM public.prices'))
            total_rows = r.scalar()
            r = conn.execute(text('SELECT COUNT(DISTINCT "Ticker") FROM public.prices'))
            total_tickers = r.scalar()
            print(f"Строк: {total_rows}, Тикеров: {total_tickers}")

            # 3. Проверяем PRIMARY KEY
            r = conn.execute(text("""
                SELECT COUNT(*) FROM information_schema.table_constraints
                WHERE table_schema = 'public'
                  AND table_name   = 'prices'
                  AND constraint_type = 'PRIMARY KEY'
            """))
            has_pk = r.scalar() > 0

            if has_pk:
                print("PRIMARY KEY уже есть — всё в порядке!")
            else:
                print("PRIMARY KEY отсутствует — исправляем...")

                # 4. Удаляем дубликаты
                r = conn.execute(text("""
                    SELECT COUNT(*) FROM (
                        SELECT "Ticker", "Date", COUNT(*) c
                        FROM public.prices
                        GROUP BY "Ticker", "Date"
                        HAVING COUNT(*) > 1
                    ) t
                """))
                dupes = r.scalar()
                if dupes > 0:
                    print(f"  Найдено дубликатов: {dupes} — удаляем...")
                    conn.execute(text("""
                        DELETE FROM public.prices a
                        USING  public.prices b
                        WHERE  a.ctid < b.ctid
                          AND  a."Ticker" = b."Ticker"
                          AND  a."Date"   = b."Date"
                    """))
                    conn.commit()
                    print("  Дубликаты удалены.")
                else:
                    print("  Дубликатов нет.")

                # 5. Добавляем PRIMARY KEY
                print("  Добавляем PRIMARY KEY...")
                conn.execute(text("""
                    ALTER TABLE public.prices
                    ADD CONSTRAINT prices_pkey PRIMARY KEY ("Ticker", "Date")
                """))
                conn.commit()
                print("  PRIMARY KEY добавлен успешно!")

        # 6. Индексы
        conn.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_prices_ticker ON public.prices ("Ticker")'
        ))
        conn.execute(text(
            'CREATE INDEX IF NOT EXISTS idx_prices_date ON public.prices ("Date")'
        ))
        conn.commit()
        print("Индексы проверены/созданы.")

        # 7. Итог
        r = conn.execute(text('SELECT COUNT(DISTINCT "Ticker") FROM public.prices'))
        final_count = r.scalar()
        print(f"\nГотово! Тикеров в DB: {final_count}")
        if final_count == 0:
            print("DB пустая — при первом запуске uvicorn скачает все данные через yfinance и сохранит в DB.")
            print("При следующем запуске данные будут браться из DB (yfinance = 0 вызовов).")
        elif final_count < 100:
            print(f"В DB {final_count} тикеров из 100 — при старте uvicorn докачает {100 - final_count} недостающих.")
        else:
            print("Все 100 тикеров в DB — при старте uvicorn yfinance вызываться НЕ будет!")

    dispose_engine()

if __name__ == "__main__":
    main()
