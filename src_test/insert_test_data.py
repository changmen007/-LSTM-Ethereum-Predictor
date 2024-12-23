from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, TradingSnapshot, Trade
import random

# 创建数据库引擎
engine = create_engine('sqlite:///trading.db')
Base.metadata.create_all(engine)

# 创建会话
Session = sessionmaker(bind=engine)
session = Session()

# 清除现有数据
session.query(TradingSnapshot).delete()
session.query(Trade).delete()
session.commit()

# 生成测试数据
initial_capital = 10000
current_timestamp = datetime.now() - timedelta(hours=24)  # 从24小时前开始
current_cash = initial_capital
position_size = 0
current_price = 2000  # ETH初始价格
position_entry_price = current_price
closed_trades = 0
profitable_trades = 0
realized_pnl = 0

# 生成交易快照
for i in range(100):
    # 模拟价格变动
    price_change = random.uniform(-50, 50)
    current_price += price_change
    
    # 随机生成交易信号
    if random.random() < 0.1:  # 10%概率发生交易
        if position_size == 0:  # 开仓
            position_size = random.uniform(0.1, 0.5)  # 随机仓位
            position_entry_price = current_price
            current_cash -= position_size * current_price
            
            trade = Trade(
                entry_type='buy',
                entry_price=current_price,
                entry_size=position_size,
                entry_time=current_timestamp,
                is_closed=False
            )
            session.add(trade)
        else:  # 平仓
            trade_pnl = (current_price - position_entry_price) * position_size
            realized_pnl += trade_pnl
            current_cash += position_size * current_price
            
            if trade_pnl > 0:
                profitable_trades += 1
            closed_trades += 1
            
            trade = Trade(
                entry_type='sell',
                entry_price=current_price,
                entry_size=position_size,
                entry_time=current_timestamp,
                pnl=trade_pnl,
                return_rate=(trade_pnl / (position_size * position_entry_price)) * 100,
                is_closed=True
            )
            session.add(trade)
            position_size = 0
    
    # 计算当前持仓价值和未实现盈亏
    position_cost = position_size * position_entry_price if position_size > 0 else 0
    position_value = position_size * current_price if position_size > 0 else 0
    unrealized_pnl = position_value - position_cost if position_size > 0 else 0
    
    # 计算组合总值和收益率
    portfolio_value = current_cash + position_value
    total_return_rate = (portfolio_value - initial_capital) / initial_capital * 100
    
    # 计算最大回撤
    max_drawdown = random.uniform(-15, 0)  # 随机回撤，负数表示损失
    
    # 计算胜率
    win_rate = (profitable_trades / closed_trades * 100) if closed_trades > 0 else 0
    
    # 创建交易快照
    snapshot = TradingSnapshot(
        timestamp=current_timestamp,
        initial_capital=initial_capital,
        current_cash=current_cash,
        position_size=position_size,
        position_entry_price=position_entry_price,
        current_price=current_price,
        position_cost=position_cost,
        position_value=position_value,
        unrealized_pnl=unrealized_pnl,
        portfolio_value=portfolio_value,
        total_return_rate=total_return_rate,
        max_drawdown=max_drawdown,
        closed_trades=closed_trades,
        profitable_trades=profitable_trades,
        win_rate=win_rate,
        realized_pnl=realized_pnl
    )
    session.add(snapshot)
    
    # 更新时间戳
    current_timestamp += timedelta(minutes=15)  # 每15分钟一个数据点

# 提交所有更改
session.commit()
session.close()

print("测试数据已插入到数据库中。")
