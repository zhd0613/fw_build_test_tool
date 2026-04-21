# 配置文件
# 功能：
# 1. 存储项目的配置信息
# 2. 提供配置项的读取和修改功能
# 3. 支持配置文件的加载和保存

# 配置项：
# - 编译服务器配置：地址、端口、用户名、密码、编译命令
# - 测试服务器配置：地址、端口、用户名、密码、烧卡脚本路径
# - LLM模型配置：API密钥、模型名称、API地址
# - 测试配置：测试脚本路径、串口日志收集脚本路径
# - 上传配置：上传网页地址、上传参数

import json
import os
from typing import Dict, Any, Optional

class Config:
    """配置管理类"""
    
    def __init__(self, config_file: str = "config.json"):
        """
        初始化配置管理
        参数：config_file - 配置文件路径
        """
        self.config_file = config_file
        self.config: Dict[str, Any] = self._get_default_config()
        self.load_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """
        获取默认配置
        注意：这里使用了默认值，实际使用时需要替换为真实的配置信息
        """
        return {
            "build_server": {
                "host": "BS_JUJUBE_SZ_01.memblaze.com",
                "port": 22,
                "username": "xxx",
                "password": "xxx",  # 注意：实际使用时需要替换为真实密码
                "build_command": "cd firmware && python3 /home/haodong.zhang/firmware/products/goji/scripts/build_goji_ymtc_blkXpage.py build release all"
            },
            "test_server": {
                "host": "172.16.8.51",
                "port": 22,
                "username": "xxx",
                "password": "xxx",  # 注意：实际使用时需要替换为真实密码
                "flash_script": "/path/to/flash_script.sh"
            },
            "llm": {
                "api_key": "xxx",  # 注意：实际使用时需要替换为真实API密钥
                "model": "DeepSeek-V3.2",
                "api_url": "xxx"
            },
            "test": {
                "test_script": "/path/to/test_script.sh",
                "uart_log_script": "/path/to/uart_log.sh"
            },
            "upload": {
                "upload_url": "https://example.com/upload",
                "upload_params": {
                    "project": "test_project"
                }
            }
        }
    
    def load_config(self):
        """
        加载配置文件
        """
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
            except Exception as e:
                print(f"加载配置文件失败: {str(e)}")
                self.config = self._get_default_config()
    
    def save_config(self):
        """
        保存配置文件
        """
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
            return False
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """
        获取配置项
        参数：
            key - 配置项键名，支持点号分隔的路径，如 "build_server.host"
            default - 默认值
        返回：配置项值
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set_config(self, key: str, value: Any) -> bool:
        """
        设置配置项
        参数：
            key - 配置项键名，支持点号分隔的路径，如 "build_server.host"
            value - 配置项值
        返回：设置是否成功
        """
        try:
            keys = key.split('.')
            config = self.config
            
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            config[keys[-1]] = value
            return True
        except Exception as e:
            print(f"设置配置项失败: {str(e)}")
            return False

# 全局配置实例
config = Config()

def get_config() -> Config:
    """
    获取配置实例
    """
    return config
