import os
import re
import numpy as np
import yfinance as yf
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI(title="AI Stock Terminal API")

# Enable CORS for local index.html and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini Client (Reads GEMINI_API_KEY from environment)
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")
ai_client = genai.Client(api_key=GEMINI_KEY) if GEMINI_KEY else None

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
    """Calculates 14-day RSI safely using NumPy."""
    if len(prices) < window + 1:
        return 50.0
    
    deltas = np.diff(prices)
    seed = deltas[:window+1]
    up = seed[seed >= 0].sum() / window
    down = -seed[seed < 0].sum() / window
    
    rs = up / down if down != 0 else 0
    rsi = np.zeros_like(prices)
    rsi[:window] = 100. - 100. / (1. + rs)

    for i in range(window, len(prices)):
        delta = deltas[i - 1]
        upval = delta if delta > 0 else 0.
        downval = -delta if delta < 0 else 0.

        up = (up * (window - 1) + upval) / window
        down = (down * (window - 1) + downval) / window
        rs = up / down if down != 0 else 0
        rsi[i] = 100. - 100. / (1. + rs)

    return round(float(rsi[-1]), 2)

def analyze_sentiment(symbol):
    """Lightweight headline keyword analyzer (No NLTK or TextBlob needed)."""
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        if not news:
            return "NEUTRAL"
        
        bullish_words = {"growth", "gain", "profit", "surge", "buy", "up", "bull", "high", "record", "beat"}
        bearish_words = {"drop", "fall", "loss", "decline", "sell", "down", "bear", "low", "risk", "miss"}
        
        score = 0
        for item in news[:5]:
            title = item.get("title", "").lower()
            for word in title.split():
                if word in bullish_words:
                    score += 1
                elif word in bearish_words:
                    score -= 1

        if score > 0:
            return "BULLISH"
        elif score < 0:
            return "BEARISH"
        return "NEUTRAL"
    except Exception:
        return "NEUTRAL"

@app.get("/")
def read_root():
    return {"status": "online", "service": "AI Stock Terminal API"}

@app.get("/api/signals")
def get_signals(category: str = Query("markets")):
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
            rsi = calculate_rsi(prices)
            sentiment = analyze_sentiment(symbol)
            
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

            clean_symbol = symbol.replace("=X", "").replace("=F", "").replace("^", "")
            results.append({
                "symbol": clean_symbol,
                "price": current_price,
                "rsi": rsi,
                "sentiment": sentiment,
                "signal": signal,
                "confidence": confidence
            })
        except Exception as e:
            print(f"Error processing {symbol}: {e}")

    return {"category": category, "signals": results}

@app.post("/api/chat")
def ai_stock_advisor(payload: dict = Body(...)):
    user_prompt = payload.get("prompt", "")
    
    # Extract ticker symbol candidate
    extracted_symbols = re.findall(r'\b[A-Za-z]{1,5}\b', user_prompt.upper())
    ignore_words = {"WHAT", "HOW", "IS", "BUY", "SELL", "STOCK", "GOOD", "THE", "CAN", "FOR", "SHOULD", "I"}
    filtered_symbols = [s for s in extracted_symbols if s not in ignore_words]
    symbol = filtered_symbols[0] if filtered_symbols else "AAPL"

    current_price = "N/A"
    rsi = "N/A"
    sentiment = "NEUTRAL"
    
    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")
        if not hist.empty:
            prices = hist['Close'].values
            current_price = f"${round(float(prices[-1]), 2)}"
            rsi = calculate_rsi(prices)
            sentiment = analyze_sentiment(symbol)
    except Exception as e:
        print(f"Fetch error for {symbol}: {e}")

    if not ai_client:
        return {
            "symbol": symbol,
            "response": f"**[Market Data Context]**\nSymbol: {symbol} | Price: {current_price} | RSI: {rsi} | Sentiment: {sentiment}\n\n*Set the `GEMINI_API_KEY` environment variable in your Render dashboard to enable conversational AI output.*"
        }

    prompt = f"""
    You are an expert AI Stock Analyst.
    User Question: "{user_prompt}"

    Live Market Metrics for {symbol}:
    - Current Price: {current_price}
    - 14-Day RSI: {rsi}
    - News Sentiment: {sentiment}

    Provide a concise, formatted Markdown analysis containing:
    1. Technical Summary
    2. Risk Factor
    3. Final Recommendation (Buy, Hold, or Sell)
    End with a brief 1-sentence legal disclaimer.
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return {"symbol": symbol, "response": response.text}
    except Exception as err:
        return {"symbol": symbol, "response": f"AI Engine error: {str(err)}"}