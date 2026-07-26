import sqlite3
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

DB_NAME = "market_data.db"

app = FastAPI(
    title="AI Stock Signal API",
    description="REST API serving technical indicators, news sentiment, and AI trade recommendations.",
    version="1.0.0"
)

# Enable CORS so web apps (React/Flutter) can call this API directly
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    """Returns a SQLite connection formatted as dictionaries."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    return conn

@app.get("/")
def read_root():
    """Health check endpoint."""
    return {
        "status": "online",
        "service": "AI Stock Signal Engine API",
        "endpoints": ["/api/signals", "/api/signals/{ticker}"]
    }

@app.get("/api/signals")
def get_all_signals(signal_filter: Optional[str] = None):
    """
    Returns AI signals for all tracked stocks.
    Optional query parameter: ?signal_filter=BUY (or HOLD, SELL)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if signal_filter:
        query = "SELECT * FROM ai_signals WHERE UPPER(Signal) = ?"
        rows = cursor.execute(query, (signal_filter.upper(),)).fetchall()
    else:
        query = "SELECT * FROM ai_signals ORDER BY Confidence_Score DESC"
        rows = cursor.execute(query).fetchall()
        
    conn.close()
    
    signals = [dict(row) for row in rows]
    return {
        "count": len(signals),
        "data": signals
    }

@app.get("/api/signals/{ticker}")
def get_signal_by_ticker(ticker: str):
    """Returns the AI recommendation and summary for a specific stock ticker."""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    row = cursor.execute(
        "SELECT * FROM ai_signals WHERE UPPER(Ticker) = ?", 
        (ticker.upper(),)
    ).fetchone()
    
    conn.close()
    
    if not row:
        raise HTTPException(
            status_code=404, 
            detail=f"Ticker '{ticker.upper()}' not found in AI signals database."
        )
        
    return {"data": dict(row)}