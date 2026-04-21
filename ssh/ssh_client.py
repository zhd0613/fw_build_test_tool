# SSH连接与服务器交互模块
# 功能：
# 1. 建立SSH连接到远程服务器
# 2. 执行远程命令并获取输出
# 3. 处理SSH连接异常
# 4. 提供连接池管理，避免频繁建立连接

# 依赖库：
# - paramiko: 用于SSH连接和命令执行
import paramiko
import time
from typing import Dict, Optional, Tuple

class SSHClient:
    """封装SSH连接的类"""
    
    def __init__(self, host: str, port: int = 22, username: str = "user", password: str = "password"):
        """
        初始化SSHClient
        注意：这里使用了默认的用户名和密码，实际使用时需要替换为真实的账户信息
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.client = None
        self.connected = False
    
    def connect(self) -> bool:
        """
        建立SSH连接
        返回：连接是否成功
        """
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=self.host,
                port=self.port,
                username=self.username,
                password=self.password,
                timeout=30
            )
            self.connected = True
            return True
        except Exception as e:
            print(f"SSH连接失败: {str(e)}")
            self.connected = False
            return False
    
    def execute_command(self, command: str) -> Tuple[bool, str, str]:
        """
        执行远程命令
        参数：command - 要执行的命令
        返回：(执行是否成功, 标准输出, 标准错误)
        """
        if not self.connected:
            if not self.connect():
                return False, "", "SSH连接失败"
        
        try:
            stdin, stdout, stderr = self.client.exec_command(command, timeout=600)
            stdout_content = stdout.read().decode('utf-8', errors='ignore')
            stderr_content = stderr.read().decode('utf-8', errors='ignore')
            return True, stdout_content, stderr_content
        except Exception as e:
            print(f"执行命令失败: {str(e)}")
            return False, "", str(e)
    
    def close(self):
        """
        关闭SSH连接
        """
        if self.client:
            try:
                self.client.close()
            except:
                pass
            finally:
                self.client = None
                self.connected = False

# 连接池管理
class SSHConnectionPool:
    """SSH连接池管理类"""
    
    def __init__(self):
        self.pool: Dict[str, SSHClient] = {}
    
    def get_connection(self, host: str, port: int = 22, username: str = "user", password: str = "password") -> SSHClient:
        """
        获取SSH连接
        注意：这里使用了默认的用户名和密码，实际使用时需要替换为真实的账户信息
        """
        key = f"{host}:{port}:{username}"
        if key not in self.pool or not self.pool[key].connected:
            client = SSHClient(host, port, username, password)
            client.connect()
            self.pool[key] = client
        return self.pool[key]
    
    def close_all(self):
        """
        关闭所有连接
        """
        for client in self.pool.values():
            client.close()
        self.pool.clear()

# 全局连接池实例
connection_pool = SSHConnectionPool()

def get_connection_pool() -> SSHConnectionPool:
    """
    获取连接池
    """
    return connection_pool
