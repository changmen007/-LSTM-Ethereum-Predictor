from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class PredictionSignal:
    """预测信号数据类"""
    timestamp: datetime
    current_price: float
    predicted_price: float
    confidence: float
    price_distribution: List[float]
    mean_prediction: float
    std_prediction: float
    
    # 各个区间的概率
    up_prob_within_5: float  # P1: 上涨5%以内概率
    up_prob_5_to_10: float  # P2: 上涨5%-10%概率
    up_prob_above_10: float  # P3: 上涨超过10%概率
    down_prob_within_5: float  # P4: 下跌5%以内概率
    down_prob_5_to_10: float  # P5: 下跌5%-10%概率
    down_prob_above_10: float  # P6: 下跌超过10%概率
    
    @property
    def signal_type(self) -> str:
        """根据概率分布判断信号类型，按优先级顺序进行判断"""
        # 计算总概率
        up_total = self.up_prob_within_5 + self.up_prob_5_to_10 + self.up_prob_above_10
        down_total = self.down_prob_within_5 + self.down_prob_5_to_10 + self.down_prob_above_10
        
        # 计算中高幅度涨跌概率
        up_medium_high = self.up_prob_5_to_10 + self.up_prob_above_10
        down_medium_high = self.down_prob_5_to_10 + self.down_prob_above_10
        
        # 1. 强看涨
        if (up_total >= 0.75 and 
            up_medium_high >= 0.35):
            return "strong_bullish"
            
        # 2. 中性看涨
        if (up_total >= 0.65 and 
            up_medium_high >= 0.20):
            return "moderate_bullish"
            
        # 3. 弱看涨
        if up_total >= 0.55:
            return "weak_bullish"
            
        # 4. 强看跌
        if (down_total >= 0.75 and 
            down_medium_high >= 0.35):
            return "strong_bearish"
            
        # 5. 中性看跌
        if (down_total >= 0.65 and 
            down_medium_high >= 0.20):
            return "moderate_bearish"
            
        # 6. 弱看跌
        if down_total >= 0.55:
            return "weak_bearish"
            
        # 7. 中性信号（其他所有情况）
        return "neutral"
    
    decision: str  # 'buy', 'sell', 'hold'

class SignalProvider:
    """交易信号提供者接口"""
    def __init__(self, predictor):
        self.predictor = predictor
        
    def get_latest_signal(self) -> Optional[PredictionSignal]:
        """获取最新的交易信号"""
        # 从predictor获取预测结果
        result = self.predictor.make_predictions()
        if result[0] is None:  # 如果预测失败
            return None
            
        current_price, last_close, distribution, predictions, current_time, next_time, avg_prediction = result
        
        # 使用分布字典中的值计算概率
        total_predictions = sum(distribution.values())
        up_within_5 = distribution.get('涨幅5%以内', 0)
        up_5_to_10 = distribution.get('涨幅5%~10%', 0)
        up_above_10 = distribution.get('涨幅超过10%', 0)
        down_within_5 = distribution.get('跌幅5%以内', 0)
        down_5_to_10 = distribution.get('跌幅5%~10%', 0)
        down_above_10 = distribution.get('跌幅超过10%', 0)
        
        # 计算置信度
        confidence = 0.8 if abs((avg_prediction - current_price) / current_price) > 0.05 else 0.6
        
        # 生成决策
        decision = "buy" if avg_prediction > current_price else "sell"
        
        return PredictionSignal(
            timestamp=current_time,
            current_price=current_price,
            predicted_price=avg_prediction,
            confidence=confidence,
            price_distribution=predictions,
            mean_prediction=avg_prediction,
            std_prediction=0.0,  # 暂时不计算标准差
            up_prob_within_5=up_within_5 / total_predictions,
            up_prob_5_to_10=up_5_to_10 / total_predictions,
            up_prob_above_10=up_above_10 / total_predictions,
            down_prob_within_5=down_within_5 / total_predictions,
            down_prob_5_to_10=down_5_to_10 / total_predictions,
            down_prob_above_10=down_above_10 / total_predictions,
            decision=decision
        )
