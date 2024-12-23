import requests
import datetime
import pandas as pd
import numpy as np
from typing import Tuple, List
import time

class DataFetcher:
    def __init__(self, interval: str = "1h", lookback_days: int = 30):
        """
        初始化数据获取器
        :param interval: K线间隔，默认4小时
        :param lookback_days: 回溯天数，默认30天
        """
        self.base_url = "https://api.binance.com/api/v3/klines"
        self.interval = interval
        self.lookback_days = lookback_days
        self.max_retries = 5
        self.retry_delay = 10  # 重试延迟秒数
        
    def _get_time_range(self) -> Tuple[int, int]:
        """获取时间范围的时间戳"""
        end_date = datetime.datetime.now(datetime.timezone.utc)
        start_date = end_date - datetime.timedelta(days=self.lookback_days)
        return (int(start_date.timestamp() * 1000), 
                int(end_date.timestamp() * 1000))
    
    def _fetch_kline_data(self, symbol: str) -> List:
        """获取K线数据"""
        start_time, end_time = self._get_time_range()
        params = {
            "symbol": symbol,
            "interval": self.interval,
            "startTime": start_time,
            "endTime": end_time,
            "limit": 1000
        }
        
        kline_data = []
        retry_count = 0
        
        while retry_count < self.max_retries:
            try:
                # 添加请求头
                headers = {
                    'User-Agent': 'Mozilla/5.0',
                    'Accept': 'application/json',
                }
                
                response = requests.get(
                    self.base_url, 
                    params=params,
                    headers=headers,
                    timeout=30  # 设置超时时间
                )
                
                if response.status_code == 200:
                    data = response.json()
                    kline_data.extend(data)
                    if len(data) < 1000:
                        break
                    params["startTime"] = data[-1][0] + 1
                elif response.status_code == 429:  # Rate limit
                    retry_delay = int(response.headers.get('Retry-After', self.retry_delay))
                    print(f"达到速率限制，等待 {retry_delay} 秒...")
                    time.sleep(retry_delay)
                    continue
                else:
                    print(f"请求失败，状态码: {response.status_code}")
                    time.sleep(self.retry_delay)
                    retry_count += 1
            except Exception as e:
                print(f"请求异常: {str(e)}")
                time.sleep(self.retry_delay)
                retry_count += 1
                continue
                
        if not kline_data and retry_count >= self.max_retries:
            raise Exception("获取数据失败，已达到最大重试次数")
            
        return kline_data
    
    def _process_kline_data(self, kline_data: List) -> pd.DataFrame:
        """处理K线数据"""
        df = pd.DataFrame(kline_data, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume',
            'close_time', 'quote_volume', 'trades_count',
            'taker_buy_volume', 'taker_buy_quote_volume', 'ignore'
        ])
        
        # 转换数据类型
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = df[col].astype(float)
            
        # 设置时间索引
        df.set_index('timestamp', inplace=True)
        
        # 只保留需要的列
        return df[['open', 'high', 'low', 'close', 'volume']]
    
    def get_latest_data(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        获取ETH和BTC的最新数据
        :return: (eth_df, btc_df)
        """
        print("\n开始获取最新市场数据...")
        
        # 获取ETH数据
        print("正在获取ETH数据...")
        eth_data = self._fetch_kline_data("ETHUSDT")
        eth_df = self._process_kline_data(eth_data)
        print(f"已获取ETH数据，共 {len(eth_df)} 条记录")
        
        # 获取BTC数据
        print("正在获取BTC数据...")
        btc_data = self._fetch_kline_data("BTCUSDT")
        btc_df = self._process_kline_data(btc_data)
        print(f"已获取BTC数据，共 {len(btc_df)} 条记录")
        
        return eth_df, btc_df
    
    def get_last_close(self) -> Tuple[float, float]:
        """
        获取最新收盘价
        :return: (eth_price, btc_price)
        """
        eth_df, btc_df = self.get_latest_data()
        return float(eth_df['close'].iloc[-1]), float(btc_df['close'].iloc[-1])

if __name__ == "__main__":
    # 测试代码
    fetcher = DataFetcher()
    eth_df, btc_df = fetcher.get_latest_data()
    print("ETH数据示例:")
    print(eth_df.tail())
    print("\nBTC数据示例:")
    print(btc_df.tail())
