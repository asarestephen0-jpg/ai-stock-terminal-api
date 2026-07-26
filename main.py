from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="AI Stock Terminal API",
    description="Live stock signals and financial analytics backend.",
    version="1.0.0"
)

# Enable Cross-Origin Resource Sharing (CORS)
# This allows index.html (and other domains) to query the Render API without browser blocks
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows requests from any origin/local file
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, OPTIONS, etc.
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "status": "online",
        "service": "AI Stock Terminal API",
        "docs": "/docs"
    }

@app.get("/api/signals")
def get_signals():
    # Return active stock market signals
    return [
        {
            "symbol": "AAPL",
            "signal": "BUY",
            "price": 224.50,
            "rsi": 42.1,
            "sentiment": "Bullish",
            "confidence": 0.88
        },
        {
            "symbol": "NVDA",
            "signal": "HOLD",
            "price": 118.20,
            "rsi": 58.6,
            "sentiment": "Neutral",
            "confidence": 0.65
        },
        {
            "symbol": "TSLA",
            "signal": "SELL",
            "price": 215.40,
            "rsi": 71.8,
            "sentiment": "Bearish",
            "confidence": 0.74
        }
    ]