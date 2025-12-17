import os
import time
import uuid
import pandas as pd
import requests
from io import StringIO
from sqlalchemy import create_engine, text


NSE_URL = "https://archives.nseindia.com/content/indices/ind_nifty50list.csv"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.nseindia.com",
}


def fetch_nifty50_universe() -> pd.DataFrame:
    with requests.session() as s:
        s.headers.update(HEADERS)
        s.get("https://www.nseindia.com", timeout=5)  # warm-up
        r = s.get(NSE_URL, timeout=10)
        r.raise_for_status()

    df = pd.read_csv(StringIO(r.content.decode("utf-8")))
    return df


def write_stock_universe(engine, df: pd.DataFrame) -> int:
    required_cols = ["Company Name", "Industry", "Symbol", "Series", "ISIN Code"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"NSE CSV missing expected columns: {missing}")

    out = df.rename(columns={
        "Company Name": "company_name",
        "Industry": "industry",
        "Symbol": "symbol",
        "Series": "series",
        "ISIN Code": "isin",
    })[["symbol", "company_name", "industry", "series", "isin"]].copy()

    # Replace is fine for a daily refresh universe
    out.to_sql("stock_universe", engine, if_exists="replace", index=False)
    return len(out)


def main():
    run_id = str(uuid.uuid4())

    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL env var is missing")

    engine = create_engine(db_url)

    # DB connectivity check
    with engine.connect() as conn:
        val = conn.execute(text("select 1")).scalar()
        print("DB OK:", val)

    # Fetch universe
    t0 = time.time()
    df = fetch_nifty50_universe()
    print(f"Universe fetched: {len(df)} rows | {round(time.time() - t0, 2)}s")

    # Write to DB
    t1 = time.time()
    rows = write_stock_universe(engine, df)
    print(f"Wrote stock_universe: {rows} rows | {round(time.time() - t1, 2)}s")

    # Show sample
    print("\nSample:")
    print(df.head(3).to_string(index=False))
    print("\nRun ID:", run_id)

if __name__ == "__main__":
    main()
