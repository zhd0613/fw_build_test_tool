# UI界面模块

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
from typing import Optional, Dict


class MainUI:
    """主界面类"""

    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("代码编译测试工具")
        self.root.geometry("800x650")
        self.root.minsize(700, 550)

        self.config_file = "ui_config.json"
        self.execution_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self.script_name_to_path: Dict[str, str] = {}
        self.script_names: list = []
        self.script_listbox = None
        self.script_listbox_visible = False

        self._output_buffer = []
        self._output_buffer_lock = threading.Lock()
        self._output_flush_running = False
        self._execution_running = False

        self.create_input_fields()
        self.create_buttons()
        self.create_output_area()
        self.create_progress_bar()
        self.load_config()
        self.fetch_test_scripts()

    def create_input_fields(self):
        input_frame = ttk.LabelFrame(self.root, text="配置信息", padding=8)
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        # row=0: 用户账号
        ttk.Label(input_frame, text="用户账号:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=3)
        self.username_entry = ttk.Entry(input_frame, width=50)
        self.username_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=3)
        self.username_entry.insert(0, "")

        # row=1: 编译路径
        ttk.Label(input_frame, text="编译路径:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=3)
        self.project_path_entry = ttk.Entry(input_frame, width=50)
        self.project_path_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=3)
        self.project_path_entry.insert(0, "/home/YOUR_USERNAME/firmware/")

        # row=2: 测试机 + 项目名 + SKU
        ttk.Label(input_frame, text="测试机:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=3)
        row2_frame = ttk.Frame(input_frame)
        row2_frame.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=3)

        self.test_device_entry = ttk.Entry(row2_frame, width=16)
        self.test_device_entry.pack(side=tk.LEFT, padx=(0, 8))
        self.test_device_entry.insert(0, "device1")

        ttk.Label(row2_frame, text="项目名:").pack(side=tk.LEFT, padx=(12, 0))
        self.project_name_var = tk.StringVar()
        self.project_name_combobox = ttk.Combobox(row2_frame, textvariable=self.project_name_var, width=14)
        self.project_name_combobox.pack(side=tk.LEFT, padx=(0, 8))
        self.project_name_combobox['values'] = ('goji', 'baiji')
        self.project_name_combobox.current(0)

        ttk.Label(row2_frame, text="SKU:").pack(side=tk.LEFT, padx=(12, 0))
        self.sku_var = tk.StringVar()
        self.sku_combobox = ttk.Combobox(row2_frame, textvariable=self.sku_var, width=10)
        self.sku_combobox.pack(side=tk.LEFT, padx=(0, 4))
        self.sku_combobox['values'] = ('ut320', 'ut384', 'ut640', 'ut768', 'ut1280', 'ut1536', 'ut3072', 'ut6144')
        self.sku_combobox.current(3)

        self.ss_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row2_frame, text="SS开卡", variable=self.ss_var).pack(side=tk.LEFT, padx=(4, 4))

        self.ddr_var = tk.StringVar(value="ddr4")
        ddr_frame = ttk.Frame(row2_frame)
        ddr_frame.pack(side=tk.LEFT)
        ttk.Radiobutton(ddr_frame, text="DDR4", variable=self.ddr_var, value="ddr4").pack(side=tk.LEFT)
        ttk.Radiobutton(ddr_frame, text="DDR5", variable=self.ddr_var, value="ddr5").pack(side=tk.LEFT)

        # row=3: 测试模式
        ttk.Label(input_frame, text="测试模式:").grid(row=3, column=0, sticky=tk.W, padx=5, pady=3)
        test_mode_frame = ttk.Frame(input_frame)
        test_mode_frame.grid(row=3, column=1, sticky=tk.W, padx=5, pady=3)
        self.test_mode_var = tk.StringVar(value="QA 脚本测试")
        ttk.Radiobutton(test_mode_frame, text="QA 脚本测试", variable=self.test_mode_var,
                       value="QA 脚本测试", command=self._on_test_mode_change).pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(test_mode_frame, text="自定义 FIO 测试", variable=self.test_mode_var,
                       value="自定义 FIO 测试", command=self._on_test_mode_change).pack(side=tk.LEFT)

        # row=4: 测试脚本多行区域（QA模式显示）
        self.test_script_label = ttk.Label(input_frame, text="测试脚本:")
        self.test_script_label.grid(row=4, column=0, sticky=tk.NW, padx=5, pady=3)

        self.script_rows_frame = ttk.Frame(input_frame)
        self.script_rows_frame.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=3)

        self.script_rows = []
        self._add_script_row(is_first=True)

        # row=4: FIO 测试需求输入框（FIO模式显示，初始隐藏）
        self.fio_requirement_label = ttk.Label(input_frame, text="测试需求:")
        self.fio_requirement_label.grid(row=4, column=0, sticky=tk.W, padx=5, pady=3)

        self.fio_requirement_frame = ttk.Frame(input_frame)
        self.fio_requirement_frame.grid(row=4, column=1, sticky=tk.EW, padx=5, pady=3)

        self.fio_requirement_entry = ttk.Entry(self.fio_requirement_frame, width=50)
        self.fio_requirement_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 8))
        self.fio_requirement_entry.insert(0, "请描述您的 FIO 测试需求，例如：顺序读写测试，块大小 128k")

        # 初始隐藏 FIO 相关控件
        self.fio_requirement_label.grid_remove()
        self.fio_requirement_frame.grid_remove()

        # row=5: 烧卡类型
        ttk.Label(input_frame, text="烧卡类型:").grid(row=5, column=0, sticky=tk.W, padx=5, pady=3)
        self.flash_type_var = tk.StringVar(value="ncmt")
        flash_type_frame = ttk.Frame(input_frame)
        flash_type_frame.grid(row=5, column=1, sticky=tk.W, padx=5, pady=3)
        ttk.Radiobutton(flash_type_frame, text="NCMT", variable=self.flash_type_var, value="ncmt").pack(side=tk.LEFT, padx=(0, 15))
        ttk.Radiobutton(flash_type_frame, text="FW Download", variable=self.flash_type_var, value="fw download").pack(side=tk.LEFT)

        # row=6: 收集串口日志
        ttk.Label(input_frame, text="收集串口日志:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=3)
        self.collect_uart_var = tk.BooleanVar()
        self.collect_uart_check = ttk.Checkbutton(input_frame, variable=self.collect_uart_var, text="是")
        self.collect_uart_check.grid(row=6, column=1, sticky=tk.W, padx=5, pady=3)
        self.collect_uart_var.set(True)

        # row=7: 上传测试结果
        ttk.Label(input_frame, text="上传测试结果:").grid(row=7, column=0, sticky=tk.W, padx=5, pady=3)
        upload_result_frame = ttk.Frame(input_frame)
        upload_result_frame.grid(row=7, column=1, sticky=tk.W, padx=5, pady=3)
        self.upload_result_var = tk.BooleanVar()
        ttk.Radiobutton(upload_result_frame, text="是", variable=self.upload_result_var, value=True, command=self._on_upload_result_toggle).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(upload_result_frame, text="否", variable=self.upload_result_var, value=False, command=self._on_upload_result_toggle).pack(side=tk.LEFT)
        self.upload_result_var.set(False)

        # row=8: 版本号
        ttk.Label(input_frame, text="版本号:").grid(row=8, column=0, sticky=tk.W, padx=5, pady=3)
        self.version_entry = ttk.Entry(input_frame, width=50)
        self.version_entry.grid(row=8, column=1, sticky=tk.EW, padx=5, pady=3)
        self.version_entry.insert(0, "")
        self.version_entry.config(state=tk.DISABLED)

        input_frame.columnconfigure(1, weight=1)

    def _on_upload_result_toggle(self):
        if self.upload_result_var.get():
            self.version_entry.config(state=tk.NORMAL)
        else:
            self.version_entry.config(state=tk.DISABLED)

    def _create_script_listbox(self):
        """
        创建浮动搜索结果列表
        """
        if self.script_listbox is not None:
            return

        self.script_listbox = tk.Listbox(self.root, height=8, font=("Consolas", 10))
        self.script_listbox.bind('<<ListboxSelect>>', self._on_script_select)
        self.script_listbox.bind('<Leave>', lambda e: self._hide_script_listbox())

    def _show_script_listbox(self, names):
        """
        显示搜索结果列表
        """
        if not names:
            self._hide_script_listbox()
            return

        self._create_script_listbox()

        self.script_listbox.delete(0, tk.END)
        for name in names:
            self.script_listbox.insert(tk.END, name)

        entry_widget = self.test_script_entry
        x = entry_widget.winfo_rootx() - self.root.winfo_rootx()
        y = entry_widget.winfo_rooty() - self.root.winfo_rooty() + entry_widget.winfo_height()
        w = entry_widget.winfo_width()

        self.script_listbox.place(x=x, y=y, width=w)
        self.script_listbox.lift()
        self.script_listbox_visible = True

    def _hide_script_listbox(self):
        """
        隐藏搜索结果列表
        """
        if self.script_listbox is not None and self.script_listbox_visible:
            self.script_listbox.place_forget()
            self.script_listbox_visible = False

    def _on_script_select(self, event):
        """
        从列表中选择一个脚本
        """
        selection = self.script_listbox.curselection()
        if not selection:
            return
        selected_name = self.script_listbox.get(selection[0])
        self.test_script_entry.delete(0, tk.END)
        self.test_script_entry.insert(0, selected_name)
        self._hide_script_listbox()
        self.test_script_entry.focus_set()
        self.test_script_entry.icursor(tk.END)

    def _on_test_script_search(self, event):
        """
        用户输入时实时过滤并显示搜索结果
        """
        if event.keysym in ('Up', 'Down', 'Left', 'Right', 'Shift_L', 'Shift_R', 'Control_L', 'Control_R', 'Alt_L', 'Alt_R'):
            return

        current_text = self.test_script_entry.get()

        if not current_text:
            self._show_script_listbox(self.script_names)
            return

        keyword = current_text.lower()
        filtered = [n for n in self.script_names if keyword in n.lower()]
        self._show_script_listbox(filtered)

    def _on_test_script_focus_out(self, event):
        """
        输入框失去焦点时延迟隐藏列表（留时间给点击选择）
        """
        self.root.after(200, self._hide_script_listbox)

    def _on_test_script_enter(self, event):
        """
        按回车时，如果列表有选中项则选择它
        """
        if self.script_listbox_visible and self.script_listbox is not None:
            selection = self.script_listbox.curselection()
            if selection:
                self._on_script_select(None)
                return "break"
        self._hide_script_listbox()

    def _on_test_script_up(self, event):
        """
        按上箭头在列表中移动
        """
        if self.script_listbox_visible and self.script_listbox is not None:
            selection = self.script_listbox.curselection()
            if selection:
                idx = selection[0]
                if idx > 0:
                    self.script_listbox.selection_clear(idx)
                    self.script_listbox.selection_set(idx - 1)
                    self.script_listbox.see(idx - 1)
            else:
                self.script_listbox.selection_set(tk.END)
                self.script_listbox.see(tk.END)
            return "break"

    def _on_test_script_down(self, event):
        """
        按下箭头在列表中移动
        """
        if self.script_listbox_visible and self.script_listbox is not None:
            selection = self.script_listbox.curselection()
            if selection:
                idx = selection[0]
                if idx < self.script_listbox.size() - 1:
                    self.script_listbox.selection_clear(idx)
                    self.script_listbox.selection_set(idx + 1)
                    self.script_listbox.see(idx + 1)
            else:
                self.script_listbox.selection_set(0)
                self.script_listbox.see(0)
            return "break"

    def _add_script_row(self, is_first=False):
        row_frame = ttk.Frame(self.script_rows_frame)
        row_frame.pack(fill=tk.X, pady=1)

        script_entry = ttk.Entry(row_frame, width=28)
        script_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 4))
        if is_first:
            script_entry.bind('<KeyRelease>', self._on_test_script_search)
            script_entry.bind('<FocusOut>', self._on_test_script_focus_out)
            script_entry.bind('<Return>', self._on_test_script_enter)
            script_entry.bind('<Up>', self._on_test_script_up)
            script_entry.bind('<Down>', self._on_test_script_down)

        ttk.Label(row_frame, text="Case:").pack(side=tk.LEFT, padx=(4, 0))
        case_entry = ttk.Entry(row_frame, width=10)
        case_entry.pack(side=tk.LEFT, padx=(0, 4))
        case_entry.insert(0, "all")

        ttk.Label(row_frame, text="Other:").pack(side=tk.LEFT, padx=(4, 0))
        other_entry = ttk.Entry(row_frame, width=10)
        other_entry.pack(side=tk.LEFT, padx=(0, 4))
        other_entry.insert(0, "null")

        add_btn = ttk.Button(row_frame, text="+", width=3,
                             command=lambda: self._add_script_row())
        add_btn.pack(side=tk.LEFT, padx=(2, 0))

        remove_btn = None
        if not is_first:
            remove_btn = ttk.Button(row_frame, text="-", width=3,
                                    command=lambda rf=row_frame: self._remove_script_row(rf))
            remove_btn.pack(side=tk.LEFT, padx=(2, 0))

        row_data = {
            "frame": row_frame,
            "script_entry": script_entry,
            "case_entry": case_entry,
            "other_entry": other_entry,
            "add_btn": add_btn,
            "remove_btn": remove_btn
        }
        self.script_rows.append(row_data)

        if is_first:
            self.test_script_entry = script_entry

    def _remove_script_row(self, row_frame):
        for i, row_data in enumerate(self.script_rows):
            if row_data["frame"] is row_frame:
                row_frame.destroy()
                self.script_rows.pop(i)
                break

    def _on_test_mode_change(self):
        if self.test_mode_var.get() == "自定义 FIO 测试":
            self.test_script_label.grid_remove()
            self.script_rows_frame.grid_remove()

            self.fio_requirement_label.grid()
            self.fio_requirement_frame.grid()

            self.upload_result_var.set(False)
            self._on_upload_result_toggle()
        else:
            self.test_script_label.grid()
            self.script_rows_frame.grid()

            self.fio_requirement_label.grid_remove()
            self.fio_requirement_frame.grid_remove()

    def create_buttons(self):
        button_frame = ttk.Frame(self.root)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(button_frame, text="从步骤开始:").pack(side=tk.LEFT, padx=5)
        self.start_step_var = tk.StringVar()
        self.start_step_combobox = ttk.Combobox(button_frame, textvariable=self.start_step_var, width=16)
        self.start_step_combobox['values'] = ('编译', '下载Output', '上传Output', '烧卡', '测试')
        self.start_step_combobox.current(0)
        self.start_step_combobox.pack(side=tk.LEFT, padx=5)

        self.start_button = ttk.Button(button_frame, text="开始执行", command=self.start_execution)
        self.start_button.pack(side=tk.LEFT, padx=5)

        self.stop_button = ttk.Button(button_frame, text="停止执行", command=self.stop_execution, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)

        self.ai_config_button = ttk.Button(button_frame, text="配置AI模型信息", command=self.show_ai_config_popup)
        self.ai_config_button.pack(side=tk.LEFT, padx=5)

    def create_output_area(self):
        output_frame = ttk.LabelFrame(self.root, text="执行输出", padding=5)
        output_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.output_text = scrolledtext.ScrolledText(output_frame, wrap=tk.WORD, height=16,
                                                       font=("Consolas", 10))
        self.output_text.pack(fill=tk.BOTH, expand=True)
        self.output_text.config(state=tk.DISABLED)

        self.output_text.tag_configure("error", foreground="red")
        self.output_text.tag_configure("success", foreground="green")
        self.output_text.tag_configure("info", foreground="blue")
        self.output_text.tag_configure("warning", foreground="orange")

    def create_progress_bar(self):
        progress_frame = ttk.Frame(self.root)
        progress_frame.pack(fill=tk.X, padx=10, pady=5)

        self.progress_bar = ttk.Progressbar(progress_frame, orient=tk.HORIZONTAL,
                                              length=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, padx=5)

        self.progress_label = ttk.Label(progress_frame, text="准备就绪")
        self.progress_label.pack(side=tk.LEFT, padx=5)

    def start_execution(self):
        self.save_config()
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.stop_event.clear()
        self._execution_running = True

        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)

        self.execution_thread = threading.Thread(target=self._execute_workflow)
        self.execution_thread.daemon = True
        self.execution_thread.start()

    def stop_execution(self):
        self.stop_event.set()
        self.stop_button.config(state=tk.DISABLED)

    def _execute_workflow(self):
        from app.application import Application

        username = self.username_entry.get()
        test_device = self.test_device_entry.get()
        test_mode = self.test_mode_var.get()
        fio_requirement = self.fio_requirement_entry.get() if test_mode == "自定义 FIO 测试" else ""
        project_path = self.project_path_entry.get()
        project_name = self.project_name_var.get()
        sku_base = self.sku_var.get()
        ss_suffix = "-ss" if self.ss_var.get() else ""
        ddr_suffix = f"-{self.ddr_var.get()}"
        sku = f"{sku_base}{ss_suffix}{ddr_suffix}"
        start_step = self.start_step_var.get()
        collect_uart = self.collect_uart_var.get()
        flash_type = self.flash_type_var.get()
        upload_result = self.upload_result_var.get()
        version = self.version_entry.get() if upload_result else ""

        script_list = []
        if test_mode == "QA 脚本测试":
            for row_data in self.script_rows:
                s = row_data["script_entry"].get().strip()
                c = row_data["case_entry"].get().strip()
                o = row_data["other_entry"].get().strip()
                if s:
                    script_list.append({
                        "script": self._resolve_test_script(s, username),
                        "case": c,
                        "other_param": o
                    })

        test_script = script_list[0]["script"] if script_list else ""
        test_case = script_list[0]["case"] if script_list else ""
        other_param = script_list[0]["other_param"] if script_list else ""
        extra_scripts = script_list[1:] if len(script_list) > 1 else []

        app = Application(log_callback=self.update_output, error_callback=self.show_error_popup)

        try:
            if self.stop_event.is_set():
                self.update_output("执行已停止\n")
                return

            if test_mode == "自定义 FIO 测试":
                # 生成FIO命令
                self.update_output("正在生成FIO命令...\n")
                self.update_progress(20, "生成FIO命令")
                
                # 调用FIO命令生成器
                success, error, fio_commands = app.fio_test_processor.generate_fio_commands(fio_requirement)
                
                if not success:
                    self.update_output(f"生成FIO命令失败: {error}\n")
                    self.update_progress(100, "执行失败")
                    return
                
                # 显示命令确认弹窗
                self.update_progress(40, "确认FIO命令")
                confirmed, fio_commands = self.show_fio_commands_popup(fio_commands)
                
                if not confirmed:
                    self.update_output("用户取消执行FIO测试\n")
                    self.update_progress(100, "执行取消")
                    return
                
                # 执行FIO测试
                self.update_progress(60, "执行FIO测试")
                success = app.execute_workflow(username, test_device, test_script,
                                              project_path, project_name, sku, start_step, collect_uart, flash_type, 
                                              self.stop_event, test_case, other_param, upload_result, version, 
                                              test_mode, fio_requirement, fio_commands, extra_scripts=[])
            else:
                # QA脚本测试流程
                success = app.execute_workflow(username, test_device, test_script,
                                              project_path, project_name, sku, start_step, collect_uart, flash_type, 
                                              self.stop_event, test_case, other_param, upload_result, version, 
                                              test_mode, fio_requirement, extra_scripts=extra_scripts)

            if success:
                self.update_progress(100, "执行完成")
            else:
                self.update_progress(100, "执行失败")
        except Exception as e:
            self.update_progress(100, "执行失败")
            self.update_output(f"执行过程中发生错误: {str(e)}\n")
        finally:
            self._execution_running = False
            self.root.after(0, lambda: self.start_button.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))

    def _resolve_test_script(self, script_input: str, username: str) -> str:
        """
        解析测试脚本
        测试脚本只需要文件名，不需要完整路径
        """
        if not script_input:
            return script_input

        if '/' in script_input:
            return script_input.split('/')[-1]

        return script_input

    def update_output(self, text: str):
        with self._output_buffer_lock:
            self._output_buffer.append(text)
        if not self._output_flush_running:
            self._output_flush_running = True
            self.root.after(50, self._flush_output_buffer)

    def _flush_output_buffer(self):
        from datetime import datetime
        with self._output_buffer_lock:
            items = self._output_buffer[:]
            self._output_buffer.clear()
        if items:
            self.output_text.config(state=tk.NORMAL)
            combined = "".join(items)
            if self._execution_running:
                now = datetime.now()
                ts = now.strftime("[%Y %#m/%#d %H:%M:%S] ")
                lines = combined.split('\n')
                timestamped_lines = []
                for line in lines:
                    if line.strip():
                        timestamped_lines.append(ts + line)
                    else:
                        timestamped_lines.append('')
                combined = '\n'.join(timestamped_lines)
            tag = None
            lower = combined.lower()
            if "error" in lower or "失败" in lower or "failed" in lower:
                tag = "error"
            elif "成功" in lower or "success" in lower or "完成" in lower:
                tag = "success"
            elif "warning" in lower or "警告" in lower:
                tag = "warning"
            elif "[llm]" in lower or "分析" in lower:
                tag = "info"
            if tag:
                self.output_text.insert(tk.END, combined, tag)
            else:
                self.output_text.insert(tk.END, combined)
            self.output_text.see(tk.END)
            self.output_text.config(state=tk.DISABLED)
        with self._output_buffer_lock:
            if self._output_buffer:
                self.root.after(50, self._flush_output_buffer)
            else:
                self._output_flush_running = False

    def show_error_popup(self, title: str, error_message: str, analysis: str = ""):
        """
        显示错误弹窗，并返回一个流式回调函数用于LLM分析输出
        """
        self._popup_analysis_text = None

        def _show():
            popup = tk.Toplevel(self.root)
            popup.title(f"⚠ {title}")
            popup.geometry("700x500")
            popup.attributes('-topmost', True)
            popup.focus_force()
            popup.bell()

            ttk.Label(popup, text=f"⚠ {title}", font=("Arial", 14, "bold"),
                       foreground="red").pack(padx=10, pady=10, anchor=tk.W)

            error_frame = ttk.LabelFrame(popup, text="错误信息")
            error_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            error_text = tk.Text(error_frame, height=8, wrap=tk.WORD, fg="red")
            error_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            error_text.insert(tk.END, error_message)
            error_text.config(state=tk.DISABLED)

            analysis_frame = ttk.LabelFrame(popup, text="LLM分析结果")
            analysis_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            analysis_text = tk.Text(analysis_frame, height=10, wrap=tk.WORD, fg="black")
            analysis_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            analysis_text.insert(tk.END, "正在分析中...\n")
            self._popup_analysis_text = analysis_text

            ttk.Button(popup, text="确定", command=popup.destroy).pack(pady=10)

            popup.grab_set()

        self.root.after(0, _show)

    def show_success_popup(self, title: str, message: str, open_url: str = ""):
        """
        显示成功提示弹窗（非阻塞）
        参数：
            title - 标题
            message - 提示信息
            open_url - 需要打开的网页URL，为空则不打开
        """
        def _show():
            popup = tk.Toplevel(self.root)
            popup.title(title)
            popup.geometry("450x180")
            popup.attributes('-topmost', True)
            popup.focus_force()
            popup.bell()

            ttk.Label(popup, text=title, font=("Arial", 14, "bold"),
                       foreground="green").pack(padx=10, pady=10, anchor=tk.W)

            ttk.Label(popup, text=message, font=("Arial", 11),
                       wraplength=400).pack(padx=10, pady=5, anchor=tk.W)

            if open_url:
                import webbrowser
                webbrowser.open(open_url)

            ttk.Button(popup, text="确定", command=popup.destroy).pack(pady=10)

        self.root.after(0, _show)

    def show_ai_config_popup(self):
        """
        显示 AI 模型配置弹窗，可修改 API Key、模型名称、API 地址
        """
        from config.config import get_config
        config = get_config()

        popup = tk.Toplevel(self.root)
        popup.title("配置AI模型信息")
        popup.geometry("550x280")
        popup.attributes('-topmost', True)
        popup.focus_force()
        popup.resizable(False, False)

        config_frame = ttk.LabelFrame(popup, text="LLM 模型配置", padding=10)
        config_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=10)

        ttk.Label(config_frame, text="API 地址:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=8)
        api_url_entry = ttk.Entry(config_frame, width=50)
        api_url_entry.grid(row=0, column=1, sticky=tk.EW, padx=5, pady=8)
        api_url_entry.insert(0, config.get_config("llm.api_url", ""))

        ttk.Label(config_frame, text="API 密钥:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=8)
        api_key_entry = ttk.Entry(config_frame, width=50)
        api_key_entry.grid(row=1, column=1, sticky=tk.EW, padx=5, pady=8)
        api_key_entry.insert(0, config.get_config("llm.api_key", ""))

        ttk.Label(config_frame, text="模型名称:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=8)
        model_entry = ttk.Entry(config_frame, width=50)
        model_entry.grid(row=2, column=1, sticky=tk.EW, padx=5, pady=8)
        model_entry.insert(0, config.get_config("llm.model", ""))

        config_frame.columnconfigure(1, weight=1)

        button_frame = ttk.Frame(popup)
        button_frame.pack(pady=10)

        def on_save():
            config.set_config("llm.api_url", api_url_entry.get())
            config.set_config("llm.api_key", api_key_entry.get())
            config.set_config("llm.model", model_entry.get())
            config.save_config()
            popup.destroy()

        def on_cancel():
            popup.destroy()

        ttk.Button(button_frame, text="保存", command=on_save).pack(side=tk.LEFT, padx=10)
        ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=10)

        popup.grab_set()

    def show_fio_commands_popup(self, fio_commands: list) -> tuple:
        """
        显示 FIO 命令确认弹窗，用户可编辑命令内容
        参数：
            fio_commands - FIO 命令列表
        返回：(是否确认, 编辑后的命令列表)
        """
        result = {"confirmed": False, "commands": fio_commands}
        
        def _show():
            popup = tk.Toplevel(self.root)
            popup.title("确认 FIO 测试命令")
            popup.geometry("750x450")
            popup.attributes('-topmost', True)
            popup.focus_force()
            popup.bell()

            ttk.Label(popup, text="请确认以下 FIO 测试命令（可直接编辑修改）：", font=("Arial", 12, "bold")).pack(padx=10, pady=10, anchor=tk.W)

            # 创建可编辑的文本框显示命令
            commands_frame = ttk.LabelFrame(popup, text="FIO 命令列表（每条命令一行，可直接修改）")
            commands_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

            commands_text = tk.Text(commands_frame, height=18, wrap=tk.CHAR, fg="black", font=("Consolas", 10))
            commands_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
            # 显示命令，每条命令一行
            for i, cmd in enumerate(fio_commands, 1):
                commands_text.insert(tk.END, f"{cmd}\n")

            # 按钮框架
            button_frame = ttk.Frame(popup)
            button_frame.pack(pady=10)

            def on_confirm():
                # 从文本框中读取编辑后的命令
                edited_text = commands_text.get("1.0", tk.END).strip()
                edited_commands = [line.strip() for line in edited_text.split('\n') if line.strip()]
                result["confirmed"] = True
                result["commands"] = edited_commands
                popup.destroy()

            def on_cancel():
                result["confirmed"] = False
                popup.destroy()

            ttk.Button(button_frame, text="确认执行", command=on_confirm).pack(side=tk.LEFT, padx=10)
            ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=10)

            popup.grab_set()
            self.root.wait_window(popup)

        _show()
        return result["confirmed"], result["commands"]

    def get_llm_stream_callback(self):
        """
        获取LLM流式输出回调函数，用于向错误弹窗的分析区域追加内容
        使用缓冲机制减少UI更新频率，避免逐字符输出导致换行问题
        """
        _buffer = {"text": "", "timer": None, "started": False}

        def _flush_buffer():
            if _buffer["text"] and self._popup_analysis_text is not None:
                self._popup_analysis_text.config(state=tk.NORMAL)
                if not _buffer["started"]:
                    self._popup_analysis_text.delete("1.0", tk.END)
                    _buffer["started"] = True
                self._popup_analysis_text.insert(tk.END, _buffer["text"])
                self._popup_analysis_text.see(tk.END)
                self._popup_analysis_text.config(state=tk.DISABLED)
                _buffer["text"] = ""
            _buffer["timer"] = None

        def _stream_callback(content: str):
            _buffer["text"] += content
            if _buffer["timer"] is None:
                _buffer["timer"] = self.root.after(50, _flush_buffer)

        return _stream_callback

    def update_progress(self, value: int, status: str):
        def _update():
            self.progress_bar['value'] = value
            self.progress_label.config(text=status)

        self.root.after(0, _update)

    def load_config(self):
        import json
        import os

        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)

                if 'username' in config:
                    self.username_entry.delete(0, tk.END)
                    self.username_entry.insert(0, config['username'])
                if 'test_device' in config:
                    self.test_device_entry.delete(0, tk.END)
                    self.test_device_entry.insert(0, config['test_device'])
                if 'test_script' in config:
                    self.test_script_entry.delete(0, tk.END)
                    self.test_script_entry.insert(0, config['test_script'])
                if 'script_rows' in config:
                    for i, row_conf in enumerate(config['script_rows']):
                        if i == 0:
                            if 'script' in row_conf:
                                self.test_script_entry.delete(0, tk.END)
                                self.test_script_entry.insert(0, row_conf['script'])
                            if 'case' in row_conf and self.script_rows:
                                self.script_rows[0]["case_entry"].delete(0, tk.END)
                                self.script_rows[0]["case_entry"].insert(0, row_conf['case'])
                            if 'other_param' in row_conf and self.script_rows:
                                self.script_rows[0]["other_entry"].delete(0, tk.END)
                                self.script_rows[0]["other_entry"].insert(0, row_conf['other_param'])
                        else:
                            self._add_script_row()
                            row_data = self.script_rows[-1]
                            if 'script' in row_conf:
                                row_data["script_entry"].insert(0, row_conf['script'])
                            if 'case' in row_conf:
                                row_data["case_entry"].delete(0, tk.END)
                                row_data["case_entry"].insert(0, row_conf['case'])
                            if 'other_param' in row_conf:
                                row_data["other_entry"].delete(0, tk.END)
                                row_data["other_entry"].insert(0, row_conf['other_param'])
                elif 'test_case' in config or 'other_param' in config:
                    if 'test_case' in config and self.script_rows:
                        self.script_rows[0]["case_entry"].delete(0, tk.END)
                        self.script_rows[0]["case_entry"].insert(0, config['test_case'])
                    if 'other_param' in config and self.script_rows:
                        self.script_rows[0]["other_entry"].delete(0, tk.END)
                        self.script_rows[0]["other_entry"].insert(0, config['other_param'])
                if 'project_path' in config:
                    self.project_path_entry.delete(0, tk.END)
                    self.project_path_entry.insert(0, config['project_path'])
                if 'project_name' in config:
                    project_name = config['project_name']
                    if project_name in self.project_name_combobox['values']:
                        self.project_name_var.set(project_name)
                if 'sku' in config:
                    sku = config['sku']
                    if sku in self.sku_combobox['values']:
                        self.sku_var.set(sku)
                if 'ss' in config:
                    self.ss_var.set(config['ss'])
                if 'ddr' in config:
                    self.ddr_var.set(config['ddr'])
                if 'flash_type' in config:
                    self.flash_type_var.set(config['flash_type'])
                if 'upload_result' in config:
                    self.upload_result_var.set(config['upload_result'])
                    self._on_upload_result_toggle()
                if 'version' in config:
                    if self.upload_result_var.get():
                        self.version_entry.config(state=tk.NORMAL)
                        self.version_entry.delete(0, tk.END)
                        self.version_entry.insert(0, config['version'])
                if 'fio_requirement' in config:
                    self.fio_requirement_entry.delete(0, tk.END)
                    self.fio_requirement_entry.insert(0, config['fio_requirement'])
                if 'test_mode' in config:
                    self.test_mode_var.set(config['test_mode'])
                    self._on_test_mode_change()
            except Exception as e:
                print(f"加载配置失败: {str(e)}")

    def save_config(self):
        import json
        import os

        config = {
            'username': self.username_entry.get(),
            'test_device': self.test_device_entry.get(),
            'script_rows': [
                {
                    "script": row_data["script_entry"].get(),
                    "case": row_data["case_entry"].get(),
                    "other_param": row_data["other_entry"].get()
                }
                for row_data in self.script_rows
            ],
            'project_path': self.project_path_entry.get(),
            'project_name': self.project_name_var.get(),
            'sku': self.sku_var.get(),
            'ss': self.ss_var.get(),
            'ddr': self.ddr_var.get(),
            'flash_type': self.flash_type_var.get(),
            'upload_result': self.upload_result_var.get(),
            'version': self.version_entry.get(),
            'fio_requirement': self.fio_requirement_entry.get(),
            'test_mode': self.test_mode_var.get()
        }

        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            print(f"保存配置失败: {str(e)}")

    def fetch_test_scripts(self):
        """
        从远程测试服务器获取测试脚本列表
        """
        def _fetch():
            try:
                from config.config import get_config
                from ssh.ssh_client import SSHClient

                config = get_config()
                host = config.get_config("test_server.host")
                port = config.get_config("test_server.port")
                password = config.get_config("test_server.password")

                username = self.username_entry.get()
                if not username:
                    return

                script_dir = f"/home/{username}/pbdt/scripts/"

                ssh_client = SSHClient(host, port, username, password)
                if not ssh_client.connect():
                    return

                command = f"find {script_dir} -name '*.py' -type f 2>/dev/null"
                success, stdout, stderr = ssh_client.execute_command(command)
                ssh_client.close()

                if success and stdout.strip():
                    full_paths = [line.strip() for line in stdout.strip().split('\n') if line.strip()]
                    name_to_path = {}
                    names = []
                    for path in full_paths:
                        name = path.split('/')[-1]
                        if name in name_to_path:
                            # 重名时用相对路径区分
                            rel = path.replace(script_dir, "")
                            name_to_path[rel] = path
                            names.append(rel)
                        else:
                            name_to_path[name] = path
                            names.append(name)
                    self.script_name_to_path = name_to_path
                    self.script_names = names
                    self.root.after(0, self._on_scripts_loaded)
            except Exception as e:
                print(f"获取测试脚本列表失败: {str(e)}")

        thread = threading.Thread(target=_fetch)
        thread.daemon = True
        thread.start()

    def _on_scripts_loaded(self):
        """
        脚本列表加载完成后的回调
        """
        pass


def run_ui():
    root = tk.Tk()
    app = MainUI(root)
    root.mainloop()
