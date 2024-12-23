from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, TradingSnapshot, Trade

def clean_test_data(hours_ago=24):
    """清除指定时间之前的数据"""
    # 创建数据库引擎
    engine = create_engine('sqlite:///trading.db')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 计算时间阈值
        threshold = datetime.now() - timedelta(hours=hours_ago)
        
        # 删除旧数据
        deleted_snapshots = session.query(TradingSnapshot).filter(
            TradingSnapshot.timestamp < threshold
        ).delete()
        
        deleted_trades = session.query(Trade).filter(
            Trade.entry_time < threshold
        ).delete()
        
        session.commit()
        print(f"已删除 {deleted_snapshots} 条快照记录")
        print(f"已删除 {deleted_trades} 条交易记录")
        
    except Exception as e:
        print(f"清理数据时发生错误: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    clean_test_data()
