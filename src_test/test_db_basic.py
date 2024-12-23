import sys
import os
import unittest
from datetime import datetime, timedelta

# 添加src目录到Python路径
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from models import Base, TradingSnapshot, Trade
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

class TestDatabaseBasic(unittest.TestCase):
    def setUp(self):
        """测试前的设置"""
        # 创建测试数据库
        self.engine = create_engine('sqlite:///trading_test.db')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
    
    def tearDown(self):
        """测试后的清理"""
        # 删除测试数据库
        if os.path.exists('trading_test.db'):
            os.remove('trading_test.db')
    
    def test_snapshot_crud(self):
        """测试交易快照的增删改查"""
        session = self.Session()
        try:
            # 创建快照
            snapshot = TradingSnapshot(
                timestamp=datetime.now(),
                initial_capital=10000,
                current_cash=9000,
                position_size=0.5,
                position_entry_price=2000,
                current_price=2100,
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
            
            # 添加到数据库
            session.add(snapshot)
            session.commit()
            
            # 读取并验证
            saved = session.query(TradingSnapshot).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.initial_capital, 10000)
            self.assertEqual(saved.current_price, 2100)
            self.assertEqual(saved.position_size, 0.5)
            
            # 修改数据
            saved.current_price = 2200
            session.commit()
            
            # 验证修改
            updated = session.query(TradingSnapshot).first()
            self.assertEqual(updated.current_price, 2200)
            
            # 删除数据
            session.delete(saved)
            session.commit()
            
            # 验证删除
            count = session.query(TradingSnapshot).count()
            self.assertEqual(count, 0)
            
        finally:
            session.close()
    
    def test_trade_crud(self):
        """测试交易记录的增删改查"""
        session = self.Session()
        try:
            # 创建交易记录
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
            
            # 添加到数据库
            session.add(trade)
            session.commit()
            
            # 读取并验证
            saved = session.query(Trade).first()
            self.assertIsNotNone(saved)
            self.assertEqual(saved.entry_price, 2000)
            self.assertEqual(saved.pnl, 50)
            self.assertTrue(saved.is_closed)
            
            # 修改数据
            saved.pnl = 60
            session.commit()
            
            # 验证修改
            updated = session.query(Trade).first()
            self.assertEqual(updated.pnl, 60)
            
            # 删除数据
            session.delete(saved)
            session.commit()
            
            # 验证删除
            count = session.query(Trade).count()
            self.assertEqual(count, 0)
            
        finally:
            session.close()

if __name__ == '__main__':
    unittest.main()
