"""
SOL价格预测系统 API服务

使用说明：
1. 启动服务：
   在终端中运行：
   uvicorn api:app --reload --app-dir src

2. 本地访问：
   - API文档：http://localhost:8000/docs
   - 前端页面：http://localhost:8000/static/index.html

3. 外网访问（使用ngrok）：
   在新的终端中运行：
   ngrok http --domain=你的域名 8000
   ngrok http --domain=changmen.ngrok.io 8000

   
   之后可以通过以下地址访问：
   - API文档：https://你的域名/docs
   - 前端页面：https://你的域名/static/index.html
   - 当前页面：https://changmen.ngrok.io/static/index.html

注意事项：
- 确保src/static目录下存在index.html文件
- API服务默认运行在8000端口
- 已配置CORS，支持跨域请求
- 使用ngrok时确保本地服务已经启动
"""

from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, TradingSnapshot, Trade
from typing import List
from datetime import datetime, timedelta
from config import Config

#uvicorn api:app --reload --app-dir src

app = FastAPI()

# 添加API路由前缀
api_router = FastAPI(prefix="/api")

# 添加静态文件支持
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# 添加CORS中间件
api_router.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 创建数据库引擎和会话
engine = create_engine(Config.DATABASE_URL, connect_args={'check_same_thread': Config.CHECK_SAME_THREAD})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 依赖项
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# API路由
@api_router.get("/trading-data")
async def get_trading_data(db: SessionLocal = Depends(get_db)):
    """获取最近的交易数据"""
    # 获取最近24小时的数据
    start_time = datetime.utcnow() - timedelta(hours=Config.TRADING_DATA_HOURS)
    snapshots = db.query(TradingSnapshot).filter(
        TradingSnapshot.timestamp >= start_time
    ).all()
    
    return {
        "timestamps": [s.timestamp.isoformat() for s in snapshots],
        "portfolio_values": [s.portfolio_value for s in snapshots],
        "return_rates": [s.total_return_rate for s in snapshots],
        "unrealized_pnls": [s.unrealized_pnl for s in snapshots],
        "max_drawdowns": [s.max_drawdown for s in snapshots],
        "current_cash": [s.current_cash for s in snapshots],
        "position_values": [s.position_value for s in snapshots],
    }

@api_router.get("/trades")
async def get_trades(db: SessionLocal = Depends(get_db)):
    """获取所有交易记录"""
    trades = db.query(Trade).all()
    return trades

@api_router.get("/summary")
async def get_summary(db: SessionLocal = Depends(get_db)):
    """获取交易统计摘要"""
    latest = db.query(TradingSnapshot).order_by(
        TradingSnapshot.timestamp.desc()
    ).first()
    
    if latest:
        return {
            "portfolio_value": latest.portfolio_value,
            "total_return_rate": latest.total_return_rate,
            "max_drawdown": latest.max_drawdown,
            "win_rate": latest.win_rate,
            "closed_trades": latest.closed_trades,
            "profitable_trades": latest.profitable_trades,
            "realized_pnl": latest.realized_pnl,
        }
    return {}

@api_router.get("/trading-data-simplified")
async def get_trading_data_simplified(db: SessionLocal = Depends(get_db)):
    snapshots = db.query(TradingSnapshot).order_by(TradingSnapshot.timestamp.desc()).limit(Config.TRADING_DATA_LIMIT).all()
    snapshots.reverse()  # 按时间正序排列
    
    return {
        "timestamps": [s.timestamp for s in snapshots],
        "return_rates": [s.total_return_rate for s in snapshots],
        "current_cash": [s.current_cash for s in snapshots],
        "position_values": [s.position_value for s in snapshots],
        "unrealized_pnls": [s.unrealized_pnl for s in snapshots],
        "max_drawdowns": [s.max_drawdown for s in snapshots]
    }

@api_router.get("/summary-simplified")
async def get_summary_simplified(db: SessionLocal = Depends(get_db)):
    latest = db.query(TradingSnapshot).order_by(TradingSnapshot.timestamp.desc()).first()
    trades = db.query(Trade).all()
    
    # 计算胜率
    profitable_trades = len([t for t in trades if float(t.pnl) > 0])
    total_trades = len(trades)
    win_rate = (profitable_trades / total_trades * 100) if total_trades > 0 else 0
    
    return {
        "portfolio_value": latest.portfolio_value if latest else 0,
        "total_return_rate": latest.total_return_rate if latest else 0,
        "max_drawdown": latest.max_drawdown if latest else 0,
        "win_rate": win_rate
    }

# 将API路由挂载到主应用
app.mount("/api", api_router)

# 确保数据库和表存在
Base.metadata.create_all(engine)
