from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
from textblob import TextBlob
import numpy as np

app = FastAPI(title="AI Stock Terminal API")

# Enable CORS for local and web frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ticker mapping per frontend category
CATEGORY_TICKERS = {
    "markets": ["^DJI", "^GSPC", "^IXIC"],
    "us": ["AAPL", "NVDA", "TSLA", "MSFT", "AMZN"],
    "futures": ["ES=F", "NQ=F", "YM=F"],
    "global": ["^FTSE", "^N225", "^GDAXI"],
    "commodities": ["CL=F", "GC=F", "SI=F", "NG=F"],
    "currencies": ["EURUSD=X", "GBPUSD=X", "USDJPY=X"],
    "cryptos": ["BTC-USD", "ETH-USD", "SOL-USD"]
}

def calculate_rsi(prices, window=14):
    """Calculate Relative Strength Index (RSI)"""
    deltas = np.diff(prices)
    seed = deltas[:window+1]
    up = seed[seed >= 0].sum()/window
    down = -seed[seed < 0].sum()/window
    rs = up/down if down != 0 else 0
    
    rsi = np.zeros_like(prices)
    rsi[:window] = 100. - 100./(1. + rs)

    for i in range(window, len(prices)):
        delta = deltas[i - 1]
        if delta > 0:
            upval = delta
            downval = 0.
        else:
            upval = 0.
            downval = -delta

        up = (up * (window - 1) + upval) / window
        down = (down * (window - 1) + downval) / window
        rs = up/down if down != 0 else 0
        rsi[i] = 100. - 100./(1. + rs)

    return round(float(rsi[-1]), 2)

def analyze_sentiment(symbol):
    """Analyze news sentiment polarity using TextBlob"""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        if not news:
            return "NEUTRAL"
        
        scores = []
        for item in news[:5]: # Analyze latest 5 news headlines
            title = item.get("title", "")
            blob = TextBlob(title)
            scores.append(blob.sentiment.polarity)
        
        avg_score = np.mean(scores) if scores else 0
        if avg_score > 0.05:
            return "BULLISH"
        elif avg_score < -0.05:
            return "BEARISH"
        return "NEUTRAL"
    except Exception:
        return "NEUTRAL"

@app.get("/")
def root():
    return {"status": "online", "system": "AI Stock Terminal Engine"}

@app.get("/api/signals")
def get_signals(category: str = Query("markets")):
    """Generates AI Signals by combining RSI and News Sentiment"""
    category_key = category.lower()
    tickers = CATEGORY_TICKERS.get(category_key, CATEGORY_TICKERS["markets"])
    results = []

    for symbol in tickers:
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1mo")
            
            if hist.empty or len(hist) < 15:
                continue

            prices = hist['Close'].values
            current_price = round(float(prices[-1]), 2)
            
            # Technical Analysis (RSI)
            rsi = calculate_rsi(prices)
            
            # Sentiment Analysis (News Headlines)
            sentiment = analyze_sentiment(symbol)
            
            # AI Signal Generation Logic
            signal = "HOLD"
            confidence = 0.50

            if rsi < 35 and sentiment == "BULLISH":
                signal = "STRONG BUY"
                confidence = 0.88
            elif rsi < 42:
                signal = "BUY"
                confidence = 0.72
            elif rsi > 65 and sentiment == "BEARISH":
                signal = "STRONG SELL"
                confidence = 0.85
            elif rsi > 60:
                signal = "SELL"
                confidence = 0.68

            results.append({
                "symbol": symbol.replace("=X", "").replace("=F", "").replace("^", ""),
                "price": current_price,
                "rsi": rsi,
                "sentiment": sentiment,
                "signal": signal,
                "confidence": confidence
            })
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    return {"category": category, "signals": results}