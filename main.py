import os
import re
import numpy as np
import yfinance as yf
from textblob import TextBlob
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from google import genai

app = FastAPI(title="AI Stock Terminal API")

# Enable CORS for local testing and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Gemini Client (Uses GEMINI_API_KEY environment variable)
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
    if len(prices) < window + 1:
        return 50.0
    deltas = np.diff(prices)
    seed = deltas[:window+1]
    up = seed[seed >= 0].sum()/window
    down = -seed[seed < 0].sum()/window
    rs = up/down if down != 0 else 0
    
    rsi = np.zeros_like(prices)
    rsi[:window] = 100. - 100./(1. + rs)

    for i in range(window, len(prices)):
        delta = deltas[i - 1]
        upval = delta if delta > 0 else 0.
        downval = -delta if delta < 0 else 0.

        up = (up * (window - 1) + upval) / window
        down = (down * (window - 1) + downval) / window
        rs = up/down if down != 0 else 0
        rsi[i] = 100. - 100./(1. + rs)

    return round(float(rsi[-1]), 2)

def analyze_sentiment(symbol):
    try:
        ticker = yf.Ticker(symbol)
        news = ticker.news
        if not news:
            return "NEUTRAL"
        
        scores = [TextBlob(item.get("title", "")).sentiment.polarity for item in news[:5]]
        avg_score = np.mean(scores) if scores else 0
        if avg_score > 0.05:
            return "BULLISH"
        elif avg_score < -0.05:
            return "BEARISH"
        return "NEUTRAL"
    except Exception:
        return "NEUTRAL"

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

@app.post("/api/chat")
def ai_stock_advisor(payload: dict = Body(...)):
    user_prompt = payload.get("prompt", "")
    
    # Simple regex extraction for ticker symbols (e.g. AAPL, NVDA, TSLA)
    extracted_symbols = re.findall(r'\b[A-Za-z]{1,5}\b', user_prompt.upper())
    symbol = "AAPL"
    
    # Common words exclusion filter
    ignore_words = {"WHAT", "HOW", "IS", "BUY", "SELL", "STOCK", "GOOD", "THE", "CAN", "FOR"}
    filtered_symbols = [s for s in extracted_symbols if s not in ignore_words]
    if filtered_symbols:
        symbol = filtered_symbols[0]

    # Fetch live financial context
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
        print(f"yfinance fetch error for {symbol}: {e}")

    # Fallback response if Gemini API key isn't set yet
    if not ai_client:
        return {
            "symbol": symbol,
            "response": f"**[Market Data]** Symbol: `{symbol}` | Price: `{current_price}` | RSI: `{rsi}` | Sentiment: `{sentiment}`.\n\n*Note: Add your GEMINI_API_KEY environment variable on Render to activate full conversational AI responses.*"
        }

    # Construct System Prompt with live data context
    system_instruction = f"""
    You are an expert AI Stock Market Analyst.
    The user is asking: "{user_prompt}"
    
    Here is the live market context for {symbol}:
    - Current Price: {current_price}
    - 14-day RSI: {rsi}
    - News Sentiment: {sentiment}

    Provide a concise, professional financial breakdown formatted in Markdown:
    1. Technical Summary
    2. Sentiment & Risk Factor
    3. Actionable Verdict (Buy, Hold, or Sell)
    Always end with a 1-sentence standard educational legal disclaimer.
    """

    try:
        response = ai_client.models.generate_content(
            model='gemini-2.5-flash',
            contents=system_instruction,
        )
        return {"symbol": symbol, "response": response.text}
    except Exception as err:
        return {"symbol": symbol, "response": f"AI Engine error: {str(err)}"}