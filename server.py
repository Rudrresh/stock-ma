from fastapi import FastAPI, HTTPException, BackgroundTasks
import yfinance as yf
import pandas as pd
from datetime import date, timedelta
from typing import List
import logging
import asyncio
import aiohttp
import os

# Basic startup logging to help debugging on hosts like Render
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stock-ma")

app = FastAPI(title="Dip Buying Trigger API")

# Background task to keep the server alive
async def keep_alive():
    """Ping self every 14 minutes to prevent Render from sleeping."""
    ping_url = f"http://0.0.0.0:{os.getenv('PORT', '8000')}/ping"
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                async with session.head(ping_url) as response:
                    logger.info(f"Self-ping status: {response.status}")
            except Exception as e:
                logger.error(f"Self-ping failed: {e}")
            await asyncio.sleep(840)  # 14 minutes

@app.on_event("startup")
async def start_keep_alive():
    """Start the keep-alive background task when the app starts."""
    asyncio.create_task(keep_alive())


@app.on_event("startup")
def _startup_event():
    # This prints to stdout/stderr which hosted platforms capture in logs
    logger.info("Starting stock-ma FastAPI app — registering routes...")
    print("[stock-ma] server module imported and startup event fired")


index_options = {
    "S&P 500": "^GSPC",
    "Nifty 50": "^NSEI",
    "Nifty Midcap 150": "0P0001IAU9.BO",
    "Nifty Smallcap 250": "0P0001Q0UH.BO",
    "NASDAQ": "^IXIC",
    "BTC": "BTC-USD",
}


def _get_last_close_and_dma(data: pd.DataFrame):
    """Return (last_close, last_200dma) as floats from a yfinance history DataFrame.

    Handles both Series and DataFrame shapes returned by yf.download/history.
    """
    if data is None or data.empty:
        raise ValueError("no data")

    # Extract Close column (could be Series or DataFrame)
    close_col = data.get("Close") if isinstance(data, dict) else data["Close"] if "Close" in data.columns else None

    if close_col is None:
        raise ValueError("no Close column")

    # For safety convert to DataFrame
    close_df = pd.DataFrame(close_col)

    # compute 200DMA on each column (works if single or multi)
    dma = close_df.rolling(window=200).mean()

    # pick the last non-null close and corresponding dma value
    last_close = None
    last_dma = None
    # iterate over last row values to find a numeric one
    last_close_row = close_df.dropna(how="all").iloc[-1]
    last_dma_row = dma.dropna(how="all").iloc[-1] if not dma.dropna(how="all").empty else None

    # last_close_row may be a Series (multiple columns) or scalar-like
    if isinstance(last_close_row, pd.Series):
        for v in last_close_row.values:
            if pd.notna(v):
                last_close = float(v)
                break
    else:
        last_close = float(last_close_row)

    if last_dma_row is not None:
        if isinstance(last_dma_row, pd.Series):
            for v in last_dma_row.values:
                if pd.notna(v):
                    last_dma = float(v)
                    break
        else:
            last_dma = float(last_dma_row)

    if last_close is None or last_dma is None:
        raise ValueError("insufficient data for 200DMA or last close")

    return last_close, last_dma


@app.get("/", tags=["health"])
def read_root():
    return {"status": "ok", "message": "Dip Buying Trigger API"}

@app.head("/ping")
async def ping():
    """Lightweight ping endpoint for keep-alive."""
    return {"status": "ok"}


@app.get("/routes", tags=["debug"])
def list_routes():
    """Return registered routes so we can confirm the /dip endpoint is present on the running app.

    This is a temporary debug endpoint — remove it after troubleshooting.
    """
    routes = []
    for r in app.routes:
        routes.append({
            "path": r.path,
            "methods": sorted(list(r.methods)) if hasattr(r, "methods") else [],
        })
    return {"routes": routes}


@app.get("/dip", tags=["dip"])
def get_dip():
    """Return dip/buying recommendations for preset indices as JSON.

    This is a single static endpoint (no query parameters). It uses fixed thresholds:
    amount=100, dip_100=10, dip_50=7, dip_25=4
    """
    # Static/constant thresholds as requested
    amount = 100.0
    dip_100 = 10.0
    dip_50 = 7.0
    dip_25 = 4.0

    end_date = date.today()
    start_date = end_date - timedelta(days=1000)

    results: List[dict] = []

    for name, ticker in index_options.items():
        try:
            data = yf.download(ticker, start=start_date.strftime('%Y-%m-%d'), end=end_date.strftime('%Y-%m-%d'))
        except Exception:
            # skip tickers that fail
            continue

        if data is None or data.empty:
            continue

        # Ensure Close exists and enough points
        try:
            last_close, last_dma = _get_last_close_and_dma(data)
        except Exception:
            # skip if we can't get required numbers
            continue

        dip = ((last_dma - last_close) / last_dma) * 100

        if dip >= dip_100:
            action = "🟢 Deploy 100%"
            deploy_amount = amount
        elif dip >= dip_50:
            action = "🟡 Deploy 50%"
            deploy_amount = 0.5 * amount
        elif dip >= dip_25:
            action = "🟠 Deploy 25%"
            deploy_amount = 0.25 * amount
        else:
            action = "⚪ Hold"
            deploy_amount = 0

        results.append({
            "Index": name,
            "Ticker": ticker,
            "Current Price": round(last_close, 2),
            "200 DMA": round(last_dma, 2),
            "Dip %": round(dip, 2),
            "Action": action,
            "Deploy": round(deploy_amount, 2),
        })

    if not results:
        raise HTTPException(status_code=404, detail="No results available. Data may be missing or API limits reached.")

    return {"results": results}
