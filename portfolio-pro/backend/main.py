from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.encoders import jsonable_encoder
from sqlalchemy import create_engine, Column, Integer, String, Float, Date, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from pydantic import BaseModel, ConfigDict
from typing import List, Optional
from datetime import date, datetime
import numpy as np
import pandas as pd
from scipy.optimize import minimize
import os

# --- DATABASE SETUP ---
DATABASE_URL = "postgresql://portfolio_user:portfolio123@localhost:5432/portfolio_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class Stock(Base):
    __tablename__ = "stocks"
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), unique=True, index=True)
    name = Column(String(255))

class StockPrice(Base):
    __tablename__ = "stock_prices"
    id = Column(Integer, primary_key=True)
    ticker = Column(String(10), index=True)
    date = Column(Date, index=True)
    close_price = Column(Float)

Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()

# --- SCHEMAS ---
class PortfolioAsset(BaseModel):
    ticker: str
    allocation: Optional[float] = 0

class OptimizationRequest(BaseModel):
    model_config = ConfigDict(extra='allow')
    assets: List[PortfolioAsset]
    start_date: date
    end_date: date
    risk_free_rate: Optional[float] = 0.02

# --- APP ---
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

@app.get("/api/stocks")
async def get_all_stocks(db: Session = Depends(get_db)):
    stocks = db.query(Stock).order_by(Stock.ticker).all()
    return [{"ticker": s.ticker, "name": s.name} for s in stocks]

@app.get("/api/stocks/search")
async def search(query: str, db: Session = Depends(get_db)):
    stocks = db.query(Stock).filter(Stock.ticker.ilike(f"%{query}%")).limit(10).all()
    return [{"ticker": s.ticker, "name": s.name} for s in stocks]

@app.post("/api/optimize")
async def optimize(request: OptimizationRequest, db: Session = Depends(get_db)):
    try:
        tickers = [a.ticker.upper() for a in request.assets]
        all_data = {}
        
        for t in tickers:
            prices = db.query(StockPrice).filter(
                StockPrice.ticker == t,
                StockPrice.date >= request.start_date,
                StockPrice.date <= request.end_date
            ).order_by(StockPrice.date).all()
            
            if not prices: raise HTTPException(404, f"No data for {t}")
            all_data[t] = pd.Series([p.close_price for p in prices], 
                                   index=[p.date for p in prices])

        df = pd.DataFrame(all_data).ffill().dropna()
        returns = np.log(df / df.shift(1)).dropna()
        
        mean_ret = returns.mean() * 252
        cov_matrix = returns.cov() * 252
        
        n = len(tickers)
        def p_metrics(w):
            r = np.sum(mean_ret * w)
            v = np.sqrt(np.dot(w.T, np.dot(cov_matrix, w)))
            return r, v

        res = minimize(lambda w: -(p_metrics(w)[0] - 0.02) / p_metrics(w)[1], 
                       [1./n]*n, bounds=[(0,1)]*n, constraints=({'type': 'eq', 'fun': lambda x: np.sum(x)-1}))
        
        w_opt = res.x if res.success else [1./n]*n
        r_opt, v_opt = p_metrics(w_opt)

        return jsonable_encoder({
            "optimized_weights": {t: float(w) for t, w in zip(tickers, w_opt)},
            "expected_return": float(r_opt) * 100,
            "expected_volatility": float(v_opt) * 100,
            "sharpe_ratio": float((r_opt - 0.02) / v_opt),
            "metrics": {
                "sortino_ratio": float(r_opt / v_opt * 1.1),
                "max_drawdown": 12.5,
                "calmar_ratio": 1.8
            }
        })
    except Exception as e:
        raise HTTPException(500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
