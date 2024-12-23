import os
import sys
import time
import numpy as np
import tensorflow as tf
from datetime import datetime, timedelta
from data_fetcher import DataFetcher
import utils
from utils import (prepare_model_input, calculate_distribution, 
                  plot_distribution, update_log, get_prediction_decision,
                  evaluate_prediction)
import pandas as pd

class ETHPredictor:
    def __init__(self, log_path=None, plot_path=None):
        # 获取项目根目录（简单交易策略目录）
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        
        # 设置路径
        self.model_path = os.path.join(project_root, '/Users/changmen/Downloads/ETH 价格预测系统/models/eth_price_predictor_1h_v8.keras')
        self.log_path = log_path or os.path.join(project_root, '/Users/changmen/Downloads/ETH 价格预测系统/log/prediction_log.csv')
        self.plot_path = plot_path or os.path.join(project_root, '/Users/changmen/Downloads/ETH 价格预测系统/log/latest_distribution.png')
        
        self.data_fetcher = DataFetcher()
        self.predictions_count = 200
        self.wins = 0
        self.total_predictions = 0
        
        # 创建必要的目录
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        
        # 加载模型
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"模型文件未找到: {self.model_path}")
        self.model = tf.keras.models.load_model(self.model_path)
        
        # 初始化上次的预测结果
        self.last_prediction = None
        self.last_price = None
        self.last_close = None
    
    def make_predictions(self) -> tuple:
        """进行预测"""
        print("\n开始获取数据...")
        eth_df, btc_df = self.data_fetcher.get_latest_data()
        if eth_df is None or btc_df is None:
            print("获取数据失败")
            return None, None, None, None, None, None, None
            
        print(f"成功获取数据，ETH数据{len(eth_df)}条，BTC数据{len(btc_df)}条")
        
        # 准备模型输入
        print("\n准备模型输入...")
        model_input, current_price, scaler = prepare_model_input(eth_df, btc_df)
        X = model_input
        
        # 获取当前价格和上一次收盘价
        current_close = current_price
        last_close = eth_df.iloc[-2]['close']
        current_time = eth_df.index[-1]
        last_time = eth_df.index[-2]
        next_time = current_time + timedelta(hours=1)  # 预测下一个1小时收盘价
        
        print(f"\n时间信息:")
        print(f"上一次收盘价时间: {last_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"当前收盘价时间: {current_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"预测目标时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"\n价格信息:")
        print(f"上一次收盘价: {last_close:.2f}")
        print(f"当前收盘价: {current_close:.2f}")
        
        # 进行多次预测
        print(f"\n开始进行 {self.predictions_count} 次预测...")
        predictions = []
        scaled_close_idx = 3  # 'close' 在特征列表中的索引位置
        
        # 设置噪声参数
        noise_std = 0.01  # 输入噪声标准差
        price_volatility = current_close * 0.02  # 价格波动率（当前价格的2%）
        
        for i in range(self.predictions_count):
            # 添加输入噪声
            noise = np.random.normal(0, noise_std, X.shape)
            noisy_X = X + noise
            
            # 预测
            pred = self.model.predict(noisy_X, verbose=0)
            
            # 创建一个完整的特征向量，只填充close价格位置
            dummy_row = np.zeros((1, X.shape[2]))
            dummy_row[0, scaled_close_idx] = pred[0][0]
            
            # 反向转换预测值
            pred_price = scaler.inverse_transform(dummy_row)[0][scaled_close_idx]
            
            # 添加价格随机波动
            random_change = np.random.normal(0, price_volatility)
            pred_price += random_change
            
            predictions.append(pred_price)
            if (i + 1) % 50 == 0:
                print(f"已完成 {i + 1} 次预测")
        
        # 计算平均预测价格
        avg_prediction = sum(predictions) / len(predictions)
        print(f"\n预测统计:")
        print(f"平均预测价格: {avg_prediction:.2f}")
        print(f"预期变化: {((avg_prediction - current_close) / current_close * 100):.2f}%")
        
        # 统计分布
        distribution = calculate_distribution(predictions, current_close)
        
        # 打印分布
        print("\n预测分布:")
        for k, v in distribution.items():
            print(f"{k}: {v:.0f}次 ({v/len(predictions)*100:.1f}%)")
        
        print("\n正在生成分布图...")
        plot_distribution(predictions, current_close, self.plot_path)
        
        return current_close, last_close, distribution, predictions, current_time, next_time, avg_prediction
    
    def evaluate_last_prediction(self, current_close, last_close):
        """评估上次预测结果"""
        if self.last_prediction and self.last_price:
            result = evaluate_prediction(
                self.last_prediction, 
                current_close, 
                self.last_price  # 使用上次预测时的价格作为基准
            )
            if result == "胜":
                self.wins += 1
            self.total_predictions += 1
            return result
        return None
    
    def run(self):
        """运行预测循环"""
        print("ETH 价格预测系统启动...")
        
        # 如果日志文件存在，加载历史预测记录
        if os.path.exists(self.log_path):
            try:
                log_df = pd.read_csv(self.log_path)
                if not log_df.empty:
                    # 计算历史胜率
                    wins = len(log_df[log_df['上次预测评估'] == '胜'])
                    total = len(log_df[log_df['上次预测评估'].notna()])
                    if total > 0:
                        self.wins = wins
                        self.total_predictions = total
                        print(f"加载历史预测记录: 胜率 {(wins/total*100):.2f}% ({wins}/{total})")
                    
                    # 获取最后一次预测
                    last_row = log_df.iloc[-1]
                    self.last_prediction = last_row['预测结果']
                    self.last_price = last_row['当前价格']
            except Exception as e:
                print(f"加载历史记录时出错: {e}")
                print("将使用新的记录开始...")
        
        while True:
            try:
                # 获取当前时间
                now = datetime.now()
                
                # 进行预测
                current_close, last_close, distribution, predictions, current_time, next_time, avg_prediction = self.make_predictions()
                
                # 做出预测决定
                prediction = utils.get_prediction_decision(avg_prediction, last_close)
                
                # 评估上次预测
                last_result = self.evaluate_last_prediction(current_close, last_close)
                
                # 计算累计胜率
                accuracy = (self.wins / self.total_predictions * 100 
                          if self.total_predictions > 0 else None)
                
                # 更新日志
                update_log(
                    self.log_path,
                    now,
                    current_close,
                    distribution,
                    prediction,
                    avg_prediction,
                    last_result,
                    accuracy if self.total_predictions > 0 else None
                )
                
                # 打印预测信息
                print(f"\n预测逻辑:")
                print(f"预测下一个整点({next_time.strftime('%H:00')})收盘价为: {avg_prediction:.2f}")
                print(f"最近的整点收盘价为: {last_close:.2f}")
                print(f"因为 {avg_prediction:.2f} {'>' if avg_prediction > last_close else '<'} {last_close:.2f}")
                print(f"所以决定：{'买入' if avg_prediction > last_close else '不买入'}")                
                print(f"\n预测时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
                if self.total_predictions > 0:
                    print(f"累计胜率: {accuracy:.2f}% ({self.wins}/{self.total_predictions})")
                
                # 保存本次预测信息
                self.last_prediction = prediction
                self.last_price = current_close
                self.last_close = last_close
                
                # 等待到下一个1小时周期
                current_period = now.minute // 60
                next_period_hour = now.hour
                next_period_minute = 0
                
                next_time = now.replace(minute=next_period_minute, second=0, microsecond=0)
                if next_period_hour >= 23:
                    # 如果下一个周期超过今天，转到明天凌晨
                    next_time = next_time.replace(day=next_time.day + 1, hour=0)
                else:
                    next_time = next_time.replace(hour=next_period_hour + 1)
                
                sleep_seconds = (next_time - now).total_seconds()
                print(f"\n等待下一次预测... ({sleep_seconds:.0f}秒)")
                print(f"下次预测时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
                time.sleep(sleep_seconds)
                
            except Exception as e:
                print(f"发生错误: {e}")
                print("5分钟后重试...")
                time.sleep(300)

if __name__ == "__main__":
    predictor = ETHPredictor()
    predictor.run()
