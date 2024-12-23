import time
import os
from datetime import datetime, timedelta
from predictor import ETHPredictor
from simulator import TradingSimulator
from trading_signals import SignalProvider

def initialize_session():
    """初始化新的交易会话"""
    # 创建新的会话目录
    session_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_dir = f"/Users/changmen/Downloads/ETH 价格预测系统/log/session_{session_time}"
    os.makedirs(log_dir, exist_ok=True)
    
    # 设置日志文件路径
    log_files = {
        "prediction_log": os.path.join(log_dir, "prediction_log.csv"),
        "trade_history": os.path.join(log_dir, "trade_history.json"),
        "trading_log": os.path.join(log_dir, "trading_simulator.log"),
        "distribution_plot": os.path.join(log_dir, "latest_distribution.png")
    }
    
    print(f"\n=== 新交易会话启动 ===")
    print(f"会话ID: {session_time}")
    print(f"日志目录: {log_dir}")
    print("===================\n")
    
    return log_files

def wait_until_next_hour():
    """等待到下一个整点"""
    current_time = datetime.now()
    # 计算距离下一个整点的秒数
    seconds_until_next_hour = 3600 - (current_time.minute * 60 + current_time.second)
    if seconds_until_next_hour > 0:
        print(f"等待到下一个整点 {(current_time.replace(minute=0, second=0) + timedelta(hours=1)).strftime('%Y-%m-%d %H:00:00')}")
        time.sleep(seconds_until_next_hour)

def main():
    # 初始化新的会话
    log_files = initialize_session()
    
    # 初始化预测器和模拟器
    predictor = ETHPredictor(
        log_path=log_files["prediction_log"],
        plot_path=log_files["distribution_plot"]
    )
    signal_provider = SignalProvider(predictor)
    simulator = TradingSimulator(
        trade_history_file=log_files["trade_history"],
        log_file=log_files["trading_log"]
    )
    
    print("开始运行交易模拟...")
    print(f"详细日志将被记录到 {log_files['trading_log']}")
    
    try:
        while True:
            # 等待到下一个整点
            wait_until_next_hour()
            
            # 获取当前时间
            current_time = datetime.now()
            print(f"\n当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 获取最新信号
            signal = signal_provider.get_latest_signal()
            if signal:
                # 执行模拟交易
                simulator.execute_trade(signal)
            
    except KeyboardInterrupt:
        print("\n程序已停止")
        # 保存交易历史
        simulator.save_trade_history()
        print(f"交易历史已保存到 {simulator.trade_history_file}")

if __name__ == "__main__":
    main()
