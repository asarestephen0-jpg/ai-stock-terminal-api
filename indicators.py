import sqlite3
import pandas as pd

DB_NAME = "market_data.db"

def calculate_rsi(series, period=14):
    """Calculates the Relative Strength Index (RSI)."""
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -1 * delta.clip(upper=0)
    
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()
    
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    return rsi

def process_technical_indicators():
    """Reads stock data from SQLite, computes indicators, and writes them back."""
    print(f"Connecting to database: {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    
    # Read historical prices from daily_prices table
    df = pd.read_sql("SELECT * FROM daily_prices", conn)
    
    if df.empty:
        print("❌ Error: No price data found in daily_prices table!")
        conn.close()
        return

    # Ensure Date ordering for rolling calculations
    df['Date'] = pd.to_datetime(df['Date'])
    df = df.sort_values(by=['Ticker', 'Date']).reset_index(drop=True)

    print("Calculating RSI (14-day) and Simple Moving Averages (20-day, 50-day)...")

    # Group by Ticker so moving windows stay isolated per stock
    df['SMA_20'] = df.groupby('Ticker')['Close'].transform(lambda x: x.rolling(window=20).mean())
    df['SMA_50'] = df.groupby('Ticker')['Close'].transform(lambda x: x.rolling(window=50).mean())
    df['RSI'] = df.groupby('Ticker')['Close'].transform(lambda x: calculate_rsi(x, period=14))

    # Write the new table to SQLite
    df.to_sql("stock_indicators", conn, if_exists="replace", index=False)
    conn.close()
    
    print("✅ Technical indicators successfully calculated and saved to 'stock_indicators' table!")

if __name__ == "__main__":
    process_technical_indicators()