import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from typing import Dict, List, Tuple
import talib
from datetime import datetime
import os
from sklearn.preprocessing import MinMaxScaler

def prepare_model_input(eth_df: pd.DataFrame, btc_df: pd.DataFrame, sequence_length: int = 24) -> Tuple[np.ndarray, float, MinMaxScaler]:
    """
    准备模型输入数据，确保与训练时的特征完全一致
    特征顺序：timestamp,open,high,low,close,volume,MA7,MA10,MA20,MA30,MA60,MACD,MACD_signal,MACD_hist,RSI,K,D,J,ATR,
             Momentum,ETH_BTC_price_diff,ETH_BTC_price_ratio,ETH_MA7,ETH_MA25,BTC_MA7,BTC_MA25,ETH_volume_change,BTC_volume_change
    """
    print("\n开始准备模型输入数据...")
    
    # 1. 创建基础DataFrame
    print("正在计算基础特征...")
    df = pd.DataFrame(index=eth_df.index)
    
    # 基础价格数据
    df['open'] = eth_df['open']
    df['high'] = eth_df['high']
    df['low'] = eth_df['low']
    df['close'] = eth_df['close']
    df['volume'] = eth_df['volume']
    
    # 2. 计算移动平均线
    print("正在计算移动平均线...")
    df['MA7'] = eth_df['close'].rolling(window=7).mean()
    df['MA10'] = eth_df['close'].rolling(window=10).mean()
    df['MA20'] = eth_df['close'].rolling(window=20).mean()
    df['MA30'] = eth_df['close'].rolling(window=30).mean()
    df['MA60'] = eth_df['close'].rolling(window=60).mean()
    
    # 3. 计算MACD
    print("正在计算MACD...")
    macd, macd_signal, macd_hist = talib.MACD(eth_df['close'].values)
    df['MACD'] = macd
    df['MACD_signal'] = macd_signal
    df['MACD_hist'] = macd_hist
    
    # 4. 计算RSI
    print("正在计算RSI...")
    df['RSI'] = talib.RSI(eth_df['close'].values, timeperiod=14)
    
    # 5. 计算KDJ
    print("正在计算KDJ...")
    high_prices = eth_df['high']
    low_prices = eth_df['low']
    close_prices = eth_df['close']
    df['K'], df['D'] = talib.STOCH(high_prices, low_prices, close_prices, 
                                  fastk_period=9, slowk_period=3, slowk_matype=0, 
                                  slowd_period=3, slowd_matype=0)
    df['J'] = 3 * df['K'] - 2 * df['D']
    
    # 6. 计算ATR和Momentum
    print("正在计算ATR和Momentum...")
    df['ATR'] = talib.ATR(eth_df['high'].values, eth_df['low'].values, eth_df['close'].values, timeperiod=14)
    df['Momentum'] = talib.MOM(eth_df['close'].values, timeperiod=10)
    
    # 6.1 计算布林带
    print("正在计算布林带...")
    df['BB_upper'], df['BB_middle'], df['BB_lower'] = talib.BBANDS(
        eth_df['close'].values, 
        timeperiod=20,
        nbdevup=2,
        nbdevdn=2,
        matype=0
    )
    
    # 6.2 计算其他技术指标
    print("正在计算其他技术指标...")
    df['ADX'] = talib.ADX(eth_df['high'].values, eth_df['low'].values, eth_df['close'].values, timeperiod=14)
    df['CCI'] = talib.CCI(eth_df['high'].values, eth_df['low'].values, eth_df['close'].values, timeperiod=14)
    df['OBV'] = talib.OBV(eth_df['close'].values, eth_df['volume'].values)
    df['STDDEV'] = talib.STDDEV(eth_df['close'].values, timeperiod=14)
    
    # 7. ETH和BTC的关系特征
    print("正在计算ETH和BTC关系特征...")
    df['ETH_BTC_price_diff'] = eth_df['close'] - btc_df['close']
    df['ETH_BTC_price_ratio'] = eth_df['close'] / btc_df['close'].replace(0, np.nan)
    
    # 8. ETH和BTC的MA
    df['ETH_MA7'] = eth_df['close'].rolling(window=7).mean()
    df['ETH_MA25'] = eth_df['close'].rolling(window=25).mean()
    df['BTC_MA7'] = btc_df['close'].rolling(window=7).mean()
    df['BTC_MA25'] = btc_df['close'].rolling(window=25).mean()
    
    # 9. 成交量变化
    df['ETH_volume_change'] = eth_df['volume'].pct_change().replace([np.inf, -np.inf], np.nan)
    df['BTC_volume_change'] = btc_df['volume'].pct_change().replace([np.inf, -np.inf], np.nan)
    
    # 10. 数据清理和归一化
    print("正在进行数据清理和归一化...")
    # 替换无穷值为NaN
    df = df.replace([np.inf, -np.inf], np.nan)
    # 使用前向填充方法填充NaN值
    df = df.ffill()
    # 使用后向填充方法填充剩余的NaN值
    df = df.bfill()
    
    # 确保列的顺序与训练时一致
    expected_columns = ['open', 'high', 'low', 'close', 'volume', 
                       'MA7', 'MA10', 'MA20', 'MA30', 'MA60',
                       'MACD', 'MACD_signal', 'MACD_hist', 'RSI',
                       'K', 'D', 'J', 'ATR', 'Momentum',
                       'BB_upper', 'BB_middle', 'BB_lower',
                       'ADX', 'CCI', 'OBV', 'STDDEV',
                       'ETH_BTC_price_diff', 'ETH_BTC_price_ratio',
                       'ETH_MA7', 'ETH_MA25', 'BTC_MA7', 'BTC_MA25',
                       'ETH_volume_change', 'BTC_volume_change']
    
    df = df[expected_columns]
    print(f"特征列: {', '.join(df.columns)}")
    
    # 归一化
    scaler = MinMaxScaler()
    df_scaled = pd.DataFrame(scaler.fit_transform(df), columns=df.columns, index=df.index)
    
    # 11. 准备序列数据
    print("正在准备序列数据...")
    current_price = float(eth_df['close'].iloc[-1])
    data = df_scaled.values
    X = data[-sequence_length:].reshape(1, sequence_length, len(expected_columns))
    
    print(f"数据准备完成，输入特征维度: {X.shape}")
    return X, current_price, scaler

