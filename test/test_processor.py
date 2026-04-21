# 测试执行与串口日志收集模块
# 功能：
# 1. 执行用户选定的测试脚本
# 2. 使用读取Uart log的脚本收集串口信息
# 3. 分析测试输出，判断是否成功
# 4. 收集测试错误信息和对应时间点的串口内容

# 依赖模块：
# - ssh.ssh_client: 用于SSH连接和命令执行
# - llm.error_analyzer: 用于分析测试错误
from ssh.ssh_client import get_connection_pool
from llm.error_analyzer import get_error_analyzer
from config.config import get_config
from typing import Tuple, Optional, Dict
import time

class TestProcessor:
    """封装测试处理的类"""
    
    def __init__(self, log_callback=None):
        config = get_config()
        self.config = config
        self.connection_pool = get_connection_pool()
        self.error_analyzer = get_error_analyzer()
        self.uart_logs = []
        self.log_callback = log_callback
    
    @property
    def test_server_config(self):
        return {
            "host": self.config.get_config("test_server.host"),
            "port": self.config.get_config("test_server.port"),
            "username": self.config.get_config("test_server.username"),
            "password": self.config.get_config("test_server.password")
        }
    
    @property
    def test_config(self):
        return {
            "test_script": self.config.get_config("test.test_script"),
            "uart_log_script": self.config.get_config("test.uart_log_script")
        }
    
    def log(self, message: str, end: str = "\n"):
        """
        输出日志信息
        """
        print(message, end=end)
        if self.log_callback:
            self.log_callback(message + end)
    
    def run_test_script(self, test_script: Optional[str] = None, stop_event=None, test_device: str = "", sku: str = "", product: str = "", test_case: str = "", other_param: str = "", upload_result: bool = False, version: str = "", extra_scripts: list = None) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        执行测试脚本
        参数：
            test_script - 测试脚本路径
            stop_event - 停止事件
            test_device - 测试设备（--host参数）
            sku - SKU型号（--sku参数）
            product - 项目名（--product参数）
            test_case - 测试用例（--case参数，默认all时不添加）
            other_param - 其他参数（默认空时不添加）
            upload_result - 是否上传测试结果到数据库
            version - 版本号（--fwkey参数）
            extra_scripts - 额外脚本列表，每项为 {"script":..., "case":..., "other_param":...}
        返回：(测试是否成功, 错误信息, 测试结果)
        """
        script_path = test_script or self.test_config["test_script"]
        
        # 构建测试命令
        command = script_path
        if test_device:
            command += f" --host={test_device}"
        if sku:
            command += f" --sku={sku}"
        if product:
            command += f" --product={product}"
        if test_case and test_case != "all":
            command += f" --case={test_case}"
        if other_param and other_param != "null":
            command += f" {other_param}"
        if upload_result:
            command += " --upload-results-to-db"
            if version:
                command += f" --fwkey={version}"
        
        # 拼接额外脚本
        if extra_scripts:
            for extra in extra_scripts:
                extra_cmd = extra["script"]
                if test_device:
                    extra_cmd += f" --host={test_device}"
                if sku:
                    extra_cmd += f" --sku={sku}"
                if product:
                    extra_cmd += f" --product={product}"
                extra_case = extra.get("case", "")
                if extra_case and extra_case != "all":
                    extra_cmd += f" --case={extra_case}"
                extra_other = extra.get("other_param", "")
                if extra_other and extra_other != "null":
                    extra_cmd += f" {extra_other}"
                if upload_result:
                    extra_cmd += " --upload-results-to-db"
                    if version:
                        extra_cmd += f" --fwkey={version}"
                command += f" && {extra_cmd}"
        
        self.log(f"测试命令: {command}")
        
        # 获取SSH连接
        ssh_client = self.connection_pool.get_connection(
            self.test_server_config["host"],
            self.test_server_config["port"],
            self.test_server_config["username"],
            self.test_server_config["password"]
        )
        
        # 使用交互式shell执行，确保pbdt环境变量生效
        import time
        channel = ssh_client.client.invoke_shell()
        
        time.sleep(1)
        if channel.recv_ready():
            channel.recv(1024)
        
        # 检查当前是否已在pbdt环境中
        self.log("检查测试环境...")
        channel.send("echo $PS1\n")
        time.sleep(1)
        ps1_output = ""
        if channel.recv_ready():
            ps1_output = channel.recv(4096).decode('utf-8', errors='replace')
        
        # 如果不在pbdt环境中，配置环境
        if "(pbdt)" not in ps1_output:
            self.log("配置测试环境...")
            channel.send("cd pbdt && setpbdt .\n")
            
            # 等待环境配置完成
            self.log("等待测试环境配置完成...")
            env_output = ""
            max_wait = 30
            wait_time = 0
            while wait_time < max_wait:
                if stop_event and stop_event.is_set():
                    self.log("\n发送Ctrl+C停止...")
                    channel.send("\x03")
                    time.sleep(0.5)
                    channel.close()
                    return False, "执行已停止", None
                if channel.recv_ready():
                    output = channel.recv(1024).decode('utf-8', errors='replace')
                    env_output += output
                    self.log(output, end="")
                    if "(pbdt)" in env_output:
                        self.log("\n测试环境配置完成！")
                        break
                time.sleep(0.5)
                wait_time += 0.5
            else:
                self.log("\n测试环境配置超时")
                channel.close()
                return False, "测试环境配置超时", None
        else:
            self.log("已在pbdt环境中")
        
        # 执行测试命令
        self.log(f"$ {command}")
        channel.send(command + "\n")
        
        # 实时读取测试输出
        self.log("测试输出:")
        stdout = ""
        stderr = ""
        while True:
            if stop_event and stop_event.is_set():
                self.log("\n发送Ctrl+C停止测试...")
                channel.send("\x03")
                time.sleep(1)
                while channel.recv_ready():
                    output = channel.recv(4096).decode('utf-8', errors='replace')
                    stdout += output
                    self.log(output, end="")
                channel.close()
                return False, "执行已停止", None
            if channel.recv_ready():
                output = channel.recv(4096).decode('utf-8', errors='replace')
                stdout += output
                self.log(output, end="")
            else:
                time.sleep(0.5)
            # 检查累积输出中是否回到命令提示符（测试执行完成）
            if "(pbdt)" in stdout and stdout.rstrip().endswith("$"):
                self.log("\n测试命令执行完成")
                break
        
        channel.close()
        
        # 分析测试结果
        test_success, error_message, test_result = self.analyze_test_result(stdout, stderr)
        if not test_success:
            error_timepoint_log = self.get_error_timepoint_log()
            return False, error_message, {"error_log": error_timepoint_log}
        
        return True, None, test_result
    
    def collect_uart_log(self, duration: int = 3600) -> bool:
        """
        收集串口日志
        参数：duration - 收集持续时间（秒）
        返回：收集是否成功
        """
        ssh_client = self.connection_pool.get_connection(
            self.test_server_config["host"],
            self.test_server_config["port"],
            self.test_server_config["username"],
            self.test_server_config["password"]
        )
        
        log_command = f"nohup {self.test_config['uart_log_script']} > uart.log 2>&1 &"
        success, stdout, stderr = ssh_client.execute_command(log_command)
        
        if not success:
            self.log(f"启动串口日志收集失败: {stderr}")
            return False
        
        return True
    
    def analyze_test_result(self, stdout: str, stderr: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        分析测试结果
        参数：
            stdout - 标准输出
            stderr - 标准错误
        返回：(测试是否成功, 错误信息, 测试结果)
        """
        combined_output = (stdout or "") + "\n" + (stderr or "")
        
        # 首先检查OverallResult和RESULT列，这是最终测试结果
        import re
        result_lines = re.findall(r'\|\s+\d+\s+\S+.*\|\s+(PASS|FAIL)\s+\|', combined_output)
        has_overall_pass = "<overallresult>pass</overallresult>" in combined_output.lower()
        has_overall_fail = "<overallresult>fail</overallresult>" in combined_output.lower()
        has_result_fail = result_lines and "FAIL" in result_lines
        
        # 如果OverallResult是PASS或RESULT列全部是PASS，判定为成功
        # 即使输出中有Traceback或Exception（可能是WARN级别）
        if has_overall_pass or (result_lines and all(r == "PASS" for r in result_lines)):
            test_result = self._parse_test_result(stdout)
            return True, None, test_result
        
        # 如果OverallResult是FAIL或RESULT列中有FAIL，判定为失败
        if has_overall_fail or has_result_fail:
            return False, combined_output, None
        
        # 没有明确的OverallResult或RESULT时，才检查异常信息
        # 检查是否有Python异常
        if "Traceback" in combined_output or "ImportError" in combined_output or "ModuleNotFoundError" in combined_output:
            return False, combined_output, None
        
        # 检查是否有bash错误（命令不存在等）
        if "bash:" in combined_output.lower() or "command not found" in combined_output.lower():
            return False, combined_output, None
        
        # 没有明确成功信息且退出码为0，保守认为测试通过
        # 但如果输出为空，可能是命令本身有问题
        if not stdout.strip() and not stderr.strip():
            return False, "测试命令无输出，可能命令无效", None
        
        test_result = self._parse_test_result(stdout)
        return True, None, test_result
    
    def _parse_test_result(self, stdout: str) -> Dict:
        """
        解析测试结果
        参数：stdout - 标准输出
        返回：测试结果字典
        """
        test_result = {
            "test_cases": [],
            "passed": 0,
            "failed": 0,
            "total": 0
        }
        
        lines = stdout.split('\n')
        for line in lines:
            if "test case" in line.lower():
                test_result["test_cases"].append(line)
                test_result["total"] += 1
            elif "passed" in line.lower():
                test_result["passed"] += 1
            elif "failed" in line.lower():
                test_result["failed"] += 1
        
        return test_result
    
    def handle_test_error(self, error_message: str, uart_log: str = "", stream_callback=None) -> str:
        """
        处理测试错误
        参数：
            error_message - 错误信息
            uart_log - 错误时间点的串口日志
            stream_callback - 流式输出回调
        返回：错误分析结果
        """
        analysis_result = self.error_analyzer.analyze_test_error(error_message, uart_log, stream_callback=stream_callback)
        return analysis_result
    
    def get_error_timepoint_log(self, time_window: int = 60) -> str:
        """
        获取错误时间点的串口内容
        参数：time_window - 时间窗口（秒）
        返回：错误时间点的串口日志
        """
        if self.uart_logs:
            return '\n'.join(self.uart_logs[-100:])
        return ""

# 全局测试处理器实例
test_processor = TestProcessor()

def get_test_processor() -> TestProcessor:
    """
    获取测试处理器实例
    """
    return test_processor
