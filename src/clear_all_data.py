from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, TradingSnapshot, Trade

def clear_all_data():
    """清除数据库中的所有数据"""
    # 创建数据库引擎
    engine = create_engine('sqlite:///trading.db')
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        # 删除所有数据
        deleted_snapshots = session.query(TradingSnapshot).delete()
        deleted_trades = session.query(Trade).delete()
        
        session.commit()
        print(f"已删除 {deleted_snapshots} 条快照记录")
        print(f"已删除 {deleted_trades} 条交易记录")
        
    except Exception as e:
        print(f"清理数据时发生错误: {e}")
        session.rollback()
    finally:
        session.close()

if __name__ == "__main__":
    clear_all_data()
