import os
import uuid
import pandas as pd
import numpy as np
from sqlalchemy import create_engine, text

def get_engine():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL env var is missing")
    return create_engine(db_url)

def add_macd(df, fast=12, slow=26, signal=9):
    df = df.sort_values("date").copy()
    close = df["close_price"].astype(float)

    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()

    df["macd"] = ema_fast - ema_slow
    df["macd_signal"] = df["macd"].ewm(span=signal, adjust=False).mean()
    df["macd_hist"] = df["macd"] - df["macd_signal"]
    return df

def make_signals(df):
    df = df.sort_values(["symbol", "date"]).copy()
    df["macd_prev"] = df.groupby("symbol")["macd"].shift(1)
    df["sig_prev"]  = df.groupby("symbol")["macd_signal"].shift(1)

    buy = (df["macd"] > df["macd_signal"]) & (df["macd_prev"] <= df["sig_prev"])
    sell = (df["macd"] < df["macd_signal"]) & (df["macd_prev"] >= df["sig_prev"])

    df["signal"] = np.where(buy, "BUY", np.where(sell, "SELL", "HOLD"))
    return df

def ensure_technical_signals_table(engine):
    ddl = """
    CREATE TABLE IF NOT EXISTS technical_signals (
        symbol TEXT NOT NULL,
        signal_date DATE NOT NULL,
        close_price DOUBLE PRECISION,
        macd DOUBLE PRECISION,
        macd_signal DOUBLE PRECISION,
        macd_hist DOUBLE PRECISION,
        signal TEXT NOT NULL,
        run_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (symbol, signal_date)
    );
    """
    with engine.begin() as conn:
        conn.execute(text(ddl))

def main():
    run_id = str(uuid.uuid4())
    engine = get_engine()

    ensure_technical_signals_table(engine)

    # Pull 1 year of prices (or all) from DB
    prices = pd.read
