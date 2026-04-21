# 测试结果上传模块
# 功能：
# 1. 将测试结果通过脚本上传到指定网页
# 2. 处理上传过程中的异常
# 3. 验证上传是否成功

# 依赖库：
# - requests: 用于HTTP请求
import requests
import json
import time
from typing import Dict, Any, Optional, Tuple
from config.config import get_config

class ResultUploader:
    """封装结果上传的类"""
    
    def __init__(self):
        """
        初始化结果上传器
        """
        config = get_config()
        self.upload_config = {
            "upload_url": config.get_config("upload.upload_url"),
            "upload_params": config.get_config("upload.upload_params")
        }
    
    def upload_test_result(self, test_result: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        上传测试结果
        参数：test_result - 测试结果
        返回：(上传是否成功, 错误信息)
        """
        try:
            # 构建上传数据
            upload_data = {
                **self.upload_config["upload_params"],
                "test_result": test_result,
                "timestamp": time.time()
            }
            
            # 发送POST请求
            response = requests.post(
                self.upload_config["upload_url"],
                json=upload_data,
                timeout=30
            )
            
            # 验证上传是否成功
            if response.status_code == 200:
                # 验证响应内容
                if self.verify_upload(response.json()):
                    return True, None
                else:
                    return False, "上传验证失败"
            else:
                return False, f"上传失败，状态码: {response.status_code}"
        except Exception as e:
            error_message = f"上传过程中发生错误: {str(e)}"
            self.handle_upload_error(e)
            return False, error_message
    
    def verify_upload(self, response: Dict[str, Any]) -> bool:
        """
        验证上传是否成功
        参数：response - 上传响应
        返回：验证是否成功
        """
        # 这里需要根据具体的上传接口响应格式来实现验证逻辑
        # 例如，假设响应中包含"status"字段，值为"success"
        if "status" in response and response["status"] == "success":
            return True
        return False
    
    def handle_upload_error(self, error: Exception):
        """
        处理上传错误
        参数：error - 错误异常
        """
        # 这里可以添加错误处理逻辑，比如日志记录、重试等
        pass

# 全局结果上传器实例
result_uploader = ResultUploader()

def get_result_uploader() -> ResultUploader:
    """
    获取结果上传器实例
    """
    return result_uploader
