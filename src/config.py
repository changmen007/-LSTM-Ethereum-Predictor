from typing import Dict, Any
from pathlib import Path

class Config:
    # 数据库配置
    DATABASE_URL = 'sqlite:///trading.db'
    CHECK_SAME_THREAD = False
    
    # 交易模拟器配置
    INITIAL_CAPITAL = 20_000.0
    UNIT_SIZE = 2_500.0  # 每个交易单位的大小
    MAX_UNITS = 5.0      # 最大交易单位数
    
    # 文件路径配置
    BASE_DIR = Path(__file__).parent.parent
    LOG_DIR = BASE_DIR / 'log'
    MODELS_DIR = BASE_DIR / 'models'
    
    # 交易相关的时间配置
    TRADING_DATA_HOURS = 24  # 获取交易数据的小时数
    TRADING_DATA_LIMIT = 100  # 简化版交易数据的限制数量
    
    # API配置
    CORS_ORIGINS = ["*"]
    CORS_CREDENTIALS = True
    CORS_METHODS = ["*"]
    CORS_HEADERS = ["*"]
    
    @classmethod
    def get_model_config(cls) -> Dict[str, Any]:
        """获取模型相关的配置"""
        return {
            "model_path": str(cls.MODELS_DIR / "model.pkl"),
            "model_params": {
                # 在这里添加模型相关的参数
                "input_size": 10,
                "output_size": 1,
                "hidden_size": 64
            }
        }
    
    @classmethod
    def get_trading_config(cls) -> Dict[str, Any]:
        """获取交易相关的配置"""
        return {
            "initial_capital": cls.INITIAL_CAPITAL,
            "unit_size": cls.UNIT_SIZE,
            "max_units": cls.MAX_UNITS,
        }
    
    @classmethod
    def setup_paths(cls) -> None:
        """确保所有必要的目录都存在"""
        cls.LOG_DIR.mkdir(exist_ok=True)
        cls.MODELS_DIR.mkdir(exist_ok=True)
