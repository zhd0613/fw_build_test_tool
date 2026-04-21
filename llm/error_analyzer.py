# LLM错误分析模块
# 功能：
# 1. 将编译、烧卡、测试过程中的错误信息作为prompt发送给LLM模型
# 2. 获取LLM模型的分析结果（支持流式输出）
# 3. 处理LLM模型的响应
# 4. 格式化分析结果，展示给用户

import requests
import json
from typing import Optional, Callable
from config.config import get_config

class ErrorAnalyzer:
    """封装错误分析的类"""
    
    def __init__(self):
        self.config = get_config()
        self.last_error = None
    
    @property
    def api_key(self):
        return self.config.get_config("llm.api_key")
    
    @property
    def model(self):
        return self.config.get_config("llm.model")
    
    @property
    def api_url(self):
        return self.config.get_config("llm.api_url").rstrip(',').rstrip('/')
    
    def _call_llm_stream(self, prompt: str, stream_callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """
        调用LLM模型（流式输出）
        参数：
            prompt - 提示词
            stream_callback - 流式输出回调函数，每收到一段内容就调用
        返回：LLM模型的完整响应
        """
        self.last_error = None
        
        max_prompt_length = 6000
        if len(prompt) > max_prompt_length:
            prompt = "...(前面内容已截断)...\n\n" + prompt[-max_prompt_length:]
        
        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}"
            }
            
            data = {
                "model": self.model,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "你是一个专业的嵌入式固件开发和测试工程师，擅长分析固件编译、烧卡(flash/remanufacture)和测试过程中的错误。"
                            "请严格按照以下格式输出分析结果，不要输出多余内容：\n"
                            "1. 错误类型：[编译错误/烧卡错误/测试错误/路径错误/环境错误/其他]\n"
                            "2. 错误原因：[一句话概括根本原因]\n"
                            "3. 详细分析：[具体分析错误发生的原因，引用关键错误信息]\n"
                            "4. 解决方案：[给出具体的解决步骤]\n"
                            "注意：分析要简洁精准，总字数不超过300字。"
                        )
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                "max_tokens": 500,
                "temperature": 0.2,
                "stream": True
            }
            
            chat_url = self.api_url + '/chat/completions'
            print(f"[LLM] 调用API(流式): {chat_url}, 模型: {self.model}, Prompt长度: {len(prompt)}")
            
            response = requests.post(chat_url, headers=headers, json=data, timeout=120, stream=True)
            response.raise_for_status()
            
            full_content = ""
            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode('utf-8')
                if not line.startswith("data: "):
                    continue
                data_str = line[6:]
                if data_str.strip() == "[DONE]":
                    break
                try:
                    chunk = json.loads(data_str)
                    choices = chunk.get("choices", [])
                    if not choices:
                        continue
                    delta = choices[0].get("delta", {})
                    content = delta.get("content", "")
                    if content:
                        full_content += content
                        if stream_callback:
                            stream_callback(content)
                except json.JSONDecodeError:
                    continue
            
            print(f"[LLM] 响应完成，总长度: {len(full_content)} 字符")
            return full_content
            
        except requests.exceptions.Timeout:
            self.last_error = "请求超时(120秒)"
            print(f"[LLM] {self.last_error}")
            return None
        except requests.exceptions.ConnectionError as e:
            self.last_error = f"连接错误: {e}"
            print(f"[LLM] {self.last_error}")
            return None
        except requests.exceptions.HTTPError as e:
            self.last_error = f"HTTP错误: {e}"
            print(f"[LLM] {self.last_error}")
            return None
        except Exception as e:
            self.last_error = f"调用LLM失败: {type(e).__name__}: {str(e)}"
            print(f"[LLM] {self.last_error}")
            return None
    
    def analyze_build_error(self, error_message: str, stream_callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """
        分析编译错误
        """
        prompt = (
            f"【编译错误分析】\n\n"
            f"以下是编译固件时产生的错误输出：\n\n"
            f"{error_message}\n\n"
            f"请分析编译失败的根本原因，重点关注：\n"
            f"- 具体是哪个源文件、哪一行出了问题\n"
            f"- 是语法错误、链接错误还是依赖缺失\n"
            f"- 给出修复建议"
        )
        result = self._call_llm_stream(prompt, stream_callback)
        return self.format_analysis_result("编译错误分析", result)
    
    def analyze_flash_error(self, error_message: str, stream_callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """
        分析烧卡错误
        """
        prompt = (
            f"【烧卡错误分析】\n\n"
            f"以下是在测试服务器上执行烧卡(flash/remanufacture)命令时产生的错误输出：\n\n"
            f"{error_message}\n\n"
            f"请分析烧卡失败的根本原因，重点关注：\n"
            f"- 是否是固件文件路径错误（如--fwrev参数指向的路径不存在或不正确）\n"
            f"- 是否是固件包格式或版本不匹配\n"
            f"- 是否是网络连接或设备连接问题\n"
            f"- 是否是测试环境配置问题\n"
            f"- 给出具体的修复步骤"
        )
        result = self._call_llm_stream(prompt, stream_callback)
        return self.format_analysis_result("烧卡错误分析", result)
    
    def analyze_test_error(self, error_message: str, uart_log: str = "", stream_callback: Optional[Callable[[str], None]] = None) -> Optional[str]:
        """
        分析测试错误
        """
        if uart_log:
            prompt = (
                f"【测试错误分析】\n\n"
                f"以下是执行测试脚本时产生的错误输出：\n\n"
                f"{error_message}\n\n"
                f"串口日志：\n{uart_log}\n\n"
                f"请分析测试失败的根本原因，重点关注：\n"
                f"- 测试脚本本身的错误\n"
                f"- 设备响应异常\n"
                f"- 环境配置问题\n"
                f"- 给出具体的修复步骤"
            )
        else:
            prompt = (
                f"【测试错误分析】\n\n"
                f"以下是执行测试脚本时产生的错误输出：\n\n"
                f"{error_message}\n\n"
                f"请分析测试失败的根本原因，重点关注：\n"
                f"- 测试脚本本身的错误\n"
                f"- 设备响应异常\n"
                f"- 环境配置问题\n"
                f"- 给出具体的修复步骤"
            )
        result = self._call_llm_stream(prompt, stream_callback)
        return self.format_analysis_result("测试错误分析", result)
    
    def format_analysis_result(self, title: str, result: Optional[str]) -> str:
        """
        格式化分析结果
        """
        if not result:
            error_detail = self.last_error or "未知错误"
            return f"{title}\n\n分析失败，原因: {error_detail}"
        
        return result

# 全局错误分析器实例
error_analyzer = ErrorAnalyzer()

def get_error_analyzer() -> ErrorAnalyzer:
    return error_analyzer
