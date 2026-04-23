# UI界面模块

import tkinter as tk
from tkinter import ttk, scrolledtext
import threading
import time
import os
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

        self._bisect_active = False
        self._bisect_first_test_done = False
        self._bisect_commits = []
        self._bisect_current_middle = None
        self._ai_bisect_running = False

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

        # row=6: 收集串口日志 + 追溯版本
        ttk.Label(input_frame, text="收集串口日志:").grid(row=6, column=0, sticky=tk.W, padx=5, pady=3)
        row6_frame = ttk.Frame(input_frame)
        row6_frame.grid(row=6, column=1, sticky=tk.W, padx=5, pady=3)
        self.collect_uart_var = tk.BooleanVar()
        ttk.Checkbutton(row6_frame, variable=self.collect_uart_var, text="收集串口日志").pack(side=tk.LEFT, padx=(0, 20))
        self.collect_uart_var.set(True)
        self.bisect_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(row6_frame, variable=self.bisect_var, text="追溯版本", command=self._on_bisect_toggle).pack(side=tk.LEFT)

        # row=7: 上传测试结果 / 追溯版本 commit 范围
        self.upload_result_label = ttk.Label(input_frame, text="上传测试结果:")
        self.upload_result_label.grid(row=7, column=0, sticky=tk.W, padx=5, pady=3)
        self.upload_result_frame = ttk.Frame(input_frame)
        self.upload_result_frame.grid(row=7, column=1, sticky=tk.W, padx=5, pady=3)
        self.upload_result_var = tk.BooleanVar()
        ttk.Radiobutton(self.upload_result_frame, text="是", variable=self.upload_result_var, value=True, command=self._on_upload_result_toggle).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Radiobutton(self.upload_result_frame, text="否", variable=self.upload_result_var, value=False, command=self._on_upload_result_toggle).pack(side=tk.LEFT)
        self.upload_result_var.set(False)

        self.bisect_commit_label = ttk.Label(input_frame, text="Commit范围:")
        self.bisect_commit_label.grid(row=7, column=0, sticky=tk.W, padx=5, pady=3)
        self.bisect_commit_frame = ttk.Frame(input_frame)
        self.bisect_commit_frame.grid(row=7, column=1, sticky=tk.W, padx=5, pady=3)
        ttk.Label(self.bisect_commit_frame, text="Start(新):").pack(side=tk.LEFT, padx=(0, 2))
        self.bisect_start_var = tk.StringVar()
        self.bisect_start_combobox = ttk.Combobox(self.bisect_commit_frame, textvariable=self.bisect_start_var, width=36)
        self.bisect_start_combobox.pack(side=tk.LEFT, padx=(0, 8))
        self.bisect_start_combobox.bind("<<ComboboxSelected>>", self._on_bisect_start_selected)
        ttk.Label(self.bisect_commit_frame, text="End(旧):").pack(side=tk.LEFT, padx=(0, 2))
        self.bisect_end_var = tk.StringVar()
        self.bisect_end_combobox = ttk.Combobox(self.bisect_commit_frame, textvariable=self.bisect_end_var, width=36)
        self.bisect_end_combobox.pack(side=tk.LEFT)
        self.bisect_commit_label.grid_remove()
        self.bisect_commit_frame.grid_remove()

        # row=8: 版本号
        self.version_label = ttk.Label(input_frame, text="版本号:")
        self.version_label.grid(row=8, column=0, sticky=tk.W, padx=5, pady=3)
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

    def _on_bisect_toggle(self):
        if self.bisect_var.get():
            self.upload_result_label.grid_remove()
            self.upload_result_frame.grid_remove()
            self.version_label.grid_remove()
            self.version_entry.grid_remove()
            self.bisect_commit_label.grid()
            self.bisect_commit_frame.grid()
            self._fetch_git_log()
        else:
            if self._bisect_active and self._execution_running:
                self.bisect_var.set(True)
                self.update_output("[追溯版本] 执行中无法取消追溯版本，请先停止执行\n")
                return
            self._end_bisect_ui()
            self.bisect_commit_label.grid_remove()
            self.bisect_commit_frame.grid_remove()
            self.upload_result_label.grid()
            self.upload_result_frame.grid()
            self.version_label.grid()
            self.version_entry.grid()

    def _end_bisect_ui(self):
        self._bisect_active = False
        self._bisect_first_test_done = False
        self._bisect_current_middle = None
        self._ai_bisect_running = False
        self._ai_bisect_phase = "bisect"
        self.start_button.pack(side=tk.LEFT, padx=5)
        self.bisect_forward_button.pack_forget()
        self.bisect_backward_button.pack_forget()
        self.bisect_ai_button.pack_forget()
        self.bisect_end_button.pack_forget()

    def _fetch_git_log(self):
        def _fetch():
            try:
                from app.application import Application
                app = Application(log_callback=self.update_output)
                username = self.username_entry.get()
                project_path = self.project_path_entry.get()
                app.config.set_config("build_server.username", username)
                commits = app.get_git_log(project_path=project_path, count=100)
                if commits:
                    self._bisect_commits = commits
                    self.root.after(0, self._on_git_log_loaded)
                else:
                    self.root.after(0, lambda: self.update_output("获取git log失败，请检查编译路径是否正确\n"))
            except Exception as e:
                self.root.after(0, lambda: self.update_output(f"获取git log异常: {str(e)}\n"))

        thread = threading.Thread(target=_fetch)
        thread.daemon = True
        thread.start()

    def _on_git_log_loaded(self):
        self.bisect_start_combobox['values'] = self._bisect_commits
        self.bisect_end_combobox['values'] = self._bisect_commits
        if len(self._bisect_commits) > 0:
            self.bisect_start_var.set(self._bisect_commits[0])
            self.bisect_end_var.set(self._bisect_commits[-1])
        self.update_output(f"已加载 {len(self._bisect_commits)} 条commit记录\n")

    def _on_bisect_start_selected(self, event=None):
        start_text = self.bisect_start_var.get()
        if not start_text or not self._bisect_commits:
            return
        start_hash = start_text.split()[0]
        start_idx = None
        for i, c in enumerate(self._bisect_commits):
            if c.split()[0] == start_hash:
                start_idx = i
                break
        if start_idx is None:
            return
        filtered = self._bisect_commits[start_idx:]
        self.bisect_end_combobox['values'] = filtered
        end_text = self.bisect_end_var.get()
        if end_text:
            end_hash = end_text.split()[0]
            end_in_range = any(c.split()[0] == end_hash for c in filtered)
            if not end_in_range:
                self.bisect_end_var.set(start_text)

    def _find_middle_commit(self):
        start_text = self.bisect_start_var.get()
        end_text = self.bisect_end_var.get()
        if not start_text or not end_text:
            return None, "请选择Start Commit和End Commit"
        start_hash = start_text.split()[0] if start_text else None
        end_hash = end_text.split()[0] if end_text else None
        if start_hash == end_hash:
            return start_text, None
        start_idx = None
        end_idx = None
        for i, c in enumerate(self._bisect_commits):
            c_hash = c.split()[0]
            if c_hash == start_hash:
                start_idx = i
            if c_hash == end_hash:
                end_idx = i
        if start_idx is None or end_idx is None:
            return None, "所选commit不在列表中，请重新选择"
        if start_idx > end_idx:
            return None, "Start提交不能早于End提交，请确保Start(新)比End(旧)更新"
        if start_idx == end_idx:
            return self._bisect_commits[start_idx], None
        mid_idx = (start_idx + end_idx) // 2
        return self._bisect_commits[mid_idx], None

    def _show_bisect_confirm_popup(self, middle_commit, direction_label=""):
        result = {"confirmed": False}

        def _show():
            popup = tk.Toplevel(self.root)
            popup.title("确认追溯版本")
            popup.geometry("600x280")
            popup.attributes('-topmost', True)
            popup.focus_force()

            if direction_label:
                ttk.Label(popup, text=direction_label, font=("Arial", 12, "bold"),
                           foreground="blue").pack(padx=10, pady=8, anchor=tk.W)

            info_frame = ttk.LabelFrame(popup, text="追溯信息", padding=8)
            info_frame.pack(fill=tk.X, padx=10, pady=5)

            ttk.Label(info_frame, text=f"Start Commit(新): {self.bisect_start_var.get()}", wraplength=550).pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"End Commit(旧):   {self.bisect_end_var.get()}", wraplength=550).pack(anchor=tk.W, pady=2)
            ttk.Label(info_frame, text=f"将测试 Commit: {middle_commit}", wraplength=550, foreground="red",
                       font=("Arial", 10, "bold")).pack(anchor=tk.W, pady=4)

            button_frame = ttk.Frame(popup)
            button_frame.pack(pady=10)

            def on_confirm():
                result["confirmed"] = True
                popup.destroy()

            def on_cancel():
                result["confirmed"] = False
                popup.destroy()

            ttk.Button(button_frame, text="确认", command=on_confirm).pack(side=tk.LEFT, padx=10)
            ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=10)

            popup.grab_set()
            self.root.wait_window(popup)

        _show()
        return result["confirmed"]

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

        self.bisect_forward_button = ttk.Button(button_frame, text="向前追溯", command=self._bisect_go_forward)
        self.bisect_backward_button = ttk.Button(button_frame, text="向后追溯", command=self._bisect_go_backward)
        self.bisect_ai_button = ttk.Button(button_frame, text="AI托管", command=self._show_ai_bisect_popup)
        self.bisect_end_button = ttk.Button(button_frame, text="结束追溯", command=self._bisect_end)

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
        if self.bisect_var.get():
            middle_commit, err = self._find_middle_commit()
            if err:
                self.update_output(f"[追溯版本] {err}\n")
                return
            self._bisect_current_middle = middle_commit
            direction = "首次追溯" if not self._bisect_first_test_done else ""
            if not self._show_bisect_confirm_popup(middle_commit, direction):
                self.update_output("[追溯版本] 用户取消\n")
                return
            self._bisect_active = True
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

    def _bisect_go_forward(self):
        if not self._bisect_current_middle:
            return
        middle_hash = self._bisect_current_middle.split()[0]
        self.bisect_end_var.set(self._bisect_current_middle)
        self._on_bisect_start_selected()
        middle_commit, err = self._find_middle_commit()
        if err:
            self.update_output(f"[追溯版本] {err}\n")
            return
        if not middle_commit or middle_commit.split()[0] == middle_hash:
            self.update_output("[追溯版本] 已无法继续缩小范围，请结束追溯\n")
            return
        self._bisect_current_middle = middle_commit
        if not self._show_bisect_confirm_popup(middle_commit, "向前追溯（问题在更旧的提交）"):
            return
        self._start_bisect_execution()

    def _bisect_go_backward(self):
        if not self._bisect_current_middle:
            return
        middle_hash = self._bisect_current_middle.split()[0]
        self.bisect_start_var.set(self._bisect_current_middle)
        self._on_bisect_start_selected()
        middle_commit, err = self._find_middle_commit()
        if err:
            self.update_output(f"[追溯版本] {err}\n")
            return
        if not middle_commit or middle_commit.split()[0] == middle_hash:
            self.update_output("[追溯版本] 已无法继续缩小范围，请结束追溯\n")
            return
        self._bisect_current_middle = middle_commit
        if not self._show_bisect_confirm_popup(middle_commit, "向后追溯（问题在更新的提交）"):
            return
        self._start_bisect_execution()

    def _bisect_end(self):
        self._ai_bisect_running = False
        self.bisect_var.set(False)
        self._on_bisect_toggle()
        self.update_output("[追溯版本] 已结束追溯\n")

    def _show_ai_bisect_popup(self):
        popup = tk.Toplevel(self.root)
        popup.title("AI托管追溯版本")
        popup.geometry("800x700")
        popup.attributes('-topmost', True)
        popup.focus_force()
        popup.resizable(True, True)

        main_frame = ttk.Frame(popup, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)

        log_frame = ttk.LabelFrame(main_frame, text="Test Log 摘取", padding=8)
        log_frame.pack(fill=tk.X, pady=(0, 5))

        test_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "test_log.txt")
        total_lines = 0
        log_content_list = []
        try:
            with open(test_log_path, 'r', encoding='utf-8', errors='replace') as f:
                log_content_list = f.readlines()
                total_lines = len(log_content_list)
        except Exception:
            pass

        line_info = ttk.Label(log_frame, text=f"test_log.txt 共 {total_lines} 行", foreground="blue")
        line_info.pack(anchor=tk.W, pady=(0, 3))

        range_frame = ttk.Frame(log_frame)
        range_frame.pack(fill=tk.X, pady=(0, 3))
        ttk.Label(range_frame, text="起始行:").pack(side=tk.LEFT, padx=(0, 2))
        start_line_entry = ttk.Entry(range_frame, width=8)
        start_line_entry.pack(side=tk.LEFT, padx=(0, 8))
        start_line_entry.insert(0, "1")
        ttk.Label(range_frame, text="结束行:").pack(side=tk.LEFT, padx=(0, 2))
        end_line_entry = ttk.Entry(range_frame, width=8)
        end_line_entry.pack(side=tk.LEFT, padx=(0, 8))
        end_line_entry.insert(0, str(min(total_lines, 50)))

        preview_text = tk.Text(log_frame, height=10, wrap=tk.WORD, font=("Consolas", 9))
        preview_text.pack(fill=tk.X, pady=(0, 3))

        def on_extract():
            try:
                s = int(start_line_entry.get())
                e = int(end_line_entry.get())
            except ValueError:
                return
            s = max(1, min(s, total_lines))
            e = max(s, min(e, total_lines))
            preview_text.config(state=tk.NORMAL)
            preview_text.delete("1.0", tk.END)
            for i in range(s - 1, e):
                preview_text.insert(tk.END, log_content_list[i])
            preview_text.config(state=tk.DISABLED)

        ttk.Button(range_frame, text="提取", command=on_extract).pack(side=tk.LEFT, padx=(0, 5))

        criteria_frame = ttk.LabelFrame(main_frame, text="期望判断依据", padding=8)
        criteria_frame.pack(fill=tk.X, pady=(0, 5))

        ttk.Label(criteria_frame, text="请输入判断测试结果是否符合预期的依据（如：我期望顺序读性能能达到12G/s）:").pack(anchor=tk.W, pady=(0, 3))
        criteria_text = tk.Text(criteria_frame, height=4, wrap=tk.WORD, font=("Arial", 10))
        criteria_text.pack(fill=tk.X)

        result_frame = ttk.LabelFrame(main_frame, text="LLM 分析结果", padding=8)
        result_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        result_text = tk.Text(result_frame, height=10, wrap=tk.WORD, font=("Consolas", 10), state=tk.DISABLED)
        result_text.pack(fill=tk.BOTH, expand=True)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(0, 0))

        def on_analyze():
            try:
                s = int(start_line_entry.get())
                e = int(end_line_entry.get())
            except ValueError:
                return
            s = max(1, min(s, total_lines))
            e = max(s, min(e, total_lines))
            extracted = "".join(log_content_list[s - 1:e])
            criteria = criteria_text.get("1.0", tk.END).strip()
            if not criteria:
                result_text.config(state=tk.NORMAL)
                result_text.delete("1.0", tk.END)
                result_text.insert(tk.END, "请输入期望判断依据")
                result_text.config(state=tk.DISABLED)
                return

            result_text.config(state=tk.NORMAL)
            result_text.delete("1.0", tk.END)
            result_text.insert(tk.END, "正在分析中...\n")
            result_text.config(state=tk.DISABLED)

            def _run_llm():
                from llm.error_analyzer import get_error_analyzer
                analyzer = get_error_analyzer()
                prompt = (
                    f"【测试结果判断】\n\n"
                    f"以下是测试日志的摘取片段：\n\n"
                    f"{extracted}\n\n"
                    f"用户的期望判断依据：{criteria}\n\n"
                    f"请根据以上测试日志和用户的期望判断依据，判断测试结果是否符合用户预期。\n"
                    f"请严格按照以下格式输出：\n"
                    f"1. 判断结果：[符合预期/不符合预期/无法判断]\n"
                    f"2. 分析依据：[引用日志中的关键数据支持你的判断]\n"
                    f"3. 详细说明：[具体分析测试结果与期望的对比]\n"
                    f"注意：判断必须基于日志中的实际数据，不要臆测。如果日志中没有足够信息，请选择'无法判断'。"
                )

                def _stream_cb(content):
                    result_text.config(state=tk.NORMAL)
                    if result_text.get("1.0", "2.0").strip() == "正在分析中...":
                        result_text.delete("1.0", tk.END)
                    result_text.insert(tk.END, content)
                    result_text.see(tk.END)
                    result_text.config(state=tk.DISABLED)

                def _safe_stream(content):
                    self.root.after(0, lambda c=content: _stream_cb(c))

                result = analyzer._call_llm_stream(prompt, _safe_stream)

                if result is None:
                    self.root.after(0, lambda: (
                        result_text.config(state=tk.NORMAL),
                        result_text.delete("1.0", tk.END),
                        result_text.insert(tk.END, f"LLM分析失败: {analyzer.last_error}"),
                        result_text.config(state=tk.DISABLED)
                    ))
                else:
                    self._ai_bisect_last_result = result
                    self.root.after(0, lambda: start_host_btn.config(state=tk.NORMAL))

            thread = threading.Thread(target=_run_llm)
            thread.daemon = True
            thread.start()

        ttk.Button(button_frame, text="LLM分析", command=on_analyze).pack(side=tk.LEFT, padx=5)

        def on_start_host():
            criteria = criteria_text.get("1.0", tk.END).strip()
            try:
                log_s = int(start_line_entry.get())
                log_e = int(end_line_entry.get())
            except ValueError:
                log_s = 1
                log_e = 50
            popup.destroy()
            self._ai_bisect_running = True
            self._ai_bisect_criteria = criteria
            self._ai_bisect_log_start = log_s
            self._ai_bisect_log_end = log_e
            self.update_output("[AI托管] 开始AI托管追溯...\n")
            self.update_output(f"[AI托管] Start(新/不符合预期): {self.bisect_start_var.get()}\n")
            self.update_output(f"[AI托管] End(旧/符合预期): {self.bisect_end_var.get()}\n")

            last_result = getattr(self, '_ai_bisect_last_result', '')
            if last_result:
                import re
                judgment_match = re.search(r'判断结果[：:]\s*\[?([^\]\n]+)\]?', last_result)
                if judgment_match:
                    judgment = judgment_match.group(1).strip()
                    is_fail = "不符合预期" in judgment
                    is_pass = "符合预期" in judgment
                    if is_fail:
                        self.update_output(f"[AI托管] 首次测试结果：{judgment} → start=middle，向旧方向搜索\n")
                        self.bisect_start_var.set(self._bisect_current_middle)
                        self._on_bisect_start_selected()
                    elif is_pass:
                        self.update_output(f"[AI托管] 首次测试结果：{judgment} → end=middle，向新方向搜索\n")
                        self.bisect_end_var.set(self._bisect_current_middle)
                        self._on_bisect_start_selected()
                    else:
                        self.update_output("[AI托管] 首次测试LLM无法判断方向，将从中间commit开始追溯\n")
                else:
                    self.update_output("[AI托管] 首次测试LLM输出格式异常，将从中间commit开始追溯\n")

            self._ai_bisect_loop()

        start_host_btn = ttk.Button(button_frame, text="开始托管", command=on_start_host, state=tk.DISABLED)
        start_host_btn.pack(side=tk.LEFT, padx=5)

        def on_cancel():
            popup.destroy()

        ttk.Button(button_frame, text="取消", command=on_cancel).pack(side=tk.LEFT, padx=5)

        popup.grab_set()

    def _ai_bisect_loop(self):
        if not self._ai_bisect_running:
            return
        if self.stop_event.is_set():
            self.update_output("[AI托管] 用户停止了执行\n")
            self._ai_bisect_running = False
            return

        start_text = self.bisect_start_var.get()
        end_text = self.bisect_end_var.get()
        start_hash = start_text.split()[0] if start_text else None
        end_hash = end_text.split()[0] if end_text else None

        if start_hash == end_hash:
            self._report_bisect_result(start_text)
            return

        middle_commit, err = self._find_middle_commit()
        if err:
            self.update_output(f"[AI托管] 计算中间commit失败: {err}\n")
            self._ai_bisect_running = False
            self.root.after(0, lambda: self._show_bisect_buttons())
            return
        if not middle_commit or (middle_commit.split()[0] == start_hash):
            self.update_output(f"[AI托管] 已收敛到相邻commit，需要验证End commit: {end_text}\n")
            self._bisect_current_middle = end_text
            self._ai_bisect_phase = "verify_end"
            self._run_ai_bisect_test()
            return

        self._bisect_current_middle = middle_commit
        self._ai_bisect_phase = "bisect"
        self.update_output(f"\n[AI托管] 测试中间commit: {middle_commit}\n")

        self._run_ai_bisect_test()

    def _report_bisect_result(self, commit_text):
        self.update_output(f"\n[AI托管] ✅ 追溯完成！最初出现问题的commit是: {commit_text}\n")
        self._ai_bisect_running = False
        self._ai_bisect_phase = "bisect"
        self.root.after(0, lambda: self._show_bisect_buttons())
        self.root.after(0, lambda: self.show_success_popup(
            "🎯 追溯完成",
            f"最初出现问题的commit是:\n{commit_text}"
        ))

    def _run_ai_bisect_test(self):
        self.stop_button.config(state=tk.NORMAL)
        self.bisect_forward_button.config(state=tk.DISABLED)
        self.bisect_backward_button.config(state=tk.DISABLED)
        self.bisect_ai_button.config(state=tk.DISABLED)
        self.bisect_end_button.config(state=tk.DISABLED)
        self.stop_event.clear()
        self._execution_running = True

        self.output_text.config(state=tk.NORMAL)
        self.output_text.delete("1.0", tk.END)
        self.output_text.config(state=tk.DISABLED)

        self.execution_thread = threading.Thread(target=self._ai_bisect_execute_and_judge)
        self.execution_thread.daemon = True
        self.execution_thread.start()

    def _ai_bisect_execute_and_judge(self):
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
        collect_uart = self.collect_uart_var.get()
        flash_type = self.flash_type_var.get()

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
                self.update_output("[AI托管] 执行已停止\n")
                return

            commit_hash = self._bisect_current_middle.split()[0]
            self.update_output(f"[AI托管] git reset 到 {self._bisect_current_middle}\n")
            reset_ok, reset_err = app.git_reset_to_commit(commit_hash, project_path=project_path)
            if not reset_ok:
                self.update_output(f"[AI托管] git reset 失败: {reset_err}\n")
                self._ai_bisect_running = False
                self.root.after(0, lambda: self._show_bisect_buttons())
                return

            if test_mode == "自定义 FIO 测试":
                self.update_output("[AI托管] 生成FIO命令...\n")
                success, error, fio_commands = app.fio_test_processor.generate_fio_commands(fio_requirement)
                if not success:
                    self.update_output(f"[AI托管] 生成FIO命令失败: {error}\n")
                    self._ai_bisect_running = False
                    self.root.after(0, lambda: self._show_bisect_buttons())
                    return
                test_success = app.execute_workflow(
                    username, test_device, test_script,
                    project_path, project_name, sku, "编译", collect_uart, flash_type,
                    self.stop_event, test_case, other_param, False, "",
                    test_mode, fio_requirement, fio_commands, extra_scripts=[], show_popup=False)
            else:
                test_success = app.execute_workflow(
                    username, test_device, test_script,
                    project_path, project_name, sku, "编译", collect_uart, flash_type,
                    self.stop_event, test_case, other_param, False, "",
                    test_mode, fio_requirement, extra_scripts=extra_scripts, show_popup=False)

            if self.stop_event.is_set():
                self.update_output("[AI托管] 执行已停止\n")
                self._ai_bisect_running = False
                self.root.after(0, lambda: self._show_bisect_buttons())
                return

            for f in app.log_files.values():
                try:
                    f.close()
                except Exception:
                    pass

            self.update_output("\n[AI托管] 测试完成，正在用LLM判断结果...\n")
            self._ai_judge_result()

        except Exception as e:
            self.update_output(f"[AI托管] 执行异常: {str(e)}\n")
            self._ai_bisect_running = False
            self.root.after(0, lambda: self._show_bisect_buttons())
        finally:
            self._execution_running = False
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED))

    def _ai_judge_result(self, retry_full_log=False):
        test_log_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs", "test_log.txt")
        log_lines = []
        try:
            with open(test_log_path, 'r', encoding='utf-8', errors='replace') as f:
                log_lines = f.readlines()
        except Exception:
            pass

        total = len(log_lines)
        if retry_full_log:
            s = 1
            e = total
            self.update_output(f"[AI托管] ⚠️ 指定区域无法判断，正在使用完整日志重试（共{total}行）...\n")
        else:
            s = max(1, getattr(self, '_ai_bisect_log_start', 1))
            e = min(getattr(self, '_ai_bisect_log_end', 50), total)
        extracted = "".join(log_lines[s - 1:e])
        criteria = getattr(self, '_ai_bisect_criteria', '')
        phase = getattr(self, '_ai_bisect_phase', 'bisect')

        if not extracted.strip():
            self.update_output(f"[AI托管] test_log截取区域(行{s}-{e})为空，尝试读取完整日志...\n")
            if not retry_full_log and total > 0:
                self._ai_judge_result(retry_full_log=True)
                return
            self.update_output("[AI托管] test_log完全为空，无法判断，请手动追溯\n")
            self._ai_bisect_running = False
            self.root.after(0, lambda: self._show_bisect_buttons())
            return

        preview = extracted[:500] + ("..." if len(extracted) > 500 else "")
        self.update_output(f"\n[AI托管] 提取test_log第{s}~{e}行（共{total}行），内容预览:\n{preview}\n")

        from llm.error_analyzer import get_error_analyzer
        analyzer = get_error_analyzer()

        if phase == "verify_end":
            prompt = (
                f"【验证End Commit测试结果】\n\n"
                f"当前正在追溯版本，已知Start(新)commit不符合预期，需要验证End(旧)commit是否符合预期。\n"
                f"以下是End commit的测试日志摘取片段（第{s}行到第{e}行，共{total}行）：\n\n"
                f"{extracted}\n\n"
                f"用户的期望判断依据：{criteria}\n\n"
                f"请判断End commit的测试结果是否符合用户预期。\n"
                f"请严格按照以下格式输出：\n"
                f"1. 判断结果：[符合预期/不符合预期/无法判断]\n"
                f"2. 分析依据：[引用日志中的关键数据支持你的判断]\n"
                f"3. 详细说明：[具体分析测试结果与期望的对比]\n"
                f"注意：判断必须基于日志中的实际数据，不要臆测。如果日志中没有足够信息，请选择'无法判断'。"
            )
        else:
            prompt = (
                f"【测试结果判断】\n\n"
                f"以下是测试日志的摘取片段（第{s}行到第{e}行，共{total}行）：\n\n"
                f"{extracted}\n\n"
                f"用户的期望判断依据：{criteria}\n\n"
                f"请根据以上测试日志和用户的期望判断依据，判断测试结果是否符合用户预期。\n"
                f"请严格按照以下格式输出：\n"
                f"1. 判断结果：[符合预期/不符合预期/无法判断]\n"
                f"2. 分析依据：[引用日志中的关键数据支持你的判断]\n"
                f"3. 详细说明：[具体分析测试结果与期望的对比]\n"
                f"注意：判断必须基于日志中的实际数据，不要臆测。如果日志中没有足够信息，请选择'无法判断'。"
            )

        full_result = []
        def _collect(content):
            full_result.append(content)

        result = analyzer._call_llm_stream(prompt, _collect)

        if result is None:
            self.update_output(f"[AI托管] LLM分析失败: {analyzer.last_error}，请手动追溯\n")
            self._ai_bisect_running = False
            self.root.after(0, lambda: self._show_bisect_buttons())
            return

        self.update_output(f"\n[AI托管] LLM分析结果:\n{result}\n")

        import re
        judgment_match = re.search(r'判断结果[：:]\s*\[?([^\]\n]+)\]?', result)
        if judgment_match:
            judgment = judgment_match.group(1).strip()
            self.update_output(f"[AI托管] 提取到判断结论: [{judgment}]\n")
        else:
            self.update_output("[AI托管] ⚠️ 无法从LLM输出中提取标准判断格式\n")
            if not retry_full_log and total > (e - s + 1):
                self.update_output("[AI托管] 尝试使用完整日志重试...\n")
                self._ai_judge_result(retry_full_log=True)
                return
            if phase == "verify_end":
                start_text = self.bisect_start_var.get()
                self.update_output("[AI托管] 无法判断End commit结果，默认报告Start为最初问题commit\n")
                self._report_bisect_result(start_text)
            else:
                self.update_output("[AI托管] 判断：无法确定，请手动追溯\n")
                self._ai_bisect_running = False
                self.root.after(0, lambda: self._show_bisect_buttons())
            return

        is_pass = "符合预期" in judgment
        is_fail = "不符合预期" in judgment

        if phase == "verify_end":
            start_text = self.bisect_start_var.get()
            end_text = self.bisect_end_var.get()
            if is_pass:
                self.update_output(f"[AI托管] End commit符合预期 → 最初出现问题的commit是Start: {start_text}\n")
                self._report_bisect_result(start_text)
            elif is_fail:
                self.update_output(f"[AI托管] End commit也不符合预期 → 最初出现问题的commit是End: {end_text}\n")
                self._report_bisect_result(end_text)
            else:
                if not retry_full_log and total > (e - s + 1):
                    self.update_output("[AI托管] 无法判断End commit，尝试使用完整日志重试...\n")
                    self._ai_judge_result(retry_full_log=True)
                    return
                self.update_output("[AI托管] 无法判断End commit结果，默认报告Start为最初问题commit\n")
                self._report_bisect_result(start_text)
            return

        if is_fail:
            self.update_output(f"[AI托管] 判断：{judgment} → 向后追溯（start=middle，向旧方向搜索）\n")
            self.bisect_start_var.set(self._bisect_current_middle)
            self._on_bisect_start_selected()
        elif is_pass:
            self.update_output(f"[AI托管] 判断：{judgment} → 向前追溯（end=middle，向新方向搜索）\n")
            self.bisect_end_var.set(self._bisect_current_middle)
            self._on_bisect_start_selected()
        else:
            if not retry_full_log and total > (e - s + 1):
                self.update_output("[AI托管] ⚠️ 指定区域无法判断，尝试使用完整日志重试...\n")
                self._ai_judge_result(retry_full_log=True)
                return
            self.update_output("[AI托管] 判断：无法确定，请手动追溯\n")
            self._ai_bisect_running = False
            self.root.after(0, lambda: self._show_bisect_buttons())
            return

        import time
        time.sleep(2)

        if self._ai_bisect_running and not self.stop_event.is_set():
            self.root.after(0, self._ai_bisect_loop)
        else:
            self._ai_bisect_running = False
            self.root.after(0, lambda: self._show_bisect_buttons())

    def _start_bisect_execution(self):
        self.stop_button.config(state=tk.NORMAL)
        self.bisect_forward_button.config(state=tk.DISABLED)
        self.bisect_backward_button.config(state=tk.DISABLED)
        self.bisect_end_button.config(state=tk.DISABLED)
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

    def _show_bisect_buttons(self):
        self.start_button.pack_forget()
        self.bisect_forward_button.pack(side=tk.LEFT, padx=5)
        self.bisect_backward_button.pack(side=tk.LEFT, padx=5)
        self.bisect_ai_button.pack(side=tk.LEFT, padx=5)
        self.bisect_end_button.pack(side=tk.LEFT, padx=5)
        self.bisect_forward_button.config(state=tk.NORMAL)
        self.bisect_backward_button.config(state=tk.NORMAL)
        self.bisect_ai_button.config(state=tk.NORMAL)
        self.bisect_end_button.config(state=tk.NORMAL)

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

            if self._bisect_active and self._bisect_current_middle:
                commit_hash = self._bisect_current_middle.split()[0]
                self.update_output(f"[追溯版本] git reset 到 {self._bisect_current_middle}\n")
                reset_ok, reset_err = app.git_reset_to_commit(commit_hash, project_path=project_path)
                if not reset_ok:
                    self.update_output(f"[追溯版本] git reset 失败: {reset_err}\n")
                    self.update_progress(100, "执行失败")
                    return
                start_step = "编译"

            if test_mode == "自定义 FIO 测试":
                self.update_output("正在生成FIO命令...\n")
                self.update_progress(20, "生成FIO命令")
                
                success, error, fio_commands = app.fio_test_processor.generate_fio_commands(fio_requirement)
                
                if not success:
                    self.update_output(f"生成FIO命令失败: {error}\n")
                    self.update_progress(100, "执行失败")
                    return
                
                self.update_progress(40, "确认FIO命令")
                confirmed, fio_commands = self.show_fio_commands_popup(fio_commands)
                
                if not confirmed:
                    self.update_output("用户取消执行FIO测试\n")
                    self.update_progress(100, "执行取消")
                    return
                
                self.update_progress(60, "执行FIO测试")
                success = app.execute_workflow(username, test_device, test_script,
                                              project_path, project_name, sku, start_step, collect_uart, flash_type, 
                                              self.stop_event, test_case, other_param, upload_result, version, 
                                              test_mode, fio_requirement, fio_commands, extra_scripts=[])
            else:
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
            if self._bisect_active:
                self._bisect_first_test_done = True
                self.root.after(0, self._show_bisect_buttons)
            else:
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
                if 'bisect' in config:
                    self.bisect_var.set(config['bisect'])
                    if config['bisect']:
                        self._on_bisect_toggle()
                if 'bisect_start' in config and self._bisect_commits:
                    self.bisect_start_var.set(config['bisect_start'])
                if 'bisect_end' in config and self._bisect_commits:
                    self.bisect_end_var.set(config['bisect_end'])
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
            'test_mode': self.test_mode_var.get(),
            'bisect': self.bisect_var.get(),
            'bisect_start': self.bisect_start_var.get(),
            'bisect_end': self.bisect_end_var.get()
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
