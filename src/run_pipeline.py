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
    "Referer": "https://www.nseindia.com"
}

def fetch_nifty50():
    with requests.session() as s:
        s.headers.update(HEADERS)
        s.get("https://www.nseindia.com", timeout=5)
        r = s.get(NSE_URL, timeout=10)
        r.raise_for_status()
    df = pd.read_csv(StringIO(r.content.decode("utf-8")))
    return df

def main():
    run_id = str(uuid.uuid4())
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL env var is missing")

    engine = create_engine(db_url)

    # DB check
    with engine.connect() as conn:
        val = conn.execute(text("select 1")).scalar()
        print("DB OK:", val)

    # Universe fetch
    t0 = time.time()
    df = fetch_nifty50()
    print("Universe rows:", len(df), "| seconds:", round(time.time() - t0, 2))
    print(df.head(3).to_string(index=False))

if __name__ == "__main__":
    main()
