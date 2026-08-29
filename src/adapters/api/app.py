from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import uvicorn

from src.adapters.persistence.sql_repository import SQLStockPriceRepository
from src.application.portfolio_calculation_use_case import PortfolioCalculationUseCase

app = FastAPI(
    title="PortfolioPredictions API Service",
    description="Interactive backend service for recalculating custom portfolios, filtering tickers, and risk targeting.",
    version="1.0.0"
)

# Enable CORS for web frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema
class PortfolioRequest(BaseModel):
    strategy: str  # 'mean_variance', 'min_variance', 'hrp', 'political', 'sentiment'
    risk_level: Optional[str] = "medium"  # 'low', 'medium', 'high'
    excluded_tickers: Optional[List[str]] = []

# Dependency Injection
stock_repo = SQLStockPriceRepository()
calculation_use_case = PortfolioCalculationUseCase(stock_repo=stock_repo)

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "PortfolioPredictions API"}

@app.post("/api/portfolio/calculate")
def calculate_portfolio(req: PortfolioRequest):
    try:
        result = calculation_use_case.calculate_custom_portfolio(
            strategy=req.strategy,
            risk_level=req.risk_level,
            excluded_tickers=req.excluded_tickers
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

if __name__ == "__main__":
    uvicorn.run("src.adapters.api.app:app", host="0.0.0.0", port=8000, reload=True)
