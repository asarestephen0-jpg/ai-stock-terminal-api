
import yfinance as yf
import sqlite3
import pandas as pd
from datetime import date, timedelta

TICKERS = ["AAPL", "NVDA", "MSFT", "TSLA", "SPY"]
DB_NAME = "market_data.db"

def build_historical_database():
    print(f"Connecting to database: {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    
    end_date = date.today()
    start_date = end_date - timedelta(days=730) 
    
    print(f"Fetching daily price data from {start_date} to {end_date}...\n")

    for ticker in TICKERS:
        try:
            print(f"Pulling data for {ticker}...")
            stock = yf.Ticker(ticker)
            df = stock.history(start=start_date, end=end_date)
            
            if df.empty:
                print(f"  -> Warning: No data found for {ticker}. Skipping.")
                continue
            
            df = df[['Open', 'High', 'Low', 'Close', 'Volume']]
            df.reset_index(inplace=True)
            df['Date'] = pd.to_datetime(df['Date']).dt.date 
            df['Ticker'] = ticker
            
            df.to_sql("daily_prices", conn, if_exists="append", index=False)
            print(f"  -> Successfully saved {len(df)} days of data for {ticker}.")
            
        except Exception as e:
            print(f"  -> Error processing {ticker}: {e}")

    conn.close()
    print("\n✅ Database build complete!")

if __name__ == "__main__":
    build_historical_database()