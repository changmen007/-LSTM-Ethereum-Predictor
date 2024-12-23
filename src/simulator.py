import json
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Dict, List, Optional
from trading_signals import SignalProvider, PredictionSignal
from models import SessionLocal, TradingSnapshot as DBTradingSnapshot, Trade as DBTrade
from config import Config

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

@dataclass
class Position:
    """仓位信息"""
    size: float  # 持仓数量
    entry_price: float  # 入场价格
    timestamp: datetime  # 开仓时间

@dataclass
class Trade:
    """交易记录"""
    entry_type: str  # 'buy' or 'sell'
    entry_price: float
    entry_size: float
    entry_time: datetime
    remaining_size: float  # 剩余未平仓数量
    exit_price: Optional[float] = None
    exit_size: Optional[float] = None
    exit_time: Optional[datetime] = None
    pnl: float = 0.0  # 平仓时的收益
    return_rate: float = 0.0  # 收益率
    holding_hours: int = 0  # 持仓时长（小时）
    is_closed: bool = False  # 是否已完全平仓

class TradingSimulator:
    def __init__(self, initial_capital: float = None, trade_history_file: str = None, log_file: str = None):
        """
        初始化交易模拟器
        Args:
            initial_capital: 初始资金，如果为None则使用配置文件中的值
            trade_history_file: 交易历史文件路径
            log_file: 日志文件路径
        """
        self.initial_capital = initial_capital or Config.INITIAL_CAPITAL
        self.cash = self.initial_capital
        self.position: Optional[Position] = None
        self.trades: List[Trade] = []  # 所有交易记录
        self.open_trades: List[Trade] = []  # 未平仓的交易
        self.trade_history_file = trade_history_file or str(Config.LOG_DIR / "trade_history.json")
        
        # 从配置文件获取交易参数
        trading_config = Config.get_trading_config()
        self.unit_size = trading_config["unit_size"]
        self.max_units = trading_config["max_units"]
        
        # 交易统计
        self.closed_trades = 0  # 已平仓的交易数（包括部分平仓）
        self.profitable_trades = 0  # 盈利的交易数
        self.total_pnl = 0.0
        self.max_drawdown = 0.0
        self.peak_value = self.initial_capital
        
        # 数据库会话
        self.db = SessionLocal()
        
        # 配置日志
        if log_file:
            # 添加文件处理器
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
            logging.getLogger().addHandler(file_handler)
        
        logging.info(f"=== 初始化交易模拟器 ===")
        logging.info(f"初始资金: ${self.initial_capital:,.2f}")
        
    def log_portfolio_status(self, signal: Optional[PredictionSignal] = None):
        """记录当前组合状态"""
        try:
            current_price = signal.current_price if signal else (self.position.entry_price if self.position else 0)
            portfolio_value = self.get_portfolio_value(current_price)
            unrealized_pnl = 0.0
            position_cost = 0.0
            position_value = 0.0
            
            logging.info("\n=== 组合状态 ===")
            logging.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"初始资金: ${self.initial_capital:,.2f}")
            logging.info(f"当前现金: ${self.cash:,.2f}")
            
            if self.position:
                position_cost = self.position.size * self.position.entry_price
                position_value = self.position.size * current_price
                unrealized_pnl = self.position.size * (current_price - self.position.entry_price)
                
                logging.info(f"持仓数量: {self.position.size:,.4f}")
                logging.info(f"持仓均价: ${self.position.entry_price:,.2f}")
                logging.info(f"当前市价: ${current_price:,.2f}")
                logging.info(f"持仓成本: ${position_cost:,.2f}")
                logging.info(f"持仓市值: ${position_value:,.2f}")
                logging.info(f"未实现盈亏: ${unrealized_pnl:,.2f}")
            
            total_return_rate = (portfolio_value / self.initial_capital - 1) * 100
            win_rate = (self.profitable_trades / self.closed_trades * 100) if self.closed_trades > 0 else 0
            
            logging.info(f"组合总值: ${portfolio_value:,.2f}")
            logging.info(f"总收益率: {total_return_rate:,.2f}%")
            logging.info(f"最大回撤: {self.max_drawdown:,.2f}%")
            
            if self.closed_trades > 0:
                logging.info(f"已平仓交易: {self.closed_trades}")
                logging.info(f"盈利交易数: {self.profitable_trades}")
                logging.info(f"胜率: {win_rate:,.2f}%")
                logging.info(f"已实现盈亏: ${self.total_pnl:,.2f}")
            
            # 更新最大回撤
            self.peak_value = max(self.peak_value, portfolio_value)
            current_drawdown = (self.peak_value - portfolio_value) / self.peak_value * 100
            self.max_drawdown = max(self.max_drawdown, current_drawdown)
            
            # 保存数据到数据库
            try:
                snapshot = DBTradingSnapshot(
                    initial_capital=self.initial_capital,
                    current_cash=self.cash,
                    position_size=self.position.size if self.position else 0,
                    position_entry_price=self.position.entry_price if self.position else 0,
                    current_price=current_price,
                    position_cost=position_cost,
                    position_value=position_value,
                    unrealized_pnl=unrealized_pnl,
                    portfolio_value=portfolio_value,
                    total_return_rate=total_return_rate,
                    max_drawdown=self.max_drawdown,
                    closed_trades=self.closed_trades,
                    profitable_trades=self.profitable_trades,
                    win_rate=win_rate,
                    realized_pnl=self.total_pnl
                )
                self.db.add(snapshot)
                self.db.commit()
                logging.info("✅ 成功保存交易快照到数据库")
            except Exception as e:
                logging.error(f"保存交易快照时发生错误: {e}")
                self.db.rollback()
            
        except Exception as e:
            logging.error(f"记录组合状态时发生错误: {e}")
            self.db.rollback()
        
        logging.info("================\n")

    def get_current_units(self) -> float:
        """获取当前持仓单位数"""
        if self.position is None:
            return 0.0
        return (self.position.size * self.position.entry_price) / self.unit_size
        
    def calculate_position_adjustment(self, signal: PredictionSignal) -> tuple[str, float]:
        """
        根据信号和当前持仓计算仓位调整
        返回: (操作类型, 调整单位数)
        """
        current_units = self.get_current_units()
        signal_type = signal.signal_type
        
        # 操作映射表
        position_matrix = {
            # 格式: (当前持仓单位, 信号类型): (操作类型, 调整单位数)
            # 空仓情况
            (0, "strong_bullish"): ("buy", 2.0),
            (0, "moderate_bullish"): ("buy", 1.0),
            (0, "weak_bullish"): ("buy", 0.5),
            (0, "neutral"): ("hold", 0),
            (0, "weak_bearish"): ("hold", 0),
            (0, "moderate_bearish"): ("hold", 0),
            (0, "strong_bearish"): ("hold", 0),
            
            # 0.5单位持仓
            (0.5, "strong_bullish"): ("buy", 1.5),
            (0.5, "moderate_bullish"): ("buy", 1.0),
            (0.5, "weak_bullish"): ("buy", 0.5),
            (0.5, "neutral"): ("hold", 0),
            (0.5, "weak_bearish"): ("sell", 0.5),
            (0.5, "moderate_bearish"): ("sell", 0.5),
            (0.5, "strong_bearish"): ("sell", 0.5),
            
            # 1.0单位持仓
            (1.0, "strong_bullish"): ("buy", 1.0),
            (1.0, "moderate_bullish"): ("buy", 0.5),
            (1.0, "weak_bullish"): ("hold", 0),
            (1.0, "neutral"): ("hold", 0),
            (1.0, "weak_bearish"): ("sell", 0.5),
            (1.0, "moderate_bearish"): ("sell", 0.5),
            (1.0, "strong_bearish"): ("sell", 1.0),
            
            # 1.5单位持仓
            (1.5, "strong_bullish"): ("buy", 0.5),
            (1.5, "moderate_bullish"): ("hold", 0),
            (1.5, "weak_bullish"): ("hold", 0),
            (1.5, "neutral"): ("sell", 0.5),
            (1.5, "weak_bearish"): ("sell", 0.5),
            (1.5, "moderate_bearish"): ("sell", 1.0),
            (1.5, "strong_bearish"): ("sell", 1.5),
            
            # 2.0单位持仓
            (2.0, "strong_bullish"): ("hold", 0),
            (2.0, "moderate_bullish"): ("sell", 0.5),
            (2.0, "weak_bullish"): ("sell", 0.5),
            (2.0, "neutral"): ("sell", 1.0),
            (2.0, "weak_bearish"): ("sell", 1.0),
            (2.0, "moderate_bearish"): ("sell", 1.5),
            (2.0, "strong_bearish"): ("sell", 2.0),
        }
        
        # 对于未在映射表中的情况，使用通用规则
        if current_units >= self.max_units:  # 满仓
            if signal_type in ["moderate_bearish", "strong_bearish"]:
                units_to_sell = 2.0 if signal_type == "strong_bearish" else 1.5
                return "sell", units_to_sell
            elif signal_type in ["weak_bearish", "neutral"]:
                return "sell", 1.0
            return "hold", 0
            
        # 查找映射表中的操作
        key = (current_units, signal_type)
        if key in position_matrix:
            return position_matrix[key]
            
        # 对于其他情况，使用基本规则
        if signal_type == "strong_bullish":
            if current_units + 2.0 <= self.max_units:
                return "buy", 2.0
            elif current_units + 1.0 <= self.max_units:
                return "buy", 1.0
        elif signal_type == "moderate_bullish":
            if current_units + 1.0 <= self.max_units:
                return "buy", 1.0
            elif current_units + 0.5 <= self.max_units:
                return "buy", 0.5
        elif signal_type == "weak_bullish":
            if current_units + 0.5 <= self.max_units:
                return "buy", 0.5
        elif signal_type == "weak_bearish":
            if current_units >= 0.5:
                return "sell", 0.5
        elif signal_type == "moderate_bearish":
            if current_units >= 1.0:
                return "sell", 1.0
        elif signal_type == "strong_bearish":
            units_to_sell = min(current_units, 2.0)
            return "sell", units_to_sell
            
        return "hold", 0
        
    def execute_trade(self, signal: PredictionSignal):
        """执行交易"""
        try:
            action, units = self.calculate_position_adjustment(signal)
            
            if action == "hold" or units == 0:
                logging.info(f"信号类型: {signal.signal_type} - 保持现有仓位")
                self.log_portfolio_status(signal)
                return
            
            if action == "buy":
                position_value = units * self.unit_size
                if position_value > self.cash:
                    logging.info(f"信号类型: {signal.signal_type} - 资金不足，无法买入")
                    return
                    
                # 计算可以买入的数量
                shares = position_value / signal.current_price
                
                logging.info(f"\n=== 执行买入交易 ===")
                logging.info(f"信号类型: {signal.signal_type}")
                logging.info(f"买入数量: {shares:,.4f}")
                logging.info(f"买入价格: ${signal.current_price:,.2f}")
                logging.info(f"交易金额: ${position_value:,.2f}")
                
                # 创建新的交易记录
                new_trade = Trade(
                    entry_type="buy",
                    entry_price=signal.current_price,
                    entry_size=shares,
                    remaining_size=shares,
                    entry_time=signal.timestamp
                )
                self.trades.append(new_trade)
                self.open_trades.append(new_trade)
                
                # 保存交易记录到数据库
                try:
                    db_trade = DBTrade(
                        entry_type="buy",
                        entry_price=signal.current_price,
                        entry_size=shares,
                        entry_time=signal.timestamp
                    )
                    self.db.add(db_trade)
                    self.db.commit()
                    logging.info("✅ 成功保存买入交易记录到数据库")
                except Exception as e:
                    logging.error(f"保存买入交易记录时发生错误: {e}")
                    self.db.rollback()
                
                # 更新持仓
                if self.position is None:
                    self.position = Position(
                        size=shares,
                        entry_price=signal.current_price,
                        timestamp=signal.timestamp
                    )
                else:
                    # 更新现有仓位的平均成本
                    total_value = (self.position.size * self.position.entry_price + 
                                 shares * signal.current_price)
                    total_shares = self.position.size + shares
                    self.position = Position(
                        size=total_shares,
                        entry_price=total_value / total_shares,
                        timestamp=signal.timestamp
                    )
                    
                self.cash -= position_value
            
            elif action == "sell":
                if not self.open_trades:
                    return
                    
                position_value = units * self.unit_size
                shares_to_sell = position_value / signal.current_price
                
                if shares_to_sell >= self.position.size:
                    shares_to_sell = self.position.size
                    
                remaining_to_sell = shares_to_sell
                total_pnl = 0.0
                
                # 使用FIFO原则处理平仓
                i = 0
                while i < len(self.open_trades) and remaining_to_sell > 0:
                    trade = self.open_trades[i]
                    # 计算本次要平掉的数量
                    shares_from_this_trade = min(remaining_to_sell, trade.remaining_size)
                    
                    # 计算这部分的盈亏
                    trade_pnl = shares_from_this_trade * (signal.current_price - trade.entry_price)
                    total_pnl += trade_pnl
                    
                    # 更新交易记录
                    if trade.exit_price is None:
                        # 第一次平仓
                        trade.exit_price = signal.current_price
                        trade.exit_size = shares_from_this_trade
                        trade.exit_time = signal.timestamp
                    else:
                        # 已经有部分平仓，更新平均卖出价格
                        total_exit_value = (trade.exit_price * trade.exit_size + 
                                          signal.current_price * shares_from_this_trade)
                        total_exit_size = trade.exit_size + shares_from_this_trade
                        trade.exit_price = total_exit_value / total_exit_size
                        trade.exit_size += shares_from_this_trade
                    
                    trade.remaining_size -= shares_from_this_trade
                    trade.pnl += trade_pnl
                    trade.return_rate = (trade.exit_price - trade.entry_price) / trade.entry_price * 100
                    trade.holding_hours = int((signal.timestamp - trade.entry_time).total_seconds() / 3600)
                    
                    # 如果这笔交易已经完全平仓
                    if trade.remaining_size == 0:
                        trade.is_closed = True
                        self.open_trades.pop(i)
                        self.closed_trades += 1
                        if trade.pnl > 0:
                            self.profitable_trades += 1
                    else:
                        i += 1
                    
                    remaining_to_sell -= shares_from_this_trade
                
                # 更新资金和持仓
                self.cash += shares_to_sell * signal.current_price
                self.total_pnl += total_pnl
                
                logging.info(f"\n=== 执行卖出交易 ===")
                logging.info(f"信号类型: {signal.signal_type}")
                logging.info(f"卖出数量: {shares_to_sell:,.4f}")
                logging.info(f"卖出价格: ${signal.current_price:,.2f}")
                logging.info(f"交易金额: ${shares_to_sell * signal.current_price:,.2f}")
                logging.info(f"交易盈亏: ${total_pnl:,.2f}")
                
                # 更新持仓
                if self.position:
                    remaining_shares = self.position.size - shares_to_sell
                    if remaining_shares > 0:
                        self.position = Position(
                            size=remaining_shares,
                            entry_price=self.position.entry_price,
                            timestamp=signal.timestamp
                        )
                    else:
                        self.position = None
                
                # 更新数据库中的交易记录
                try:
                    db_trade = self.db.query(DBTrade).filter_by(
                        entry_time=trade.entry_time,
                        entry_price=trade.entry_price,
                        entry_size=trade.entry_size
                    ).first()
                    if db_trade:
                        db_trade.exit_price = signal.current_price
                        db_trade.exit_size = shares_from_this_trade
                        db_trade.exit_time = signal.timestamp
                        db_trade.pnl = trade_pnl
                        db_trade.return_rate = (signal.current_price - trade.entry_price) / trade.entry_price * 100
                        db_trade.holding_hours = int((signal.timestamp - trade.entry_time).total_seconds() / 3600)
                        db_trade.is_closed = True
                        self.db.commit()
                        logging.info("✅ 成功更新卖出交易记录到数据库")
                except Exception as e:
                    logging.error(f"更新卖出交易记录时发生错误: {e}")
                    self.db.rollback()
            
            # 更新组合状态
            self.log_portfolio_status(signal)
            
        except Exception as e:
            logging.error(f"执行交易时发生错误: {e}")
            self.db.rollback()

    def get_portfolio_value(self, current_price: float) -> float:
        """获取当前组合价值"""
        position_value = 0 if self.position is None else self.position.size * current_price
        return self.cash + position_value
        
    def save_trade_history(self):
        """保存交易历史"""
        history = []
        for trade in self.trades:
            history.append({
                "entry_type": trade.entry_type,
                "entry_price": trade.entry_price,
                "entry_size": trade.entry_size,
                "entry_time": trade.entry_time.isoformat(),
                "exit_price": trade.exit_price,
                "exit_size": trade.exit_size,
                "exit_time": trade.exit_time.isoformat() if trade.exit_time else None,
                "pnl": trade.pnl,
                "return_rate": trade.return_rate,
                "holding_hours": trade.holding_hours,
                "is_closed": trade.is_closed
            })
            
        with open(self.trade_history_file, "w") as f:
            json.dump(history, f, indent=2)
            
    def print_performance(self):
        """打印性能统计"""
        total_trades = len(self.trades)
        profitable_trades = sum(1 for trade in self.trades if trade.pnl > 0)
        total_pnl = sum(trade.pnl for trade in self.trades)
        
        print(f"\n====== 交易统计 ======")
        print(f"总交易次数: {total_trades}")
        print(f"盈利交易数: {profitable_trades}")
        print(f"胜率: {profitable_trades/total_trades*100:.2f}%" if total_trades > 0 else "暂无交易")
        print(f"总盈亏: ${total_pnl:.2f}")
        print(f"当前资金: ${self.cash:.2f}")
        print("======================")

    def __del__(self):
        """析构函数，确保数据库会话被正确关闭"""
        if hasattr(self, 'db'):
            self.db.close()
