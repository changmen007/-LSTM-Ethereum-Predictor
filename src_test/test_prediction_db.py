import sys
import os
import unittest
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from predictor import ETHPredictor
from models import Base, TradingSnapshot, Trade
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TestPredictionDB(unittest.TestCase):
    def setUp(self):
        """测试前的设置"""
        # 创建测试数据库
        self.engine = create_engine('sqlite:///trading_test.db')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        
        # 创建预测器实例
        self.predictor = ETHPredictor()
        
        # 生成一些模拟的历史数据
        dates = pd.date_range(end=datetime.now(), periods=100, freq='1H')
        self.test_data = pd.DataFrame({
            'timestamp': dates,
            'close': np.random.normal(2000, 100, 100),  # 模拟ETH价格
            'volume': np.random.normal(1000, 100, 100)  # 模拟交易量
        })
    
    def tearDown(self):
        """测试后的清理"""
        # 删除测试数据库
        os.remove('trading_test.db')
    
    def test_prediction_to_db(self):
        """测试预测结果是否正确写入数据库"""
        # 1. 进行预测
        prediction = self.predictor.make_predictions(self.test_data)
        self.assertIsNotNone(prediction, "预测结果不应为空")
        
        # 2. 写入测试数据到数据库
        session = self.Session()
        try:
            # 创建一个交易快照
            snapshot = TradingSnapshot(
                timestamp=datetime.now(),
                initial_capital=10000,
                current_cash=9000,
                position_size=0.5,
                position_entry_price=2000,
                current_price=prediction,  # 使用预测价格
                position_cost=1000,
                position_value=1100,
                unrealized_pnl=100,
                portfolio_value=10100,
                total_return_rate=1.0,
                max_drawdown=-5.0,
                closed_trades=1,
                profitable_trades=1,
                win_rate=100.0,
                realized_pnl=100
            )
            session.add(snapshot)
            session.commit()
            
            # 3. 验证数据是否正确写入
            saved_snapshot = session.query(TradingSnapshot).order_by(
                TradingSnapshot.timestamp.desc()
            ).first()
            
            self.assertIsNotNone(saved_snapshot, "数据库中应该有保存的快照")
            self.assertEqual(saved_snapshot.current_price, prediction, 
                           "保存的预测价格应该与原始预测相同")
            
            # 4. 测试数据读取
            snapshots = session.query(TradingSnapshot).all()
            self.assertGreater(len(snapshots), 0, "应该能够读取到快照数据")
            
        finally:
            session.close()
    
    def test_multiple_predictions(self):
        """测试连续多次预测和数据库写入"""
        session = self.Session()
        try:
            # 连续进行多次预测并写入
            for _ in range(5):
                prediction = self.predictor.make_predictions(self.test_data)
                
                snapshot = TradingSnapshot(
                    timestamp=datetime.now(),
                    initial_capital=10000,
                    current_cash=9000,
                    position_size=0.5,
                    position_entry_price=2000,
                    current_price=prediction,
                    position_cost=1000,
                    position_value=1100,
                    unrealized_pnl=100,
                    portfolio_value=10100,
                    total_return_rate=1.0,
                    max_drawdown=-5.0,
                    closed_trades=1,
                    profitable_trades=1,
                    win_rate=100.0,
                    realized_pnl=100
                )
                session.add(snapshot)
                session.commit()
            
            # 验证是否所有数据都正确写入
            snapshots = session.query(TradingSnapshot).all()
            self.assertEqual(len(snapshots), 5, "应该有5条预测记录")
            
            # 验证时间戳是否按顺序排列
            timestamps = [s.timestamp for s in snapshots]
            self.assertEqual(timestamps, sorted(timestamps), 
                           "时间戳应该是按顺序的")
            
        finally:
            session.close()
    
    def test_trade_recording(self):
        """测试交易记录的写入和读取"""
        session = self.Session()
        try:
            # 记录一笔交易
            trade = Trade(
                entry_type='buy',
                entry_price=2000,
                entry_size=0.5,
                entry_time=datetime.now(),
                exit_price=2100,
                exit_size=0.5,
                exit_time=datetime.now() + timedelta(hours=1),
                pnl=50,
                return_rate=2.5,
                holding_hours=1,
                is_closed=True
            )
            session.add(trade)
            session.commit()
            
            # 验证交易记录
            saved_trade = session.query(Trade).first()
            self.assertIsNotNone(saved_trade, "应该能找到保存的交易记录")
            self.assertEqual(saved_trade.pnl, 50, "PnL应该正确保存")
            self.assertTrue(saved_trade.is_closed, "交易状态应该正确保存")
            
        finally:
            session.close()

if __name__ == '__main__':
    unittest.main()
