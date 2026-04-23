# 编译处理模块
# 功能：
# 1. 通过SSH访问编译服务器
# 2. 执行编译命令
# 3. 分析编译输出，判断是否成功
# 4. 收集编译错误信息
# 5. 当编译成功时，获取output文件路径

# 依赖模块：
# - ssh.ssh_client: 用于SSH连接和命令执行
# - llm.error_analyzer: 用于分析编译错误
from ssh.ssh_client import get_connection_pool
from llm.error_analyzer import get_error_analyzer
from config.config import get_config
from typing import Tuple, Optional

class BuildProcessor:
    """封装编译处理的类"""
    
    def __init__(self, log_callback=None):
        config = get_config()
        self.config = config
        self.connection_pool = get_connection_pool()
        self.error_analyzer = get_error_analyzer()
        self.project_path = "/home/YOUR_USERNAME/firmware/"
        self.project_name = "goji"
        self.log_callback = log_callback
    
    @property
    def build_server_config(self):
        return {
            "host": self.config.get_config("build_server.host"),
            "port": self.config.get_config("build_server.port"),
            "username": self.config.get_config("build_server.username"),
            "password": self.config.get_config("build_server.password")
        }
    
    def log(self, message: str, end: str = "\n"):
        """
        输出日志信息
        """
        print(message, end=end)
        if self.log_callback:
            self.log_callback(message + end)
    
    def set_project_info(self, project_path: str, project_name: str):
        """
        设置项目信息
        参数：
            project_path - 项目路径
            project_name - 项目名
        """
        self.project_path = project_path
        self.project_name = project_name
    
    def run_build(self, stop_event=None) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        执行编译命令
        参数：
            stop_event - 停止事件
        返回：(编译是否成功, output文件路径, 错误信息)
        """
        import time
        
        # 获取SSH连接
        ssh_client = self.connection_pool.get_connection(
            self.build_server_config["host"],
            self.build_server_config["port"],
            self.build_server_config["username"],
            self.build_server_config["password"]
        )
        
        # 根据项目名生成编译命令
        build_command = f"python3 {self.project_path}products/{self.project_name}/scripts/build_{self.project_name}_ymtc_blkXpage.py build release all"
        self.log(f"$ {build_command}")
        
        # 使用交互式shell执行编译，支持Ctrl+C停止
        channel = ssh_client.client.invoke_shell()
        
        time.sleep(1)
        if channel.recv_ready():
            channel.recv(1024)
        
        # 发送编译命令
        channel.send(build_command + "\n")
        
        # 实时读取输出
        self.log("编译输出:")
        stdout = ""
        stderr = ""
        
        while True:
            if stop_event and stop_event.is_set():
                self.log("\n发送Ctrl+C停止编译...")
                channel.send("\x03")
                time.sleep(1)
                while channel.recv_ready():
                    output = channel.recv(4096).decode('utf-8', errors='replace')
                    stdout += output
                    self.log(output, end="")
                channel.close()
                return False, None, "执行已停止"
            if channel.recv_ready():
                output = channel.recv(4096).decode('utf-8', errors='replace')
                stdout += output
                self.log(output, end="")
                import re
                tail = stdout[-300:] if len(stdout) > 300 else stdout
                clean_tail = re.sub(r'\x1b\[[0-9;]*m', '', tail)
                if re.search(r'\S+@\S+', clean_tail) and re.search(r'[#\$]>?\s*$', clean_tail.strip().split('\n')[-1].strip()):
                    self.log("\n编译命令执行完成")
                    break
            else:
                time.sleep(0.5)
        
        channel.close()
        
        # 分析编译结果
        build_success, error_message = self.analyze_build_result(stdout, stderr)
        if not build_success:
            error_message = self.extract_error_info(error_message)
            return False, None, error_message
        
        # 获取output文件路径
        output_path = self.get_output_path(stdout)
        if not output_path:
            return False, None, "无法获取编译输出文件路径"
        
        return True, output_path, None
    
    def analyze_build_result(self, stdout: str, stderr: str) -> Tuple[bool, Optional[str]]:
        """
        分析编译结果
        参数：
            stdout - 标准输出
            stderr - 标准错误
        返回：(编译是否成功, 错误信息)
        """
        combined_output = (stdout or "") + "\n" + (stderr or "")
        combined_lower = combined_output.lower()
        
        # 检查是否有明确的编译错误信息
        # 1. C/C++编译错误: "error:" 出现在源文件行中
        # 2. ninja构建失败: "ninja: build stopped" 或 "subcommand failed"
        # 3. cmake构建失败: "failed: 256" 或 "Command:" ... "failed"
        # 4. 通用失败信息: "build failed", "compilation failed", "compilation error"
        
        error_keywords = [
            "ninja: build stopped",
            "subcommand failed",
            "failed: 256",
            "build failed",
            "compilation failed",
            "compilation error",
        ]
        
        # 检查是否有编译错误行 (如 sched_write.c:1090:5: error:)
        import re
        if re.search(r':\d+:\d+:\s*error:', combined_output):
            return False, combined_output
        
        # 检查是否有明确的失败关键字
        for keyword in error_keywords:
            if keyword.lower() in combined_lower:
                return False, combined_output
        
        # 检查stderr中是否有error
        if stderr and "error" in stderr.lower():
            return False, combined_output
        
        # 检查是否有明确的成功信息
        success_keywords = [
            "build successful",
            "compilation completed",
            "build completed",
        ]
        for keyword in success_keywords:
            if keyword.lower() in combined_lower:
                return True, None
        
        # 如果没有明确的成功或失败信息，检查返回码
        # 如果输出中有大量内容但没有成功信息，可能是失败的
        # 这里保守一点，如果没有错误信息就认为成功
        return True, None
    
    def get_output_path(self, stdout: str) -> Optional[str]:
        """
        获取编译输出文件路径
        参数：stdout - 标准输出
        返回：output文件路径
        """
        # 直接返回根据项目信息生成的默认输出路径
        # 这样可以确保路径总是正确的，不受编译输出的影响
        return f"{self.project_path}build/{self.project_name}/ymtc/release/output/"
    
    def extract_error_info(self, output: str) -> str:
        """
        从编译输出中提取错误相关的信息
        参数：output - 完整的编译输出
        返回：提取后的错误信息
        """
        import re
        
        if not output:
            return ""
        
        lines = output.split('\n')
        error_lines = []
        error_context_lines = 5  # 错误行前后保留的行数
        
        # 找到所有包含 error: 的行号
        error_line_nums = []
        for i, line in enumerate(lines):
            if re.search(r'error:', line, re.IGNORECASE):
                error_line_nums.append(i)
            elif 'ninja: build stopped' in line.lower():
                error_line_nums.append(i)
            elif 'subcommand failed' in line.lower():
                error_line_nums.append(i)
            elif 'failed:' in line.lower():
                error_line_nums.append(i)
        
        if not error_line_nums:
            # 如果没有找到明确的错误行，返回最后100行
            return '\n'.join(lines[-100:])
        
        # 提取每个错误行及其上下文
        extracted = set()
        for line_num in error_line_nums:
            start = max(0, line_num - error_context_lines)
            end = min(len(lines), line_num + error_context_lines + 1)
            for i in range(start, end):
                extracted.add(i)
        
        # 按行号排序并拼接
        result_lines = []
        for i in sorted(extracted):
            result_lines.append(lines[i])
        
        result = '\n'.join(result_lines)
        
        # 如果提取后的内容还是太长，截取最后部分
        if len(result) > 6000:
            result = "...(前面内容已截断)...\n" + result[-6000:]
        
        return result
    
    def handle_build_error(self, error_message: str, stream_callback=None) -> str:
        analysis_result = self.error_analyzer.analyze_build_error(error_message, stream_callback=stream_callback)
        return analysis_result
    
    def get_git_log(self, project_path=None, count=100):
        """
        从编译服务器获取 git log
        参数：
            project_path - 项目路径
            count - 获取的提交数量
        返回：提交列表，每项为 "hash message" 格式
        """
        path = project_path or self.project_path
        ssh_client = self.connection_pool.get_connection(
            self.build_server_config["host"],
            self.build_server_config["port"],
            self.build_server_config["username"],
            self.build_server_config["password"]
        )
        command = f"cd {path} && git log --oneline -{count}"
        self.log(f"$ {command}")
        success, stdout, stderr = ssh_client.execute_command(command)
        if success and stdout.strip():
            lines = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
            return lines
        self.log(f"获取git log失败: {stderr}")
        return []
    
    def git_reset_to_commit(self, commit_hash, project_path=None):
        """
        在编译服务器上 git reset 到指定 commit
        参数：
            commit_hash - 目标 commit hash
            project_path - 项目路径
        返回：(是否成功, 错误信息)
        """
        path = project_path or self.project_path
        ssh_client = self.connection_pool.get_connection(
            self.build_server_config["host"],
            self.build_server_config["port"],
            self.build_server_config["username"],
            self.build_server_config["password"]
        )
        command = f"cd {path} && git reset {commit_hash} --hard"
        self.log(f"$ {command}")
        success, stdout, stderr = ssh_client.execute_command(command)
        if success:
            self.log(f"git reset 到 {commit_hash} 成功")
            return True, None
        self.log(f"git reset 失败: {stderr}")
        return False, stderr

# 全局编译处理器实例
build_processor = BuildProcessor()

def get_build_processor() -> BuildProcessor:
    """
    获取编译处理器实例
    """
    return build_processor
