# 自定义 FIO 测试处理模块
from typing import Tuple, Optional, Dict
from llm.fio_command_generator import FIOCommandGenerator
from ssh.ssh_client import get_connection_pool
import time
import re


class FIOTestProcessor:
    """
    自定义 FIO 测试处理器
    负责将用户的测试需求转换为 FIO 命令并执行测试
    """
    
    def __init__(self, config, log_callback=None):
        self.config = config
        self.log_callback = log_callback or (lambda x: print(x))
        self.connection_pool = get_connection_pool()
    
    @property
    def fio_generator(self):
        return FIOCommandGenerator(
            api_url=self.config.get_config("llm.api_url"),
            api_key=self.config.get_config("llm.api_key"),
            model=self.config.get_config("llm.model")
        )
    
    @property
    def test_server_config(self):
        return {
            "host": self.config.get_config("test_server.host"),
            "port": self.config.get_config("test_server.port"),
            "username": self.config.get_config("test_server.username"),
            "password": self.config.get_config("test_server.password")
        }
    
    def log(self, message: str, end: str = "\n"):
        """日志输出"""
        self.log_callback(message + end)
    
    def generate_fio_commands(self, test_requirement: str) -> Tuple[bool, Optional[str], Optional[list]]:
        """
        根据用户输入的测试需求生成 FIO 命令
        参数：
            test_requirement - 用户输入的测试需求描述
        返回：(是否成功，错误信息，FIO 命令列表)
        """
        self.log("[FIO] 正在生成 FIO 命令...")
        
        # 调用 LLM 生成 FIO 命令
        success, error, commands = self.fio_generator.generate_commands(test_requirement)
        
        if not success:
            self.log(f"[FIO] 生成失败：{error}")
            return False, error, None
        
        self.log(f"[FIO] 成功生成 {len(commands)} 条 FIO 命令")
        for i, cmd in enumerate(commands, 1):
            self.log(f"  {i}. {cmd}")
        
        return True, None, commands
    
    def _wait_for_prompt(self, channel, prompts, max_wait=30, stop_event=None):
        """
        等待指定的提示符出现
        参数：
            channel - SSH channel
            prompts - 期望出现的提示符列表
            max_wait - 最大等待时间（秒）
            stop_event - 停止事件
        返回：(是否成功, 累积输出)
        """
        output = ""
        wait_time = 0
        while wait_time < max_wait:
            if stop_event and stop_event.is_set():
                return False, output
            if channel.recv_ready():
                try:
                    chunk = channel.recv(4096).decode('utf-8', errors='replace')
                except Exception:
                    break
                output += chunk
                self.log(chunk, end="")
                for prompt in prompts:
                    if prompt in output:
                        return True, output
            time.sleep(0.3)
            wait_time += 0.3
        return False, output
    
    def run_fio_test(self, test_device: str, fio_commands: list, stop_event=None) -> Tuple[bool, Optional[str]]:
        """
        执行 FIO 测试命令
        流程：
        1. SSH连接到测试服务器
        2. 在测试服务器上通过交互式shell执行 ssh root@test_device 登录测试机
        3. 输入密码完成登录
        4. 确认登录成功后，逐条执行 fio 命令
        参数：
            test_device - 测试设备标识（如 szb41）
            fio_commands - FIO 命令列表
            stop_event - 停止事件
        返回：(测试是否成功，错误信息)
        """
        self.log("[FIO] 开始执行 FIO 测试...")
        
        # 1. 获取测试服务器的 SSH 连接
        ssh_client = self.connection_pool.get_connection(
            self.test_server_config["host"],
            self.test_server_config["port"],
            self.test_server_config["username"],
            self.test_server_config["password"]
        )
        
        # 2. 使用交互式shell
        try:
            channel = ssh_client.client.invoke_shell()
        except Exception as e:
            self.log(f"[FIO] 创建交互式shell失败: {e}")
            return False, f"创建交互式shell失败: {e}"
        
        time.sleep(1)
        if channel.recv_ready():
            channel.recv(4096)
        
        # 3. SSH 登录到测试机
        ssh_login_cmd = f"ssh root@{test_device}\n"
        self.log(f"[FIO] 登录测试机: ssh root@{test_device}")
        channel.send(ssh_login_cmd)
        
        # 等待密码提示或host key确认提示
        login_output = ""
        password_prompted = False
        max_login_wait = 30
        login_wait = 0
        while login_wait < max_login_wait:
            if stop_event and stop_event.is_set():
                channel.close()
                return False, "执行已停止"
            if channel.recv_ready():
                try:
                    chunk = channel.recv(4096).decode('utf-8', errors='replace')
                except Exception:
                    break
                login_output += chunk
                self.log(chunk, end="")
                
                if "are you sure you want to continue connecting" in login_output.lower() or "(yes/no)" in login_output.lower():
                    self.log("[FIO] 接受host key...")
                    channel.send("yes\n")
                    login_output = ""
                
                if "password:" in login_output.lower():
                    password_prompted = True
                    break
                
                clean_output = re.sub(r'\x1b\[[0-9;]*m', '', login_output)
                if "# " in clean_output or "$ " in clean_output or "#>" in clean_output or "$>" in clean_output:
                    self.log("[FIO] 已登录测试机（免密）")
                    break
            time.sleep(0.3)
            login_wait += 0.3
        
        if password_prompted:
            test_server_password = self.test_server_config["password"]
            self.log("[FIO] 输入密码...")
            channel.send(test_server_password + "\n")
            
            success, output = self._wait_for_prompt(channel, ["# ", "$ ", "#>", "$>", "Permission denied"], max_wait=15, stop_event=stop_event)
            if not success:
                self.log("[FIO] 登录测试机超时")
                channel.close()
                return False, "登录测试机超时"
            
            if "Permission denied" in output:
                self.log("[FIO] 登录测试机失败：密码错误")
                channel.close()
                return False, "登录测试机失败：密码错误"
            
            self.log("[FIO] 成功登录测试机")
        elif not ("# " in login_output or "$ " in login_output or "#>" in login_output or "$>" in login_output):
            clean_output = re.sub(r'\x1b\[[0-9;]*m', '', login_output)
            if not ("# " in clean_output or "$ " in clean_output or "#>" in clean_output or "$>" in clean_output):
                self.log("[FIO] 登录测试机超时")
                channel.close()
                return False, "登录测试机超时"
        
        # 4. 逐条执行 FIO 命令
        for i, cmd in enumerate(fio_commands, 1):
            if stop_event and stop_event.is_set():
                self.log("[FIO] 测试被用户停止")
                channel.send("\x03")
                time.sleep(0.5)
                channel.close()
                return False, "测试被用户停止"
            
            self.log(f"[FIO] 执行第 {i} 条命令: {cmd}")
            channel.send(cmd + "\n")
            
            # 等待命令执行完成（回到shell提示符）
            cmd_output = ""
            cmd_start_time = time.time()
            while True:
                if stop_event and stop_event.is_set():
                    self.log("\n[FIO] 发送Ctrl+C停止...")
                    channel.send("\x03")
                    time.sleep(0.5)
                    channel.close()
                    return False, "测试被用户停止"
                if channel.recv_ready():
                    try:
                        chunk = channel.recv(4096).decode('utf-8', errors='replace')
                    except Exception:
                        break
                    cmd_output += chunk
                    self.log(chunk, end="")
                    tail = cmd_output[-300:] if len(cmd_output) > 300 else cmd_output
                    clean_tail = re.sub(r'\x1b\[[0-9;]*m', '', tail)
                    if re.search(r'\S+@\S+', clean_tail) and re.search(r'[#\$]>?\s*$', clean_tail.strip().split('\n')[-1].strip()):
                        if "password:" not in cmd_output.lower():
                            break
                time.sleep(0.5)
            
            # 检查命令是否有明显错误
            if "command not found" in cmd_output.lower() or "no such file" in cmd_output.lower():
                self.log(f"[FIO] 命令执行出错: {cmd_output}")
                channel.close()
                return False, f"命令执行出错: {cmd_output}"
            
            elapsed = time.time() - cmd_start_time
            self.log(f"\n[FIO] 第 {i} 条命令执行完成，耗时 {elapsed:.1f} 秒")
        
        # 5. 退出测试机
        self.log("[FIO] 退出测试机...")
        channel.send("exit\n")
        time.sleep(1)
        
        channel.close()
        self.log("[FIO] FIO 测试执行完成")
        return True, None
