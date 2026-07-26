import sqlite3
import pandas as pd

DB_NAME = "market_data.db"

def calculate_stock_signal(row):
    """Evaluates technical indicators and sentiment scores to generate a rating."""
    score = 0
    reasons = []

    # 1. Trend Analysis (SMA 20 vs SMA 50) - 40 Points Max
    close = row['Close']
    sma_20 = row['SMA_20']
    sma_50 = row['SMA_50']

    if pd.notnull(sma_20) and pd.notnull(sma_50):
        if close > sma_20 and sma_20 > sma_50:
            score += 40
            reasons.append("Strong Uptrend (Close > SMA20 > SMA50)")
        elif close > sma_20:
            score += 25
            reasons.append("Moderate Uptrend (Close > SMA20)")
        else:
            reasons.append("Downtrend (Close below SMA20)")

    # 2. Momentum Analysis (RSI) - 30 Points Max
    rsi = row['RSI']
    if pd.notnull(rsi):
        if 30 <= rsi <= 60:
            score += 30  # Prime buying zone
            reasons.append(f"Optimal RSI ({round(rsi, 1)})")
        elif 60 < rsi < 70:
            score += 15  # Slight overbought momentum
            reasons.append(f"High Momentum RSI ({round(rsi, 1)})")
        elif rsi >= 70:
            score += 0   # Overbought risk
            reasons.append(f"Overbought Warning RSI ({round(rsi, 1)})")
        else:
            score += 5   # Oversold condition
            reasons.append(f"Oversold RSI ({round(rsi, 1)})")

    # 3. News Sentiment Analysis - 30 Points Max
    sentiment = row['Sentiment_Score']
    if pd.notnull(sentiment):
        if sentiment >= 0.15:
            score += 30
            reasons.append(f"Strong Bullish News ({sentiment})")
        elif 0.05 <= sentiment < 0.15:
            score += 20
            reasons.append(f"Mildly Positive News ({sentiment})")
        elif -0.05 < sentiment < 0.05:
            score += 10
            reasons.append("Neutral News Sentiment")
        else:
            score += 0
            reasons.append(f"Bearish News Sentiment ({sentiment})")

    # Final Decision Output
    if score >= 70:
        signal = "BUY"
    elif score >= 40:
        signal = "HOLD"
    else:
        signal = "SELL"

    return pd.Series([score, signal, " | ".join(reasons)], index=['Confidence_Score', 'Signal', 'Analysis_Summary'])

def generate_ai_signals():
    """Reads indicators + sentiment, calculates signals, and writes to SQLite."""
    print(f"Connecting to database: {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)

    # Get the latest daily indicators for each ticker
    query_indicators = """
        SELECT * FROM stock_indicators 
        WHERE (Ticker, Date) IN (
            SELECT Ticker, MAX(Date) FROM stock_indicators GROUP BY Ticker
        )
    """
    df_indicators = pd.read_sql(query_indicators, conn)

    # Get latest news sentiment scores
    df_sentiment = pd.read_sql("SELECT Ticker, Sentiment_Score FROM news_sentiment", conn)

    if df_indicators.empty:
        print("❌ Error: No technical indicators found in database.")
        conn.close()
        return

    # Merge technical indicators with sentiment scores
    df = pd.merge(df_indicators, df_sentiment, on="Ticker", how="left")

    print("Evaluating AI rules across stocks...")
    # Apply scoring function row by row
    signal_results = df.apply(calculate_stock_signal, axis=1)
    df[['Confidence_Score', 'Signal', 'Analysis_Summary']] = signal_results

    # Select key columns for the summary output table
    output_df = df[['Ticker', 'Date', 'Close', 'RSI', 'Sentiment_Score', 'Confidence_Score', 'Signal', 'Analysis_Summary']]

    # Save to ai_signals table in database
    output_df.to_sql("ai_signals", conn, if_exists="replace", index=False)
    conn.close()

    print("\n✅ AI Signal Engine complete! Output saved to 'ai_signals' table.")

if __name__ == "__main__":
    generate_ai_signals()