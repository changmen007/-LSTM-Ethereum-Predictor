from sqlalchemy import Column, Integer, Float, String, DateTime, Boolean, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()

class TradingSnapshot(Base):
    """交易快照数据"""
    __tablename__ = 'trading_snapshots'
    
    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow)
    initial_capital = Column(Float)
    current_cash = Column(Float)
    position_size = Column(Float)
    position_entry_price = Column(Float)
    current_price = Column(Float)
    position_cost = Column(Float)
    position_value = Column(Float)
    unrealized_pnl = Column(Float)
    portfolio_value = Column(Float)
    total_return_rate = Column(Float)
    max_drawdown = Column(Float)
    closed_trades = Column(Integer)
    profitable_trades = Column(Integer)
    win_rate = Column(Float)
    realized_pnl = Column(Float)

class Trade(Base):
    """交易记录"""
    __tablename__ = 'trades'
    
    id = Column(Integer, primary_key=True)
    entry_type = Column(String)  # 'buy' or 'sell'
    entry_price = Column(Float)
    entry_size = Column(Float)
    entry_time = Column(DateTime)
    exit_price = Column(Float, nullable=True)
    exit_size = Column(Float, nullable=True)
    exit_time = Column(DateTime, nullable=True)
    pnl = Column(Float, default=0.0)
    return_rate = Column(Float, default=0.0)
    holding_hours = Column(Integer, default=0)
    is_closed = Column(Boolean, default=False)

# 创建数据库引擎和会话
engine = create_engine('sqlite:///trading.db')
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)
