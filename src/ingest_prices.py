import os
import time
import uuid
import argparse
import pandas as pd
import yfinance as yf
from sqlalchemy import create_engine, text

def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL env var is missing")
    return create_engine(db_url)

def fetch_symbols(engine, limit=None):
    q = "SELECT symbol FROM stock_universe ORDER BY symbol"
    if limit:
        q += " LIMIT :limit"
        return pd.read_sql(text(q), engine, params={"limit": limit})["symbol"].tolist()
    return pd.read_sql(text(q), engine)["symbol"].tolist()

def ensure_stock_prices_table(engine):
    ddl = """
    CREATE TABLE IF NOT EXISTS stock_prices (
        symbol TEXT NOT NULL,
        date   DATE NOT NULL,
        open_price  DOUBLE PRECISION,
        high_price  DOUBLE PRECISION,
        low_price   DOUBLE PRECISION,
        close_price DOUBLE PRECISION,
        volume      BIGINT,
        source      TEXT DEFAULT 'yfinance',
        ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (symbol, date)
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))

def download_1y_daily(yahoo_symbol: str) -> pd.DataFrame:
    t = yf.Ticker(yahoo_symbol)
    hist = t.history(period="1y", interval="1d", auto_adjust=False)
    if hist is None or hist.empty:
        return pd.DataFrame()

    hist = hist.reset_index()  # Date becomes a column
    # yfinance sometimes returns 'Date' or 'Datetime'
    date_col = "Date" if "Date" in hist.columns else ("Datetime" if "Datetime" in hist.columns else None)
    if not date_col:
        raise ValueError(f"Could not find date column in yfinance result for {yahoo_symbol}")

    out = pd.DataFrame({
        "date": pd.to_datetime(hist[date_col]).dt.date,
        "open_price": hist.get("Open"),
        "high_price": hist.get("High"),
        "low_price": hist.get("Low"),
        "close_price": hist.get("Close"),
        "volume": hist.get("Volume"),
    })
    out = out.dropna(subset=["date"])
    return out

def upsert_prices(engine, symbol: str, df_prices: pd.DataFrame):
    if df_prices.empty:
        return 0, None, None

    df_prices = df_prices.copy()
    df_prices["symbol"] = symbol
    df_prices["source"] = "yfinance"

    min_d = df_prices["date"].min()
    max_d = df_prices["date"].max()

    # Idempotent load: delete the same date-range for that symbol, then insert
    with engine.begin() as conn:
        conn.execute(
            text("DELETE FROM stock_prices WHERE symbol=:sym AND date BETWEEN :d1 AND :d2"),
            {"sym": symbol, "d1": min_d, "d2": max_d},
        )
        df_prices[[
            "symbol", "date", "open_price", "high_price", "low_price", "close_price", "volume", "source"
        ]].to_sql("stock_prices", conn, if_exists="append", index=False, method="multi")

    return len(df_prices), min_d, max_d

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5, help="How many symbols from stock_universe to ingest")
    ap.add_argument("--suffix", default=".NS", help="Yahoo suffix for NSE symbols (default .NS)")
    ap.add_argument("--sleep", type=float, default=0.25, help="Sleep between symbols to be polite")
    args = ap.parse_args()

    run_id = str(uuid.uuid4())
    engine = get_engine()

    # sanity check
    with engine.connect() as conn:
        print("DB OK:", conn.execute(text("select 1")).scalar())

    ensure_stock_prices_table(engine)

    symbols = fetch_symbols(engine, limit=args.limit)
    print(f"Symbols to ingest: {len(symbols)} | run_id={run_id}")

    total_rows = 0
    for sym in symbols:
        yahoo_sym = f"{sym}{args.suffix}"
        t0 = time.time()
        try:
            prices = download_1y_daily(yahoo_sym)
            rows, d1, d2 = upsert_prices(engine, sym, prices)
            total_rows += rows
            print(f"{sym} ({yahoo_sym}) -> {rows} rows [{d1}..{d2}] in {round(time.time()-t0, 2)}s")
        except Exception as e:
            print(f"{sym} ({yahoo_sym}) -> ERROR: {e}")

        if args.sleep:
            time.sleep(args.sleep)

    print("DONE. Total rows inserted:", total_rows)

if __name__ == "__main__":
    main()