def calculate_distribution(predictions: List[float], current_price: float) -> Dict[str, float]:
    """计算预测分布"""
    # 计算价格变化的百分比
    changes = [(pred - current_price) / current_price * 100 for pred in predictions]
    distribution = {
        '涨幅5%以内': 0,
        '涨幅5%~10%': 0,
        '涨幅10%以上': 0,
        '跌幅5%以内': 0,
        '跌幅5%~10%': 0,
        '跌幅10%以上': 0
    }
    
    # 计算每个区间的预测次数
    for change in changes:
        if change > 0:
            if change <= 5:
                distribution['涨幅5%以内'] += 1
            elif change <= 10:
                distribution['涨幅5%~10%'] += 1
            else:
                distribution['涨幅10%以上'] += 1
        else:
            if change >= -5:
                distribution['跌幅5%以内'] += 1
            elif change >= -10:
                distribution['跌幅5%~10%'] += 1
            else:
                distribution['跌幅10%以上'] += 1
    
    # 不再转换为百分比，保持原始次数
    return distribution

def plot_distribution(predictions: List[float], current_price: float, save_path: str):
    """绘制预测分布图"""
    # 设置中文字体
    plt.rcParams['font.sans-serif'] = ['Arial Unicode MS']  # macOS的中文字体
    plt.rcParams['axes.unicode_minus'] = False  # 用来正常显示负号
    
    changes = [(pred - current_price) / current_price * 100 for pred in predictions]
    
    plt.figure(figsize=(12, 6))
    plt.hist(changes, bins=50, color='blue', alpha=0.7)
    plt.axvline(x=0, color='red', linestyle='--', label='当前价格')
    plt.title('ETH价格预测分布图')
    plt.xlabel('价格变化百分比 (%)')
    plt.ylabel('预测次数')
    plt.legend()
    plt.grid(True, alpha=0.3)
    
    # 添加统计信息
    stats_text = (
        f'当前价格: {current_price:.2f}\n'
        f'预测次数: {len(predictions)}\n'
        f'波动标准差: {np.std(changes):.2f}%'
    )
    plt.text(0.02, 0.95, stats_text, 
             transform=plt.gca().transAxes, 
             bbox=dict(facecolor='white', alpha=0.8))
    
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    plt.close()

def update_log(log_file: str, timestamp: datetime, current_price: float, 
               distribution: Dict[str, float], prediction: str, 
               avg_prediction: float, last_result: str = None, 
               cumulative_accuracy: float = None):
    """更新预测日志"""
    # 确保日志目录存在
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    
    # 准备新的记录
    new_record = {
        '预测时间': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
        '当前价格': current_price,
        '预测': prediction,
        '上次结果': last_result if last_result else '',
        '累计胜率': f"{cumulative_accuracy:.2f}%" if cumulative_accuracy is not None else '',
    }
    
    # 添加分布信息
    for category, value in distribution.items():
        new_record[category] = value
        
    # 添加平均预测价格和预测结果
    new_record['平均预测价格'] = avg_prediction
    new_record['预测结果'] = prediction
    new_record['上次预测评估'] = last_result if last_result else ''
    
    # 将新记录添加到CSV文件
    df = pd.DataFrame([new_record])
    header = not os.path.exists(log_file) or os.path.getsize(log_file) == 0
    df.to_csv(log_file, mode='a', header=header, index=False)

def get_prediction_decision(avg_prediction: float, last_close: float) -> str:
    """
    根据预测价格与最近整点收盘价比较决定是否买入
    :param avg_prediction: 预测的下一个整点收盘价
    :param last_close: 最近一次的整点收盘价
    :return: "买入"或"不买入"
    """
    return "买入" if avg_prediction > last_close else "不买入"

def evaluate_prediction(prediction: str, next_close: float, last_close: float) -> str:
    """
    评估预测结果
    :param prediction: 预测结果（"买入"或"不买入"）
    :param next_close: 实际的下一个整点收盘价
    :param last_close: 预测时的最近整点收盘价
    :return: "胜"或"负"
    """
    actual_higher = next_close > last_close
    predicted_higher = prediction == "买入"
    return "胜" if actual_higher == predicted_higher else "负"
