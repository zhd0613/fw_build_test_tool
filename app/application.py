# 应用程序核心模块
# 功能：
# 1. 协调各个模块的工作流程
# 2. 处理用户输入和系统配置

# 依赖模块：
# - ssh.ssh_client: 用于SSH连接
# - build.build_processor: 用于编译处理
# - file_transfer.file_transfer: 用于文件传输
# - flash.flash_processor: 用于烧卡处理
# - test.test_processor: 用于测试执行
# - llm.error_analyzer: 用于错误分析
# - upload.result_uploader: 用于结果上传
# - config.config: 用于配置管理
import os
import sys
from typing import Tuple, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ssh.ssh_client import get_connection_pool
from build.build_processor import get_build_processor, BuildProcessor
from file_transfer.file_transfer import create_file_transfer
from flash.flash_processor import get_flash_processor, FlashProcessor
from test.test_processor import get_test_processor, TestProcessor
from test.fio_test_processor import FIOTestProcessor
from llm.error_analyzer import get_error_analyzer
from upload.result_uploader import get_result_uploader
from config.config import get_config

class Application:
    """应用程序类"""
    
    def __init__(self, log_callback=None, error_callback=None):
        """
        初始化应用程序
        参数：
            log_callback - 日志回调函数，用于将输出显示到UI界面
            error_callback - 错误回调函数，用于弹出错误弹窗
        """
        self.config = get_config()
        self.build_processor = BuildProcessor(log_callback=self.log if log_callback else None)
        self.flash_processor = FlashProcessor(log_callback=self.log if log_callback else None)
        self.test_processor = TestProcessor(log_callback=self.log if log_callback else None)
        self.fio_test_processor = FIOTestProcessor(self.config, log_callback=self.log if log_callback else None)
        self.error_analyzer = get_error_analyzer()
        self.result_uploader = get_result_uploader()
        self.connection_pool = get_connection_pool()
        self.log_callback = log_callback
        self.error_callback = error_callback
        self.current_step = "编译"
        
        import os
        log_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")
        if not os.path.exists(log_dir):
            os.makedirs(log_dir)
        self.log_dir = log_dir
        self.log_files = {
            "编译": open(os.path.join(log_dir, "build_log.txt"), "w", encoding="utf-8"),
            "烧卡": open(os.path.join(log_dir, "flash_log.txt"), "w", encoding="utf-8"),
            "测试": open(os.path.join(log_dir, "test_log.txt"), "w", encoding="utf-8"),
        }
    
    def log(self, message: str, end: str = "\n"):
        """
        输出日志信息
        参数：
            message - 日志信息
            end - 结尾字符
        """
        print(message, end=end)
        if self.current_step in self.log_files:
            self.log_files[self.current_step].write(message + end)
            self.log_files[self.current_step].flush()
        if self.log_callback:
            self.log_callback(message + end)
    
    def show_error(self, title: str, error_message: str, analysis: str = ""):
        """
        显示错误弹窗
        参数：
            title - 错误标题
            error_message - 错误信息
            analysis - LLM分析结果
        """
        if self.error_callback:
            self.error_callback(title, error_message, analysis)
    
    def _get_stream_callback(self):
        """
        获取LLM流式输出回调函数
        从error_callback所属的UI对象获取流式回调
        """
        if self.error_callback and hasattr(self.error_callback, '__self__'):
            ui_instance = self.error_callback.__self__
            if hasattr(ui_instance, 'get_llm_stream_callback'):
                return ui_instance.get_llm_stream_callback()
        return None
    
    def _show_completion_popup(self, upload_result: bool = False):
        """
        显示测试完成弹窗
        参数：
            upload_result - 是否上传了测试结果
        """
        if self.error_callback and hasattr(self.error_callback, '__self__'):
            ui_instance = self.error_callback.__self__
            if hasattr(ui_instance, 'show_success_popup'):
                if upload_result:
                    ui_instance.show_success_popup(
                        "✅ 测试完成",
                        "测试已完成，结果已上传到数据库。",
                        open_url="http://pbdtweb.memblaze.com:31560/report/index?filter=performance"
                    )
                else:
                    ui_instance.show_success_popup("✅ 测试完成", "测试已完成。")
    
    def set_project_info(self, project_path: str, project_name: str):
        """
        设置项目信息
        参数：
            project_path - 项目路径
            project_name - 项目名
        """
        self.build_processor.set_project_info(project_path, project_name)
    
    def run_build(self):
        """
        执行编译步骤
        返回：(编译是否成功, output路径, 错误信息)
        """
        self.current_step = "编译"
        self.log("开始编译...")
        stop_event = getattr(self, 'stop_event', None)
        build_success, output_path, build_error = self.build_processor.run_build(stop_event=stop_event)
        if not build_success:
            if build_error == "执行已停止":
                return False, None, build_error
            self.log(f"编译失败: {build_error}")
            self.log("[LLM] 正在分析错误...")
            self.show_error("编译失败", build_error)
            stream_callback = self._get_stream_callback()
            error_analysis = self.build_processor.handle_build_error(build_error, stream_callback=stream_callback)
        return build_success, output_path, build_error
    
    def download_output(self, output_path: str):
        """
        下载output文件夹
        参数：
            output_path - 远程output文件夹路径
        返回：(下载是否成功, 本地output目录路径)
        """
        self.log(f"编译成功，output文件夹路径: {output_path}")
        local_output_dir = "./output"
        
        import os
        import shutil
        if os.path.exists(local_output_dir):
            shutil.rmtree(local_output_dir)
            self.log("清空本地output目录")
        os.makedirs(local_output_dir)
        self.log(f"创建本地output目录: {local_output_dir}")
        
        # 获取编译服务器的SSH连接
        build_ssh_client = self.connection_pool.get_connection(
            self.config.get_config("build_server.host"),
            self.config.get_config("build_server.port"),
            self.config.get_config("build_server.username"),
            self.config.get_config("build_server.password")
        )
        
        # 创建文件传输实例
        file_transfer = create_file_transfer(build_ssh_client)
        
        # 下载output文件夹
        self.log("下载output文件夹...")
        download_success = file_transfer.download_directory(output_path, local_output_dir)
        file_transfer.close()
        
        if download_success:
            # 检查本地output目录是否有内容
            if not os.listdir(local_output_dir):
                self.log("本地output目录为空，请检查编译是否正确")
                return False, local_output_dir
            self.log(f"本地output目录包含 {len(os.listdir(local_output_dir))} 个文件")
        else:
            self.log("下载output文件夹失败")
        
        return download_success, local_output_dir
    
    def upload_output(self, local_output_dir: str):
        """
        上传output文件夹到测试服务器
        参数：
            local_output_dir - 本地output目录路径
        返回：上传是否成功
        """
        self.log("上传output文件夹到测试服务器...")
        
        # 获取测试服务器的SSH连接
        test_ssh_client = self.connection_pool.get_connection(
            self.config.get_config("test_server.host"),
            self.config.get_config("test_server.port"),
            self.config.get_config("test_server.username"),
            self.config.get_config("test_server.password")
        )
        
        # 获取测试服务器用户名
        test_server_username = self.config.get_config("test_server.username")
        # 使用绝对路径
        remote_firmware_dir = f"/home/{test_server_username}/firmware"
        remote_output_dir = f"/home/{test_server_username}/firmware/output"
        
        # 确保测试服务器的firmware文件夹存在
        self.log(f"创建测试服务器firmware目录: {remote_firmware_dir}")
        success, stdout, stderr = test_ssh_client.execute_command(f"mkdir -p {remote_firmware_dir}")
        if not success:
            self.log(f"创建firmware文件夹失败: {stderr}")
            return False
        
        # 确保firmware目录有写权限
        self.log(f"设置firmware目录权限: {remote_firmware_dir}")
        success, stdout, stderr = test_ssh_client.execute_command(f"chmod 755 {remote_firmware_dir}")
        if not success:
            self.log(f"设置firmware目录权限失败: {stderr}")
            return False
        
        # 删除旧的output文件夹
        self.log(f"删除旧的output文件夹: {remote_output_dir}")
        success, stdout, stderr = test_ssh_client.execute_command(f"rm -rf {remote_output_dir}")
        if not success:
            self.log(f"删除旧的output文件夹失败: {stderr}")
            # 继续执行，因为可能文件夹不存在
        
        # 创建新的output目录
        self.log(f"创建新的output目录: {remote_output_dir}")
        success, stdout, stderr = test_ssh_client.execute_command(f"mkdir -p {remote_output_dir}")
        if not success:
            self.log(f"创建output目录失败: {stderr}")
            return False
        
        # 确保output目录有写权限
        self.log(f"设置output目录权限: {remote_output_dir}")
        success, stdout, stderr = test_ssh_client.execute_command(f"chmod 755 {remote_output_dir}")
        if not success:
            self.log(f"设置output目录权限失败: {stderr}")
            return False
        
        # 创建文件传输实例
        test_file_transfer = create_file_transfer(test_ssh_client)
        
        # 上传output文件夹
        self.log(f"上传output文件夹到测试服务器: {remote_output_dir}")
        upload_success = test_file_transfer.upload_directory(local_output_dir, remote_output_dir)
        test_file_transfer.close()
        
        if not upload_success:
            self.log("上传output文件夹失败")
        
        return upload_success
    
    def run_flash(self, test_device: str, project_name: str, sku: str, flash_type: str = "ncmt"):
        """
        执行烧卡步骤
        参数：
            test_device - 测试设备标识
            project_name - 项目名
            sku - SKU型号
            flash_type - 烧卡类型 (ncmt / fw download)
        返回：(烧卡是否成功, 错误信息)
        """
        self.current_step = "烧卡"
        self.log("执行烧卡...")
        stop_event = getattr(self, 'stop_event', None)
        flash_success, flash_error = self.flash_processor.run_flash_script(test_device, project_name=project_name, sku=sku, flash_type=flash_type, stop_event=stop_event)
        
        if not flash_success:
            if flash_error == "执行已停止":
                return False, flash_error
            self.log(f"烧卡失败: {flash_error}")
            self.log("[LLM] 正在分析错误...")
            self.show_error("烧卡失败", flash_error)
            stream_callback = self._get_stream_callback()
            error_analysis = self.flash_processor.handle_flash_error(flash_error, stream_callback=stream_callback)
        
        return flash_success, flash_error
    
    def run_test(self, test_script: str, test_device: str = "", sku: str = "", product: str = "", test_case: str = "", other_param: str = "", upload_result: bool = False, version: str = "", extra_scripts: list = None):
        """
        执行测试步骤
        参数：
            test_script - 测试脚本路径
            test_device - 测试设备
            sku - SKU型号
            product - 项目名
            test_case - 测试用例
            other_param - 其他参数
            upload_result - 是否上传测试结果到数据库
            version - 版本号
            extra_scripts - 额外脚本列表，每项为 {"script":..., "case":..., "other_param":...}
        返回：(测试是否成功, 错误信息, 测试结果)
        """
        self.current_step = "测试"
        self.log("执行测试...")
        stop_event = getattr(self, 'stop_event', None)
        test_success, test_error, test_result = self.test_processor.run_test_script(
            test_script, stop_event=stop_event,
            test_device=test_device, sku=sku, product=product,
            test_case=test_case, other_param=other_param,
            upload_result=upload_result, version=version,
            extra_scripts=extra_scripts
        )
        
        if not test_success:
            if test_error == "执行已停止":
                return False, test_error, None
            error_log = test_result.get("error_log", "") if test_result else ""
            self.log(f"测试失败: {test_error}")
            self.log("[LLM] 正在分析错误...")
            self.show_error("测试失败", test_error)
            stream_callback = self._get_stream_callback()
            error_analysis = self.test_processor.handle_test_error(test_error, error_log, stream_callback=stream_callback)
        
        return test_success, test_error, test_result
    
    def upload_result(self, test_result: dict, version: str = ""):
        """
        上传测试结果
        参数：
            test_result - 测试结果
            version - 版本号
        返回：(上传是否成功, 错误信息)
        """
        self.log("上传测试结果...")
        if version:
            test_result["version"] = version
        upload_success, upload_error = self.result_uploader.upload_test_result(test_result)
        
        if not upload_success:
            self.log(f"上传测试结果失败: {upload_error}")
        
        return upload_success, upload_error
    
    def run_fio_test(self, test_device: str, fio_commands: list, stop_event=None) -> Tuple[bool, Optional[str]]:
        """
        执行自定义FIO测试
        参数：
            test_device - 测试设备标识
            fio_commands - FIO命令列表
            stop_event - 停止事件
        返回：(测试是否成功, 错误信息)
        """
        self.current_step = "测试"
        self.log("执行自定义FIO测试...")
        test_success, test_error = self.fio_test_processor.run_fio_test(test_device, fio_commands, stop_event=stop_event)
        
        if not test_success:
            if test_error == "执行已停止":
                return False, test_error
            self.log(f"FIO测试失败: {test_error}")
            self.show_error("FIO测试失败", test_error)
        
        return test_success, test_error
    
    def start_uart_collection(self, test_device: str):
        """
        启动串口日志收集
        参数：
            test_device - 测试设备标识
        """
        import threading
        
        # 启动一个新线程来处理串口收集
        def uart_collection_thread():
            # 为串口收集创建一个单独的SSH连接，不使用连接池
            # 这样就不会被connection_pool.close_all()关闭
            from ssh.ssh_client import SSHClient
            test_ssh_client = SSHClient(
                self.config.get_config("test_server.host"),
                self.config.get_config("test_server.port"),
                self.config.get_config("test_server.username"),
                self.config.get_config("test_server.password")
            )
            
            # 连接到测试服务器
            if not test_ssh_client.connect():
                self.log("无法连接到测试服务器")
                return
            
            # 运行Uart.py --host=xxx命令
            self.log(f"运行Uart.py --host={test_device}...")
            try:
                # 注意：这里需要使用交互式shell来执行命令
                # 由于paramiko的限制，我们需要使用invoke_shell
                channel = test_ssh_client.client.invoke_shell()
                
                if not channel:
                    self.log("无法创建SSH channel")
                    return
                
                # 配置测试环境
                self.log("配置测试环境...")
                channel.send("cd pbdt && setpbdt .\n")
                import time
                
                # 等待测试环境配置完成，检测(pbdt)提示符
                env_output = ""
                max_wait = 30
                wait_time = 0
                while wait_time < max_wait:
                    if channel.recv_ready():
                        output = channel.recv(1024).decode('utf-8')
                        env_output += output
                        if "(pbdt)" in env_output:
                            break
                    time.sleep(0.5)
                    wait_time += 0.5
                else:
                    self.log("等待测试环境配置超时")
                    channel.close()
                    return
                
                # 发送Uart.py命令
                uart_command = f"Uart.py --host={test_device}\n"
                channel.send(uart_command)
                
                # 等待Uart.py启动
                uart_output = ""
                max_wait = 30
                wait_time = 0
                while wait_time < max_wait:
                    if channel.recv_ready():
                        output = channel.recv(1024).decode('utf-8')
                        uart_output += output
                        if "poll" in uart_output.lower() or "Please enter" in uart_output:
                            break
                    time.sleep(0.5)
                    wait_time += 0.5
                
                # 输入p并回车
                channel.send("p\n")
                
                # 读取串口输出，只记录到文件，不打印到终端
                import os
                os.makedirs("logs", exist_ok=True)
                log_file = open("logs/uart_log.txt", "w", encoding='utf-8')
                
                try:
                    while True:
                        if channel.recv_ready():
                            output = channel.recv(1024).decode('utf-8')
                            if output:
                                log_file.write(output)
                                log_file.flush()
                        time.sleep(0.1)
                except Exception as e:
                    self.log(f"串口收集异常: {str(e)}")
                finally:
                    log_file.close()
                    channel.close()
            except Exception as e:
                self.log(f"启动串口收集失败: {str(e)}")
                return
        
        # 启动串口收集线程
        uart_thread = threading.Thread(target=uart_collection_thread)
        uart_thread.daemon = True
        uart_thread.start()
    
    def execute_workflow(self, username: str, test_device: str, test_script: str, project_path: str = "/home/YOUR_USERNAME/firmware/", project_name: str = "YOUR_PROJECT", sku: str = "YOUR_SKU", start_step: str = "编译", collect_uart: bool = True, flash_type: str = "ncmt", stop_event=None, test_case: str = "", other_param: str = "", upload_result: bool = False, version: str = "", test_mode: str = "QA 脚本测试", fio_requirement: str = "", fio_commands: list = None, extra_scripts: list = None):
        """
        执行整个工作流程
        参数：
            username - 用户账号（用于编译和测试服务器）
            test_device - 测试设备标识
            test_script - 测试脚本路径
            project_path - 项目路径
            project_name - 项目名
            sku - SKU型号
            start_step - 开始步骤
            collect_uart - 是否收集串口日志
            flash_type - 烧卡类型
            stop_event - 停止事件
            test_case - 测试用例
            other_param - 其他参数
            upload_result - 是否上传测试结果
            version - 版本号
            test_mode - 测试模式 ("QA 脚本测试" 或 "自定义 FIO 测试")
            fio_requirement - FIO 测试需求（当 test_mode 为 "自定义 FIO 测试" 时有效）
            fio_commands - FIO 命令列表（当 test_mode 为 "自定义 FIO 测试" 时有效）
        """
        self.stop_event = stop_event
        try:
            # 根据用户账号更新config中的username
            self.config.set_config("build_server.username", username)
            self.config.set_config("test_server.username", username)
            
            # 自定义FIO测试流程
            if test_mode == "自定义 FIO 测试":
                self.log("执行自定义FIO测试流程...")
                
                # 设置项目信息
                self.set_project_info(project_path, project_name)
                
                # 执行步骤（与QA流程共享编译/下载/上传/烧卡步骤）
                output_path = None
                local_output_dir = "./output"
                
                # 编译步骤
                if start_step == "编译":
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    build_success, output_path, build_error = self.run_build()
                    if not build_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    download_success, local_output_dir = self.download_output(output_path)
                    if not download_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    upload_success = self.upload_output(local_output_dir)
                    if not upload_success:
                        return False
                    
                    # 启动串口收集
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    flash_success, flash_error = self.run_flash(test_device, project_name, sku, flash_type)
                    if not flash_success:
                        return False
                    
                elif start_step == "下载Output":
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    output_path = f"{project_path}/build/{project_name}/ymtc/release/output/"
                    download_success, local_output_dir = self.download_output(output_path)
                    if not download_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    upload_success = self.upload_output(local_output_dir)
                    if not upload_success:
                        return False
                    
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    flash_success, flash_error = self.run_flash(test_device, project_name, sku, flash_type)
                    if not flash_success:
                        return False
                    
                elif start_step == "上传Output":
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    upload_success = self.upload_output(local_output_dir)
                    if not upload_success:
                        return False
                    
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    flash_success, flash_error = self.run_flash(test_device, project_name, sku, flash_type)
                    if not flash_success:
                        return False
                    
                elif start_step == "烧卡":
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    flash_success, flash_error = self.run_flash(test_device, project_name, sku, flash_type)
                    if not flash_success:
                        return False
                    
                elif start_step == "测试":
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                
                # 执行FIO测试
                if self.stop_event and self.stop_event.is_set():
                    self.log("执行已停止")
                    return False
                
                test_success, test_error = self.run_fio_test(test_device, fio_commands, stop_event=stop_event)
                if not test_success:
                    return False
                
                self.log("自定义FIO测试流程执行完成")
                self._show_completion_popup(upload_result)
                return True
            
            # QA脚本测试流程
            else:
                # 设置项目信息
                self.set_project_info(project_path, project_name)
                
                # 执行步骤
                output_path = None
                local_output_dir = "./output"
                test_result = None
                
                # 编译步骤
                if start_step == "编译":
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    build_success, output_path, build_error = self.run_build()
                    if not build_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 下载Output步骤
                    download_success, local_output_dir = self.download_output(output_path)
                    if not download_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 上传Output步骤
                    upload_success = self.upload_output(local_output_dir)
                    if not upload_success:
                        return False
                    
                    # 启动串口收集
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 烧卡步骤
                    flash_success, flash_error = self.run_flash(test_device, project_name, sku, flash_type)
                    if not flash_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 测试步骤
                    test_success, test_error, test_result = self.run_test(test_script, test_device=test_device, sku=sku, product=project_name, test_case=test_case, other_param=other_param, upload_result=upload_result, version=version, extra_scripts=extra_scripts)
                    if not test_success:
                        return False
                    
                    # 从下载Output开始
                elif start_step == "下载Output":
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 这里需要获取output_path，暂时使用默认路径
                    output_path = f"{project_path}/build/{project_name}/ymtc/release/output/"
                    download_success, local_output_dir = self.download_output(output_path)
                    if not download_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 上传Output步骤
                    upload_success = self.upload_output(local_output_dir)
                    if not upload_success:
                        return False
                    
                    # 启动串口收集
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 烧卡步骤
                    flash_success, flash_error = self.run_flash(test_device, project_name, sku, flash_type)
                    if not flash_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 测试步骤
                    test_success, test_error, test_result = self.run_test(test_script, test_device=test_device, sku=sku, product=project_name, test_case=test_case, other_param=other_param, upload_result=upload_result, version=version, extra_scripts=extra_scripts)
                    if not test_success:
                        return False
                    
                # 从上传Output开始
                elif start_step == "上传Output":
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 上传Output步骤
                    upload_success = self.upload_output(local_output_dir)
                    if not upload_success:
                        return False
                    
                    # 启动串口收集
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 烧卡步骤
                    flash_success, flash_error = self.run_flash(test_device, project_name, sku, flash_type)
                    if not flash_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 测试步骤
                    test_success, test_error, test_result = self.run_test(test_script, test_device=test_device, sku=sku, product=project_name, test_case=test_case, other_param=other_param, upload_result=upload_result, version=version, extra_scripts=extra_scripts)
                    if not test_success:
                        return False
                    
                # 从烧卡开始
                elif start_step == "烧卡":
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    
                    # 启动串口收集
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    # 烧卡步骤
                    flash_success, flash_error = self.run_flash(test_device, project_name, sku, flash_type)
                    if not flash_success:
                        return False
                    
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    # 测试步骤
                    test_success, test_error, test_result = self.run_test(test_script, test_device=test_device, sku=sku, product=project_name, test_case=test_case, other_param=other_param, upload_result=upload_result, version=version, extra_scripts=extra_scripts)
                    if not test_success:
                        return False
                    
                # 从测试开始
                elif start_step == "测试":
                    if self.stop_event and self.stop_event.is_set():
                        self.log("执行已停止")
                        return False
                    
                    # 启动串口收集
                    if collect_uart:
                        self.log("启动串口日志收集...")
                        import threading
                        uart_thread = threading.Thread(target=self.start_uart_collection, args=(test_device,))
                        uart_thread.daemon = True
                        uart_thread.start()
                    
                    # 测试步骤
                    test_success, test_error, test_result = self.run_test(test_script, test_device=test_device, sku=sku, product=project_name, test_case=test_case, other_param=other_param, upload_result=upload_result, version=version, extra_scripts=extra_scripts)
                    if not test_success:
                        return False
                    
                self.log("工作流程执行完成")
                self._show_completion_popup(upload_result)
                return True
        except Exception as e:
            self.handle_exception(e)
            return False
        finally:
            # 清理资源
            self.connection_pool.close_all()
    
    def handle_exception(self, exception: Exception):
        """
        处理异常
        参数：exception - 异常对象
        """
        self.log(f"发生异常: {str(exception)}")
        # 这里可以添加更详细的异常处理逻辑，比如日志记录等