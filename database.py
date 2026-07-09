import sqlite3
from datetime import datetime
from pathlib import Path


DB_PATH = Path("looking_glass.db")


def get_connection():
    return sqlite3.connect(DB_PATH)


def initialize_database():
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                category TEXT,
                series_name TEXT,
                series_ticker TEXT,
                market_ticker TEXT,
                title TEXT,
                yes_bid REAL,
                yes_ask REAL,
                last_price REAL,
                volume REAL,
                liquidity REAL
            )
        """)

        connection.commit()


def save_market_scans(markets):
    timestamp = datetime.now().isoformat(timespec="seconds")

    rows = [
        (
            timestamp,
            market.get("category"),
            market.get("series_name"),
            market.get("series_ticker"),
            market.get("ticker"),
            market.get("title"),
            float(market.get("yes_bid_dollars") or 0),
            float(market.get("yes_ask_dollars") or 0),
            float(market.get("last_price_dollars") or 0),
            float(market.get("volume_fp") or 0),
            float(market.get("liquidity_dollars") or 0),
        )
        for market in markets
    ]

    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.executemany("""
            INSERT INTO market_scans (
                timestamp,
                category,
                series_name,
                series_ticker,
                market_ticker,
                title,
                yes_bid,
                yes_ask,
                last_price,
                volume,
                liquidity
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

        connection.commit()


def get_recent_scans_as_dicts(limit=200):
    with get_connection() as connection:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT
                timestamp,
                category,
                series_name,
                series_ticker,
                market_ticker,
                title,
                yes_bid,
                yes_ask,
                last_price,
                volume,
                liquidity
            FROM market_scans
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))

        rows = cursor.fetchall()

    return [
        {
            "Timestamp": row[0],
            "Category": row[1],
            "Series": row[2],
            "Series Ticker": row[3],
            "Ticker": row[4],
            "Title": row[5],
            "YES Bid": row[6],
            "YES Ask": row[7],
            "Last Price": row[8],
            "Volume": row[9],
            "Liquidity": row[10],
        }
        for row in rows
    ]