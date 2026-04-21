# 烧卡处理模块
# 功能：
# 1. 通过SSH访问测试服务器
# 2. 上传output文件到测试服务器
# 3. 执行烧卡脚本对指定测试机进行烧卡
# 4. 分析烧卡输出，判断是否成功
# 5. 收集烧卡错误信息

# 依赖模块：
# - ssh.ssh_client: 用于SSH连接和命令执行
# - file_transfer.file_transfer: 用于文件上传
# - llm.error_analyzer: 用于分析烧卡错误
import time
from ssh.ssh_client import get_connection_pool
from file_transfer.file_transfer import create_file_transfer
from llm.error_analyzer import get_error_analyzer
from config.config import get_config
from typing import Tuple, Optional

class FlashProcessor:
    """封装烧卡处理的类"""
    
    def __init__(self, log_callback=None):
        config = get_config()
        self.config = config
        self.connection_pool = get_connection_pool()
        self.error_analyzer = get_error_analyzer()
        self.log_callback = log_callback
    
    @property
    def test_server_config(self):
        return {
            "host": self.config.get_config("test_server.host"),
            "port": self.config.get_config("test_server.port"),
            "username": self.config.get_config("test_server.username"),
            "password": self.config.get_config("test_server.password"),
            "flash_script": self.config.get_config("test_server.flash_script")
        }
    
    def log(self, message: str, end: str = "\n"):
        """
        输出日志信息
        """
        print(message, end=end)
        if self.log_callback:
            self.log_callback(message + end)
    
    def upload_output_file(self, local_output_path: str, remote_output_path: str = "/tmp/output.bin") -> bool:
        """
        上传output文件到测试服务器
        参数：
            local_output_path - 本地output文件路径
            remote_output_path - 远程output文件路径
        返回：上传是否成功
        """
        # 获取SSH连接
        ssh_client = self.connection_pool.get_connection(
            self.test_server_config["host"],
            self.test_server_config["port"],
            self.test_server_config["username"],
            self.test_server_config["password"]
        )
        
        # 创建文件传输实例
        file_transfer = create_file_transfer(ssh_client)
        
        # 上传文件
        success = file_transfer.upload_file(local_output_path, remote_output_path)
        
        # 关闭文件传输
        file_transfer.close()
        
        return success
    
    def run_flash_script(self, test_device: str, remote_output_path: str = "/tmp/output.bin", project_name: str = "goji", sku: str = "ut768", flash_type: str = "ncmt", stop_event=None) -> Tuple[bool, Optional[str]]:
        """
        执行烧卡脚本
        参数：
            test_device - 测试设备标识
            remote_output_path - 远程output文件路径
            project_name - 项目名
            sku - SKU型号
            flash_type - 烧卡类型 (ncmt / fw download)
        返回：(烧卡是否成功, 错误信息)
        """
        # 获取SSH连接
        ssh_client = self.connection_pool.get_connection(
            self.test_server_config["host"],
            self.test_server_config["port"],
            self.test_server_config["username"],
            self.test_server_config["password"]
        )
        
        # 1. 确保firmware文件夹存在
        self.log("检查测试服务器firmware文件夹...")
        command = "mkdir -p ~/firmware"
        self.log(f"$ {command}")
        success, stdout, stderr = ssh_client.execute_command(command)
        if stdout:
            self.log(stdout, end="")
        if stderr:
            self.log(stderr, end="")
        if not success:
            return False, f"创建firmware文件夹失败: {stderr}"
        
        # 2. 检查output文件夹是否存在
        self.log("检查output文件夹是否存在...")
        command = "ls -la ~/firmware/output"
        self.log(f"$ {command}")
        success, stdout, stderr = ssh_client.execute_command(command)
        if stdout:
            self.log(stdout, end="")
        if stderr:
            self.log(stderr, end="")
        
        # 3. 从编译服务器下载output文件夹到本地
        self.log("从编译服务器下载output文件夹...")
        # 这里需要实现从编译服务器下载output文件夹的逻辑
        # 暂时跳过，假设已经下载到本地
        
        # 4. 上传output文件夹到测试服务器的firmware目录
        self.log("上传output文件夹到测试服务器...")
        # 这里需要实现上传output文件夹到测试服务器的逻辑
        # 暂时跳过，假设已经上传
        
        # 6. 构建烧卡命令
        # 烧卡脚本：Remanufacture.py --host=xx --sku=YOUR_SKU --product=YOUR_PROJECT --force --fwrev=/home/YOUR_USERNAME/firmware/output/
        # 其中host是被烧卡的机器，product是项目名，fwrev路径中包含测试服务器登录账号
        test_server_username = self.test_server_config["username"]
        
        # 7. 执行烧卡命令
        self.log("执行烧卡命令...")
        self.log("开始执行命令...")
        start_time = time.time()
        
        # 使用交互式shell来执行命令，这样可以保持环境变量
        channel = ssh_client.client.invoke_shell()
        
        # 配置测试环境
        self.log("配置测试环境...")
        channel.send("cd pbdt && setpbdt .\n")
        
        # 等待测试环境配置完成，检测(pbdt)提示符
        self.log("等待测试环境配置完成...")
        env_output = ""
        max_wait = 30  # 最多等待30秒
        wait_time = 0
        while wait_time < max_wait:
            if stop_event and stop_event.is_set():
                self.log("\n发送Ctrl+C停止...")
                channel.send("\x03")
                time.sleep(0.5)
                channel.close()
                return False, "执行已停止"
            if channel.recv_ready():
                output = channel.recv(1024).decode('utf-8')
                env_output += output
                self.log(output, end="")
                # 检查是否出现了(pbdt)提示符
                if "(pbdt)" in env_output:
                    self.log("\n测试环境配置完成！")
                    break
            time.sleep(0.5)
            wait_time += 0.5
        else:
            self.log("\n等待测试环境配置超时")
            channel.close()
            return False, "等待测试环境配置超时"
        
        # 执行烧卡命令
        if flash_type == "fw download":
            flash_command = f"FwDownload.py --product={project_name} --ca=3 --fs=2 --host={test_device} --fwrev=/home/{test_server_username}/firmware/output/"
        else:
            flash_command = f"Remanufacture.py --host={test_device} --sku={sku} --product={project_name} --force --fwrev=/home/{test_server_username}/firmware/output/"
        self.log(f"$ {flash_command}")
        channel.send(flash_command + "\n")
        
        # 等待命令执行完成，持续读取输出，不设超时
        self.log("等待烧卡命令执行完成...")
        stdout = ""
        stderr = ""
        while True:
            if stop_event and stop_event.is_set():
                self.log("\n发送Ctrl+C停止烧卡...")
                channel.send("\x03")
                time.sleep(1)
                # 读取剩余输出
                while channel.recv_ready():
                    output = channel.recv(4096).decode('utf-8', errors='replace')
                    stdout += output
                    self.log(output, end="")
                channel.close()
                return False, "执行已停止"
            if channel.recv_ready():
                output = channel.recv(1024).decode('utf-8')
                stdout += output
                self.log(output, end="")
                if "(pbdt)" in output and "$" in output:
                    self.log("\n烧卡命令执行完成！")
                    break
            time.sleep(0.5)
        
        end_time = time.time()
        self.log(f"\n命令执行完成，耗时: {end_time - start_time:.2f} 秒")
        
        # 关闭通道
        channel.close()
        
        # 检查输出中是否有错误信息
        success = True
        combined = (stdout + "\n" + stderr).lower()
        if "bash:" in combined or "command not found" in combined:
            success = False
        # 检查OverallResult是否为FAIL
        if "<overallresult>fail</overallresult>" in combined:
            success = False
        
        # 分析烧卡结果
        if not success:
            error_message = stdout if stdout.strip() else (stderr or "烧卡命令执行失败")
            return False, error_message
        
        flash_success, error_message = self.analyze_flash_result(stdout, stderr)
        if not flash_success:
            return False, error_message
        
        return True, None
    
    def analyze_flash_result(self, stdout: str, stderr: str) -> Tuple[bool, Optional[str]]:
        """
        分析烧卡结果
        判断规则：
        - OverallResult为PASS → 成功
        - OverallResult为FAIL → 失败
        - WARN不算失败
        - 包含bash错误或command not found → 失败
        参数：
            stdout - 标准输出
            stderr - 标准错误
        返回：(烧卡是否成功, 错误信息)
        """
        combined = (stdout + "\n" + stderr).lower()
        
        # 检查OverallResult
        if "<overallresult>pass</overallresult>" in combined:
            return True, None
        
        if "<overallresult>fail</overallresult>" in combined:
            return False, stdout or stderr
        
        # 检查bash错误
        if "bash:" in combined or "command not found" in combined:
            return False, combined
        
        # 没有明确的PASS/FAIL结果，默认认为烧卡成功
        return True, None
    
    def handle_flash_error(self, error_message: str, stream_callback=None) -> str:
        """
        处理烧卡错误
        参数：
            error_message - 错误信息
            stream_callback - 流式输出回调
        返回：错误分析结果
        """
        analysis_result = self.error_analyzer.analyze_flash_error(error_message, stream_callback=stream_callback)
        return analysis_result

# 全局烧卡处理器实例
flash_processor = FlashProcessor()

def get_flash_processor() -> FlashProcessor:
    """
    获取烧卡处理器实例
    """
    return flash_processor
