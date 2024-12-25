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
    timestamp: datetime  # 更新时间
    entry_price: float = 0.0  # 入场价格，仅作参考，实际成本通过open_trades计算

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
            
            # 获取当前持仓信息
            total_shares, weighted_avg_cost = self.get_aggregate_position_info()
            position_cost = total_shares * weighted_avg_cost
            position_value = total_shares * current_price
            unrealized_pnl = total_shares * (current_price - weighted_avg_cost) if total_shares > 0 else 0.0
            
            logging.info("\n=== 组合状态 ===")
            logging.info(f"当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            logging.info(f"初始资金: ${self.initial_capital:,.2f}")
            logging.info(f"当前现金: ${self.cash:,.2f}")
            
            if total_shares > 0:
                logging.info(f"持仓数量: {total_shares:,.4f}")
                logging.info(f"持仓均价: ${weighted_avg_cost:,.2f}")
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
                    position_size=total_shares,
                    position_entry_price=weighted_avg_cost,
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
        """
        计算当前策略持有的"单位"数 = ( 持仓总价值 / unit_size )
        改为基于 open_trades 的加权成本，而不是 position.entry_price
        """
        total_shares, weighted_avg_cost = self.get_aggregate_position_info()
        if total_shares <= 1e-6:
            return 0.0
        total_value = total_shares * weighted_avg_cost
        return total_value / self.unit_size

    def calculate_position_adjustment(self, signal: PredictionSignal) -> tuple[str, float]:
        """
        根据信号和当前持仓计算仓位调整
        """
        signal_target_map = {
            "strong_bullish": 5.0,     # 强看多 -> 满仓
            "moderate_bullish": 2.0,   # 中等看多 -> 1.5个单位
            "weak_bullish": 1.0,       # 弱看多 -> 1个单位
            "neutral": 0.5,            # 中性 -> 0.5个单位
            "weak_bearish": 0.1,       # 弱看空 -> 0.1个单位
            "moderate_bearish": 0.0,   # 中等看空 -> 空仓
            "strong_bearish": 0.0      # 强看空 -> 空仓
        }
        
        signal_type = signal.signal_type
        target_units = signal_target_map.get(signal_type, 0.0)
        target_units = min(target_units, self.max_units)
        
        current_units = self.get_current_units()
        
        # 如果已经 >= 目标，则无需加仓
        threshold = 1e-6
        if current_units >= target_units - threshold:
            return ("hold", 0.0)
        
        # diff
        diff = target_units - current_units
        if abs(diff) < threshold:
            return ("hold", 0.0)
        
        if diff > 0:
            # buy
            # 也可以再限制，不能超过 max_units
            can_add = self.max_units - current_units
            units_to_add = min(diff, can_add)
            return ("buy", units_to_add)
        else:
            # sell
            return ("sell", abs(diff))

        
    def get_aggregate_position_info(self) -> tuple[float, float]:
        """
        通过 self.open_trades 计算当前剩余总仓位和加权平均成本
        return: (total_shares, weighted_avg_cost)
        """
        total_shares = 0.0
        total_cost = 0.0
        for t in self.open_trades:
            if not t.is_closed and t.remaining_size > 0:
                total_shares += t.remaining_size
                total_cost += t.remaining_size * t.entry_price
        if total_shares > 0:
            avg_cost = total_cost / total_shares
            return total_shares, avg_cost
        else:
            return 0.0, 0.0

    def execute_trade(self, signal: PredictionSignal):
        """执行交易"""
        try:
            action, units = self.calculate_position_adjustment(signal)
            
            if action == "hold" or units == 0:
                logging.info(f"信号类型: {signal.signal_type} - 保持现有仓位")
                self.log_portfolio_status(signal)
                return
            
            if action == "buy":
                # 计算理想买入金额
                position_value = units * self.unit_size
                
                # 如果要购买的金额超过当前现金，就用全部现金买
                if position_value > self.cash:
                    position_value = self.cash
                
                # 如果剩下的现金都不足以买 0.01个单位 (可自行调整阈值)
                if position_value < (0.01 * self.unit_size):
                    logging.info(f"现金不足以买到 0.01 单位, 放弃买入")
                    self.log_portfolio_status(signal)
                    return
                
                # 计算可以买入的数量（在标的物层面）
                shares = position_value / signal.current_price
                
                logging.info(f"\n=== 执行买入交易 ===")
                logging.info(f"信号类型: {signal.signal_type}")
                logging.info(f"想买入单位: {units:.2f} (换算交易金额: {units*self.unit_size:.2f})")
                logging.info(f"实际可用资金: ${self.cash:,.2f}")
                logging.info(f"本次实际买入金额: ${position_value:,.2f}")
                logging.info(f"买入数量: {shares:,.4f}")
                logging.info(f"买入价格: ${signal.current_price:,.2f}")
                
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
                
                # 更新持仓信息（仅更新size，不再计算加权成本）
                total_shares, _ = self.get_aggregate_position_info()
                self.position = Position(
                    size=total_shares,
                    timestamp=signal.timestamp
                )
                
                self.cash -= position_value

            elif action == "sell":
                if not self.open_trades:
                    return
                
                position_value = units * self.unit_size
                shares_to_sell = position_value / signal.current_price
                
                # 限制不要超过总剩余持仓
                total_shares, _ = self.get_aggregate_position_info()
                if shares_to_sell > total_shares:
                    shares_to_sell = total_shares
                
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
                        # 已经有部分平仓，更新加权平均卖出价格
                        old_exit_value = trade.exit_price * trade.exit_size
                        new_exit_value = signal.current_price * shares_from_this_trade
                        combined_size = trade.exit_size + shares_from_this_trade
                        
                        trade.exit_price = (old_exit_value + new_exit_value) / combined_size
                        trade.exit_size += shares_from_this_trade
                        trade.exit_time = signal.timestamp
                    
                    trade.remaining_size -= shares_from_this_trade
                    trade.pnl += trade_pnl
                    trade.return_rate = (trade.exit_price - trade.entry_price) / trade.entry_price * 100
                    trade.holding_hours = int((signal.timestamp - trade.entry_time).total_seconds() / 3600)
                    
                    # 只有在完全平仓时才标记为closed
                    if trade.remaining_size == 0:
                        trade.is_closed = True
                        self.open_trades.pop(i)
                        self.closed_trades += 1
                        if trade.pnl > 0:
                            self.profitable_trades += 1
                            
                        # 更新数据库中的交易记录
                        try:
                            db_trade = self.db.query(DBTrade).filter_by(
                                entry_time=trade.entry_time,
                                entry_price=trade.entry_price,
                                entry_size=trade.entry_size
                            ).first()
                            if db_trade:
                                db_trade.exit_price = trade.exit_price
                                db_trade.exit_size = trade.exit_size
                                db_trade.exit_time = trade.exit_time
                                db_trade.pnl = trade.pnl
                                db_trade.return_rate = trade.return_rate
                                db_trade.holding_hours = trade.holding_hours
                                db_trade.is_closed = True
                                self.db.commit()
                                logging.info("✅ 成功更新完全平仓交易记录到数据库")
                        except Exception as e:
                            logging.error(f"更新完全平仓交易记录时发生错误: {e}")
                            self.db.rollback()
                    else:
                        # 部分平仓时只更新相关字段，不标记为closed
                        try:
                            db_trade = self.db.query(DBTrade).filter_by(
                                entry_time=trade.entry_time,
                                entry_price=trade.entry_price,
                                entry_size=trade.entry_size
                            ).first()
                            if db_trade:
                                db_trade.exit_price = trade.exit_price
                                db_trade.exit_size = trade.exit_size
                                db_trade.exit_time = trade.exit_time
                                db_trade.pnl = trade.pnl
                                db_trade.return_rate = trade.return_rate
                                db_trade.holding_hours = trade.holding_hours
                                # 不设置is_closed为True
                                self.db.commit()
                                logging.info("✅ 成功更新部分平仓交易记录到数据库")
                        except Exception as e:
                            logging.error(f"更新部分平仓交易记录时发生错误: {e}")
                            self.db.rollback()
                        i += 1
                    
                    remaining_to_sell -= shares_from_this_trade
                
                # 更新资金
                self.cash += shares_to_sell * signal.current_price
                self.total_pnl += total_pnl
                
                logging.info(f"\n=== 执行卖出交易 ===")
                logging.info(f"信号类型: {signal.signal_type}")
                logging.info(f"卖出数量: {shares_to_sell:,.4f}")
                logging.info(f"卖出价格: ${signal.current_price:,.2f}")
                logging.info(f"交易金额: ${shares_to_sell * signal.current_price:,.2f}")
                logging.info(f"交易盈亏: ${total_pnl:,.2f}")
                
                # 更新持仓信息（仅更新size，不再计算加权成本）
                total_shares, _ = self.get_aggregate_position_info()
                if total_shares > 0:
                    self.position = Position(
                        size=total_shares,
                        timestamp=signal.timestamp
                    )
                else:
                    self.position = None
            
            # 最后更新组合状态
            self.log_portfolio_status(signal)
            
        except Exception as e:
            logging.error(f"执行交易时发生错误: {e}")
            self.db.rollback()

    def get_portfolio_value(self, current_price: float) -> float:
        """获取当前组合价值"""
        total_shares, _ = self.get_aggregate_position_info()
        position_value = total_shares * current_price
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
