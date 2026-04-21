# 文件传输模块
# 功能：
# 1. 从编译服务器下载output文件
# 2. 上传文件到测试服务器
# 3. 监控文件传输进度
# 4. 处理文件传输异常

# 依赖模块：
# - ssh.ssh_client: 用于SSH连接和文件传输
import paramiko
import os
from typing import Optional, Callable
from ssh.ssh_client import SSHClient

class FileTransfer:
    """封装文件传输的类"""
    
    def __init__(self, ssh_client: SSHClient):
        """
        初始化文件传输
        参数：ssh_client - SSH客户端实例
        """
        self.ssh_client = ssh_client
        self.sftp = None
        self.transfer_progress = 0
    
    def _get_sftp(self) -> Optional[paramiko.SFTPClient]:
        """
        获取SFTP客户端
        返回：SFTP客户端实例
        """
        if not self.sftp:
            try:
                if not self.ssh_client.connected:
                    if not self.ssh_client.connect():
                        return None
                self.sftp = self.ssh_client.client.open_sftp()
            except Exception as e:
                print(f"创建SFTP客户端失败: {str(e)}")
                return None
        return self.sftp
    
    def _progress_callback(self, current: int, total: int):
        """
        传输进度回调函数
        参数：
            current - 当前传输的字节数
            total - 总字节数
        """
        if total > 0:
            self.transfer_progress = int((current / total) * 100)
            # 可以在这里添加进度更新的逻辑，比如回调函数
    
    def download_file(self, remote_path: str, local_path: str) -> bool:
        """
        从远程服务器下载文件
        参数：
            remote_path - 远程文件路径
            local_path - 本地文件路径
        返回：下载是否成功
        """
        sftp = self._get_sftp()
        if not sftp:
            return False
        
        try:
            # 确保本地目录存在
            local_dir = os.path.dirname(local_path)
            if local_dir and not os.path.exists(local_dir):
                os.makedirs(local_dir)
            
            # 下载文件
            sftp.get(remote_path, local_path, callback=self._progress_callback)
            return True
        except Exception as e:
            print(f"下载文件失败: {str(e)}")
            self.handle_transfer_error(e)
            return False
    
    def upload_file(self, local_path: str, remote_path: str) -> bool:
        """
        上传文件到远程服务器
        参数：
            local_path - 本地文件路径
            remote_path - 远程文件路径
        返回：上传是否成功
        """
        sftp = self._get_sftp()
        if not sftp:
            return False
        
        try:
            # 确保远程目录存在
            remote_dir = os.path.dirname(remote_path)
            if remote_dir:
                try:
                    sftp.stat(remote_dir)
                except FileNotFoundError:
                    # 创建远程目录
                    self._create_remote_directory(sftp, remote_dir)
            
            # 上传文件
            sftp.put(local_path, remote_path, callback=self._progress_callback)
            return True
        except Exception as e:
            print(f"上传文件失败: {str(e)}")
            self.handle_transfer_error(e)
            return False
    
    def download_directory(self, remote_dir: str, local_dir: str) -> bool:
        """
        下载远程目录到本地
        参数：
            remote_dir - 远程目录路径
            local_dir - 本地目录路径
        返回：下载是否成功
        """
        sftp = self._get_sftp()
        if not sftp:
            return False
        
        try:
            # 确保本地目录存在
            if not os.path.exists(local_dir):
                os.makedirs(local_dir)
            
            # 下载目录中的所有文件
            self._download_directory_recursive(sftp, remote_dir, local_dir)
            return True
        except Exception as e:
            print(f"下载目录失败: {str(e)}")
            self.handle_transfer_error(e)
            return False
    
    def _download_directory_recursive(self, sftp: paramiko.SFTPClient, remote_dir: str, local_dir: str):
        """
        递归下载目录
        参数：
            sftp - SFTP客户端实例
            remote_dir - 远程目录路径
            local_dir - 本地目录路径
        """
        remote_dir = remote_dir.rstrip('/')
        try:
            entries = sftp.listdir_attr(remote_dir)
        except Exception as e:
            print(f"列出远程目录失败 {remote_dir}: {str(e)}")
            return

        for file_attr in entries:
            remote_path = f"{remote_dir}/{file_attr.filename}"
            local_path = os.path.join(local_dir, file_attr.filename)

            is_dir = False
            if hasattr(file_attr, 'st_mode') and file_attr.st_mode is not None:
                is_dir = bool(file_attr.st_mode & 0o040000)
            else:
                try:
                    sftp.stat(remote_path)
                    is_dir = True
                except:
                    is_dir = False

            if is_dir:
                if not os.path.exists(local_path):
                    os.makedirs(local_path)
                self._download_directory_recursive(sftp, remote_path, local_path)
            else:
                try:
                    sftp.get(remote_path, local_path, callback=self._progress_callback)
                except Exception as e:
                    print(f"下载文件失败 {remote_path}: {str(e)}")
    
    def upload_directory(self, local_dir: str, remote_dir: str) -> bool:
        """
        上传本地目录到远程服务器
        参数：
            local_dir - 本地目录路径
            remote_dir - 远程目录路径
        返回：上传是否成功
        """
        sftp = self._get_sftp()
        if not sftp:
            return False
        
        try:
            # 确保远程目录存在
            try:
                sftp.stat(remote_dir)
            except FileNotFoundError:
                # 创建远程目录
                self._create_remote_directory(sftp, remote_dir)
            
            # 上传目录中的所有文件
            self._upload_directory_recursive(sftp, local_dir, remote_dir)
            return True
        except Exception as e:
            print(f"上传目录失败: {str(e)}")
            self.handle_transfer_error(e)
            return False
    
    def _upload_directory_recursive(self, sftp: paramiko.SFTPClient, local_dir: str, remote_dir: str):
        """
        递归上传目录
        参数：
            sftp - SFTP客户端实例
            local_dir - 本地目录路径
            remote_dir - 远程目录路径
        """
        for root, dirs, files in os.walk(local_dir):
            # 计算相对路径
            rel_path = os.path.relpath(root, local_dir)
            if rel_path == '.':
                current_remote_dir = remote_dir
            else:
                current_remote_dir = f"{remote_dir}/{rel_path}"
            
            # 创建远程子目录
            for dir_name in dirs:
                remote_subdir = f"{current_remote_dir}/{dir_name}"
                try:
                    sftp.stat(remote_subdir)
                except FileNotFoundError:
                    sftp.mkdir(remote_subdir)
            
            # 上传文件
            for file_name in files:
                local_path = os.path.join(root, file_name)
                remote_path = f"{current_remote_dir}/{file_name}"
                sftp.put(local_path, remote_path, callback=self._progress_callback)
    
    def _create_remote_directory(self, sftp: paramiko.SFTPClient, path: str):
        """
        创建远程目录
        参数：
            sftp - SFTP客户端实例
            path - 远程目录路径
        """
        parts = path.split('/')
        current_path = ''
        for part in parts:
            if not part:
                continue
            current_path += f"/{part}"
            try:
                sftp.stat(current_path)
            except FileNotFoundError:
                sftp.mkdir(current_path)
    
    def get_transfer_progress(self) -> int:
        """
        获取传输进度
        返回：传输进度百分比（0-100）
        """
        return self.transfer_progress
    
    def handle_transfer_error(self, error: Exception):
        """
        处理传输错误
        参数：error - 错误异常
        """
        # 这里可以添加错误处理逻辑，比如日志记录、重试等
        pass
    
    def close(self):
        """
        关闭SFTP连接
        """
        if self.sftp:
            try:
                self.sftp.close()
            except:
                pass
            finally:
                self.sftp = None

def create_file_transfer(ssh_client: SSHClient) -> FileTransfer:
    """
    创建文件传输实例
    参数：ssh_client - SSH客户端实例
    返回：FileTransfer实例
    """
    return FileTransfer(ssh_client)
