# 主程序
# 功能：
# 1. 作为整个项目的入口点
# 2. 协调各个模块的工作流程
# 3. 处理用户输入和系统配置
# 4. 启动UI界面

# 依赖模块：
# - ui.main_ui: 用于创建UI界面
# - ssh.ssh_client: 用于SSH连接
# - build.build_processor: 用于编译处理
# - file_transfer.file_transfer: 用于文件传输
# - flash.flash_processor: 用于烧卡处理
# - test.test_processor: 用于测试执行
# - llm.error_analyzer: 用于错误分析
# - upload.result_uploader: 用于结果上传
# - config.config: 用于配置管理
import os
from ui.main_ui import run_ui
from app.application import Application

def main():
    """
    主函数
    """
    # 创建应用程序实例
    app = Application()
    
    # 启动UI界面
    run_ui()

if __name__ == "__main__":
    main()
