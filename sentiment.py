import sqlite3
import pandas as pd
import requests
from bs4 import BeautifulSoup
import nltk
from nltk.sentiment.vader import SentimentIntensityAnalyzer

# Download VADER lexicon for NLTK (only downloads once)
nltk.download('vader_lexicon', quiet=True)

DB_NAME = "market_data.db"
TICKERS = ["AAPL", "NVDA", "MSFT", "TSLA", "SPY"]

def fetch_finviz_news(ticker):
    """Scrapes recent news headlines for a ticker from FinViz."""
    url = f"https://finviz.com/quote.ashx?t={ticker}"
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    
    try:
        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            print(f"  -> Warning: HTTP {response.status_code} for {ticker}")
            return []
            
        soup = BeautifulSoup(response.content, 'html.parser')
        news_table = soup.find(id='news-table')
        
        if not news_table:
            return []
            
        headlines = []
        for row in news_table.find_all('tr'):
            a_tag = row.find('a')
            if a_tag:
                headlines.append(a_tag.text.strip())
        return headlines
        
    except Exception as e:
        print(f"  -> Error fetching news for {ticker}: {e}")
        return []

def process_sentiment_scores():
    """Scores news headlines and saves sentiment values to SQLite."""
    print(f"Connecting to database: {DB_NAME}...")
    conn = sqlite3.connect(DB_NAME)
    sia = SentimentIntensityAnalyzer()
    
    results = []
    
    print("Fetching headlines and scoring sentiment...")
    for ticker in TICKERS:
        print(f"Processing news for {ticker}...")
        headlines = fetch_finviz_news(ticker)
        
        if not headlines:
            print(f"  -> No headlines found for {ticker}.")
            continue
            
        # Score each headline using VADER
        compound_scores = []
        for text in headlines[:10]: # Process top 10 most recent headlines
            score = sia.polarity_scores(text)['compound']
            compound_scores.append(score)
            
        # Calculate average sentiment (-1.0 Bearish to +1.0 Bullish)
        avg_sentiment = sum(compound_scores) / len(compound_scores)
        
        results.append({
            'Ticker': ticker,
            'Headlines_Analyzed': len(compound_scores),
            'Sentiment_Score': round(avg_sentiment, 4)
        })
        print(f"  -> Average Sentiment for {ticker}: {round(avg_sentiment, 4)}")
        
    df = pd.DataFrame(results)
    
    if not df.empty:
        # Save sentiment to news_sentiment table
        df.to_sql("news_sentiment", conn, if_exists="replace", index=False)
        print("\n✅ News sentiment successfully saved to 'news_sentiment' table!")
    else:
        print("\n❌ No sentiment data generated.")
        
    conn.close()

if __name__ == "__main__":
    process_sentiment_scores()