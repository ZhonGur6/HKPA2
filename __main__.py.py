import json
import os
import threading
import tkinter as tk
import subprocess
from tkinter import ttk, messagebox
import sys
import uuid
import urllib.request
import hashlib
import zipfile
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import time
from PIL import Image, ImageTk
import io
import urllib.request

# 尝试导入 Windows 注册表模块，非 Windows 平台将无法获取 Java 版本
if sys.platform == 'win32':
    try:
        import winreg
        WINDOWS_MODE = True
    except ImportError:
        WINDOWS_MODE = False
        messagebox.showwarning("环境警告", "winreg 模块不可用，Java 版本检测功能将受限。")
else:
    WINDOWS_MODE = False

# 导入 ctypes 用于 Windows API 调用
if sys.platform == 'win32':
    try:
        import ctypes
        from ctypes import wintypes
        ctypes_available = True
    except ImportError:
        ctypes_available = False
else:
    ctypes_available = False

class Game():
    def __init__(self) -> None:
        self.root = tk.Tk(className="HKPA1")
        self.root.geometry("900x600")
        self.root.minsize(850, 550)
        
        # 保存初始窗口位置
        self.root.update_idletasks()
        self.initial_x = self.root.winfo_x()
        self.initial_y = self.root.winfo_y()
        
        # Windows 下需要设置任务栏图标和标题
        if sys.platform == 'win32' and ctypes_available:
            # 设置应用用户模型 ID，使窗口显示在任务栏
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HKPA1.MinecraftLauncher")

        self.selected_mc_version = ""
        self.selected_java_info = ("", "")
        self.player_nickname = "Player"
        self.player_skin_path = None
        self.tree = None

        self.style = ttk.Style()
        self.style.configure("Accent.TButton", font=('Microsoft YaHei', 10, 'bold'))
        self.style.configure("Header.TLabel", font=('Microsoft YaHei', 12, 'bold'))
        self.style.configure("Nav.TButton", font=('Microsoft YaHei', 10), padding=10)

        # 初始化 Minecraft 目录结构
        self.init_minecraft_directory()

        self.create_widgets()

    def Run(self) -> None:
        #启动程序循环
        self.root.mainloop()

    def create_widgets(self):
        """创建和布局所有界面组件"""
        # 使用无边框窗口设计
        self.root.overrideredirect(True)  # 去掉标准标题栏和边框
        
        # Windows 下设置任务栏图标
        if sys.platform == 'win32' and ctypes_available:
            # 设置应用用户模型 ID，使窗口显示在任务栏
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("HKPA1.MinecraftLauncher")
        
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)
        
        header_frame = tk.Frame(main_container, height=50, bg='#1976D2')
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)
        
        # 加载草方块图片作为 Logo
        try:
            def get_resource_path(filename):
                """获取资源文件路径，兼容打包后的 exe"""
                if getattr(sys, 'frozen', False):
                    # 打包后的 exe 环境
                    path = os.path.dirname(sys.executable)
                else:
                    # 开发环境
                    path = os.path.dirname(__file__)
                return os.path.join(path, filename)
        
            logo_image = Image.open(get_resource_path("Grass.ico"))
            logo_image = logo_image.resize((32, 32), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(header_frame, image=self.logo_photo, bg='#1976D2')
        except Exception as e:
            # 如果加载失败，使用文字替代
            self.logo_photo = None
            logo_label = tk.Label(header_frame, text="🎮", bg='#1976D2', font=('Segoe UI Emoji', 24))
        
        logo_label.pack(side=tk.LEFT, padx=15, pady=9)
        
        title_label = tk.Label(header_frame, text="HKPA1", 
                              bg='#1976D2', fg='white', 
                              font=('Microsoft YaHei', 14, 'bold'))
        title_label.pack(side=tk.LEFT, padx=(0, 20), pady=10)
        
        nav_frame = tk.Frame(header_frame, bg='#1976D2')
        nav_frame.pack(side=tk.LEFT, padx=20)
        
        download_btn = tk.Button(nav_frame, text="⬇ 下载", 
                                bg='#1976D2', fg='white',
                                font=('Microsoft YaHei', 10),
                                bd=0, cursor='hand2',
                                command=self.toggle_download_page)
        download_btn.pack(side=tk.LEFT, padx=5)
        
        settings_btn = tk.Button(nav_frame, text="⚙ 设置", 
                                bg='#1976D2', fg='white',
                                font=('Microsoft YaHei', 10),
                                bd=0, cursor='hand2',
                                command=self.toggle_settings_page)
        settings_btn.pack(side=tk.LEFT, padx=5)
        
        more_btn = tk.Button(nav_frame, text="⋮ 更多", 
                            bg='#1976D2', fg='white',
                            font=('Microsoft YaHei', 10),
                            bd=0, cursor='hand2',
                            command=self.show_more_menu)
        more_btn.pack(side=tk.LEFT, padx=5)
        
        window_btn_frame = tk.Frame(header_frame, bg='#1976D2')
        window_btn_frame.pack(side=tk.RIGHT, padx=15, pady=5)
        
        minimize_btn = tk.Button(window_btn_frame, text="─", bg='#1976D2', fg='white',
                 font=('Arial', 12), bd=0, cursor='hand2',
                 command=self.minimize_window)
        minimize_btn.pack(side=tk.LEFT, padx=5)
        
        self.maximized = False
        
        def toggle_maximize():
            self.maximized = not self.maximized
            if self.maximized:
                # 保存当前窗口位置和大小
                self._old_geometry = self.root.geometry()
                # 获取屏幕尺寸
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                # 最大化窗口（覆盖整个屏幕）
                self.root.geometry(f"{screen_width}x{screen_height}+0+0")
                maximize_btn.config(text="❐")
            else:
                # 恢复窗口
                if hasattr(self, '_old_geometry'):
                    self.root.geometry(self._old_geometry)
                maximize_btn.config(text="◻")
        
        maximize_btn = tk.Button(window_btn_frame, text="◻", bg='#1976D2', fg='white',
                 font=('Arial', 12), bd=0, cursor='hand2',
                 command=toggle_maximize)
        maximize_btn.pack(side=tk.LEFT, padx=5)
        
        close_btn = tk.Button(window_btn_frame, text="✕", bg='#1976D2', fg='white',
                 font=('Arial', 12), bd=0, cursor='hand2',
                 command=self.root.quit)
        close_btn.pack(side=tk.LEFT, padx=5)
        
        minimize_btn.bind('<Enter>', lambda e: minimize_btn.config(bg='#1565C0'))
        minimize_btn.bind('<Leave>', lambda e: minimize_btn.config(bg='#1976D2'))
        maximize_btn.bind('<Enter>', lambda e: maximize_btn.config(bg='#1565C0'))
        maximize_btn.bind('<Leave>', lambda e: maximize_btn.config(bg='#1976D2'))
        close_btn.bind('<Enter>', lambda e: close_btn.config(bg='#D32F2F'))
        close_btn.bind('<Leave>', lambda e: close_btn.config(bg='#1976D2'))
        
        self._dragging = False
        self._drag_start_x = 0
        self._drag_start_y = 0
        
        def on_mouse_press(event):
            self._dragging = True
            self._drag_start_x = event.x
            self._drag_start_y = event.y
        
        def on_mouse_release(event):
            self._dragging = False
        
        def on_mouse_move(event):
            if self._dragging:
                x = self.root.winfo_x() - self._drag_start_x + event.x
                y = self.root.winfo_y() - self._drag_start_y + event.y
                self.root.geometry(f'+{x}+{y}')
        
        header_frame.bind('<ButtonPress-1>', on_mouse_press)
        header_frame.bind('<ButtonRelease-1>', on_mouse_release)
        header_frame.bind('<B1-Motion>', on_mouse_move)
        
        logo_label.bind('<ButtonPress-1>', on_mouse_press)
        logo_label.bind('<ButtonRelease-1>', on_mouse_release)
        logo_label.bind('<B1-Motion>', on_mouse_move)
        
        nav_frame.bind('<ButtonPress-1>', on_mouse_press)
        nav_frame.bind('<ButtonRelease-1>', on_mouse_release)
        nav_frame.bind('<B1-Motion>', on_mouse_move)
        
        for child in nav_frame.winfo_children():
            child.bind('<ButtonPress-1>', on_mouse_press)
            child.bind('<ButtonRelease-1>', on_mouse_release)
            child.bind('<B1-Motion>', on_mouse_move)
        
        content_frame = tk.Frame(main_container, bg='#f5f5f5')
        content_frame.pack(fill=tk.BOTH, expand=True)
        
        left_panel = tk.Frame(content_frame, width=320, bg='white')
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)
        
        # 右侧多页面容器
        right_container = tk.Frame(content_frame, bg='#E3F2FD')
        right_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 创建多个页面框架
        self.main_page = tk.Frame(right_container, bg='#E3F2FD')
        self.main_page.pack(fill=tk.BOTH, expand=True)
        
        self.settings_page = ttk.Frame(right_container)
        
        self.download_page = ttk.Frame(right_container)
        
        # 默认显示主页面
        self.current_page = self.main_page
        
        right_panel = self.main_page
        
        mode_frame = tk.Frame(left_panel, bg='white')
        mode_frame.pack(fill=tk.X, padx=20, pady=15)
        
        self.online_btn = tk.Button(mode_frame, text="🛡 正版", 
                                   bg='white', fg='#1976D2',
                                   font=('Microsoft YaHei', 10),
                                   bd=1, relief='solid', cursor='hand2',
                                   command=self.show_no_open)
        self.online_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        self.offline_btn = tk.Button(mode_frame, text="🔗 离线", 
                                    bg='#1976D2', fg='white',
                                    font=('Microsoft YaHei', 10, 'bold'),
                                    bd=1, relief='solid', cursor='hand2',
                                    command=self.toggle_offline_mode)
        self.offline_btn.pack(side=tk.LEFT)
        
        skin_frame = tk.Frame(left_panel, bg='white')
        skin_frame.pack(pady=20)
        
        self.skin_preview_label = tk.Label(skin_frame, text="👤", 
                                          bg='#E3F2FD',
                                          font=('Segoe UI Emoji', 48),
                                          relief='flat',
                                          width=4, height=2)
        self.skin_preview_label.pack()
        
        self.skin_preview_label.bind('<Button-1>', lambda e: self.select_skin())
        
        ttk.Label(skin_frame, text="点击更换皮肤", 
                 font=('Microsoft YaHei', 8), 
                 foreground='#999').pack(pady=5)
        
        ttk.Label(skin_frame, text="玩家昵称:", 
                 font=('Microsoft YaHei', 9)).pack(anchor=tk.W, pady=(0, 5))
        
        self.nickname_entry = ttk.Entry(skin_frame, 
                                       font=('Microsoft YaHei', 10),
                                       width=25)
        self.nickname_entry.insert(0, "Player")
        self.nickname_entry.pack(fill=tk.X, ipady=5)
        
        version_select_frame = tk.Frame(left_panel, bg='white')
        version_select_frame.pack(fill=tk.X, padx=20, pady=10)
        
        ttk.Label(version_select_frame, text="游戏版本:", 
                 font=('Microsoft YaHei', 9)).pack(anchor=tk.W, pady=(0, 5))
        
        self.version_combo = ttk.Combobox(version_select_frame, 
                                         font=('Microsoft YaHei', 10),
                                         state='readonly')
        self.version_combo.pack(fill=tk.X, ipady=5)
        self.version_combo.bind('<<ComboboxSelected>>', self.on_version_select)
        
        launch_big_frame = tk.Frame(left_panel, bg='white')
        launch_big_frame.pack(fill=tk.X, padx=20, pady=20)
        
        self.big_launch_btn = tk.Button(launch_big_frame, 
                                       text="启动游戏",
                                       bg='white', fg='#1976D2',
                                       font=('Microsoft YaHei', 12, 'bold'),
                                       bd=2, relief='solid',
                                       cursor='hand2',
                                       command=self.launch_game,
                                       height=2)
        self.big_launch_btn.pack(fill=tk.X, ipady=10)
        
        self.version_info_label = tk.Label(launch_big_frame,
                                          text="未选择版本",
                                          bg='white', fg='#999',
                                          font=('Microsoft YaHei', 9))
        self.version_info_label.pack(pady=(5, 0))
        
        bottom_btn_frame = tk.Frame(left_panel, bg='white')
        bottom_btn_frame.pack(fill=tk.X, padx=20, pady=10)
        
        self.console_text = tk.Text(right_panel, height=8, width=50, 
                                   state='disabled', bg='white',
                                   fg='#333', font=('Consolas', 9),
                                   relief='flat')
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # 程序启动时自动扫描 Minecraft 版本和 Java
        self.root.after(100, self.scan_minecraft_versions)
        self.root.after(500, self.auto_select_java)

    def init_minecraft_directory(self):
        """初始化 Minecraft 目录结构，如果不存在则创建"""
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        versions_dir = os.path.join(minecraft_dir, "versions")
        libraries_dir = os.path.join(minecraft_dir, "libraries")
        assets_dir = os.path.join(minecraft_dir, "assets")
        indexes_dir = os.path.join(assets_dir, "indexes")
        objects_dir = os.path.join(assets_dir, "objects")
        
        # 创建所有必需的目录
        directories = [
            minecraft_dir,
            versions_dir,
            libraries_dir,
            assets_dir,
            indexes_dir,
            objects_dir
        ]
        
        created_dirs = []
        for directory in directories:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
                created_dirs.append(os.path.basename(directory))
        
        if created_dirs:
            self.log_to_console(f"已创建 Minecraft 目录结构：{', '.join(created_dirs)}")
        else:
            self.log_to_console("Minecraft 目录已存在")
        
        # 检查是否需要下载资源文件（第一次运行时）
        self.root.after(1000, self.check_and_download_assets)
    
    def check_and_download_assets(self):
        """检查 assets 目录，如果是第一次运行则自动下载资源"""
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        assets_dir = os.path.join(minecraft_dir, "assets")
        indexes_dir = os.path.join(assets_dir, "indexes")
        objects_dir = os.path.join(assets_dir, "objects")
        
        # 创建必要的目录
        for directory in [minecraft_dir, assets_dir, indexes_dir, objects_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory, exist_ok=True)
        
        # 检查是否需要下载资源
        # 如果 indexes 或 objects 目录为空，则需要下载
        indexes_empty = not os.listdir(indexes_dir) if os.path.exists(indexes_dir) else True
        objects_empty = not os.listdir(objects_dir) if os.path.exists(objects_dir) else True
        
        # 如果任意一个目录为空，就触发下载
        if indexes_empty or objects_empty:
            # 扫描版本目录
            versions_path = os.path.join(minecraft_dir, "versions")
            if os.path.exists(versions_path) and os.listdir(versions_path):
                self.log_to_console("发现已安装的游戏版本，自动下载资源文件...")
                messagebox.showinfo("提示", "正在自动下载游戏资源文件，请稍候...")
                self.download_all_assets()
            else:
                self.log_to_console("未发现游戏版本，请先下载 Minecraft 版本")
                messagebox.showinfo("提示", "请先在\"下载\"页面下载 Minecraft 版本，然后会自动下载对应的游戏资源。")

    def log_to_console(self, message: str):
        """向控制台区域添加日志信息（已禁用）"""
        pass
    
    def minimize_window(self):
        """最小化窗口 - 无边框窗口兼容，使用 Windows API"""
        if sys.platform == 'win32' and ctypes_available:
            # 使用 Windows API 最小化无边框窗口
            hwnd = ctypes.windll.user32.FindWindowW(None, self.root.title())
            if hwnd:
                SW_SHOWMINIMIZED = 2
                ctypes.windll.user32.ShowWindow(hwnd, SW_SHOWMINIMIZED)
        else:
            # 非 Windows 平台尝试其他方法
            try:
                self.root.wm_state('iconic')
            except:
                pass
    
    def show_no_open():
        messagebox.showinfo("提示", "功能开发中，敬请期待！")
    
    def auto_select_java(self):
        """自动选择最适合的 Java 版本"""
        self.log_to_console("正在自动检测 Java 环境...")
        
        java_versions = self.GetJavaVersions()
        
        if not java_versions:
            self.log_to_console("警告：未找到已安装的 Java")
            self.selected_java_info = ("", "")
            return
        
        # 根据当前选中的 Minecraft 版本自动选择 Java
        mc_version = self.selected_mc_version
        
        if mc_version:
            # 提取主版本号
            try:
                version_parts = mc_version.split('.')
                if len(version_parts) >= 2:
                    mc_major = int(version_parts[1])
                else:
                    mc_major = 0
            except:
                mc_major = 0
            
            # Minecraft 版本对应的 Java 需求
            # 1.17+ 需要 Java 17
            # 1.12-1.16 推荐 Java 8
            # 1.8-1.11 需要 Java 8
            if mc_major >= 17:
                required_java = 17
                self.log_to_console(f"Minecraft {mc_version} 需要 Java 17+")
            elif mc_major >= 12:
                required_java = 8
                self.log_to_console(f"Minecraft {mc_version} 推荐 Java 8")
            else:
                required_java = 8
                self.log_to_console(f"Minecraft {mc_version} 需要 Java 8")
            
            # 优先选择符合要求的 Java 版本
            suitable_java = None
            fallback_java = None
            
            for display_name, java_home, java_major in java_versions:
                if java_major >= required_java:
                    if suitable_java is None or java_major > suitable_java[2]:
                        suitable_java = (display_name, java_home, java_major)
                elif java_major >= 8:
                    if fallback_java is None or java_major > fallback_java[2]:
                        fallback_java = (display_name, java_home, java_major)
            
            # 选择合适的 Java
            if suitable_java:
                self.selected_java_info = (f"Java {suitable_java[0]}", suitable_java[1])
                self.log_to_console(f"已自动选择：Java {suitable_java[0]}")
                self.log_to_console(f"Java 路径：{suitable_java[1]}")
            elif fallback_java:
                self.selected_java_info = (f"Java {fallback_java[0]}", fallback_java[1])
                self.log_to_console(f"未找到 Java {required_java}，已选择备用：Java {fallback_java[0]}")
                self.log_to_console(f"Java 路径：{fallback_java[1]}")
            else:
                # 使用最新的 Java 版本
                best_java = max(java_versions, key=lambda x: x[2])
                self.selected_java_info = (f"Java {best_java[0]}", best_java[1])
                self.log_to_console(f"已选择最新 Java: {best_java[0]}")
                self.log_to_console(f"Java 路径：{best_java[1]}")
        else:
            # 没有选中 MC 版本时，选择最新的 Java
            if java_versions:
                best_java = max(java_versions, key=lambda x: x[2])
                self.selected_java_info = (f"Java {best_java[0]}", best_java[1])
                self.log_to_console(f"已自动选择最新 Java: {best_java[0]}")
                self.log_to_console(f"Java 路径：{best_java[1]}")

    def toggle_offline_mode(self):
        """切换离线模式"""
        if self.offline_btn.cget('bg') == '#1976D2':
            self.offline_btn.config(bg='white', fg='#1976D2', font=('Microsoft YaHei', 10))
            self.online_btn.config(bg='#1976D2', fg='white', font=('Microsoft YaHei', 10, 'bold'))
        else:
            self.offline_btn.config(bg='#1976D2', fg='white', font=('Microsoft YaHei', 10, 'bold'))
            self.online_btn.config(bg='white', fg='#1976D2', font=('Microsoft YaHei', 10))

    def show_more_menu(self):
        """显示更多菜单"""
        self.log_to_console("显示更多菜单")
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="📁 打开 .minecraft", command=self.open_minecraft_dir)
        menu.add_command(label="🌐 下载依赖库", command=self.download_all_libraries)
        menu.add_command(label="📦 下载游戏资源", command=self.download_all_assets)
        menu.add_command(label="🎨 浏览皮肤", command=self.show_skin_browser)
        menu.add_separator()
        menu.add_command(label="ℹ️ 关于", command=self.show_about)
        menu.add_command(label="退出", command=self.root.quit)
            
        try:
            menu.post(self.root.winfo_rootx() + 600, self.root.winfo_rooty() + 40)
            self.log_to_console("菜单已显示")
        except Exception as e:
            self.log_to_console(f"显示菜单失败：{str(e)}")

    def on_version_select(self, event=None):
        """处理版本选择"""
        selected = self.version_combo.get()
        if selected:
            self.selected_mc_version = selected
            self.version_info_label.config(text=selected)
            self.log_to_console(f"已选择版本：{selected}")

    def show_version_selector(self):
        """显示版本选择器"""
        self.scan_minecraft_versions()

    def calculate_sha1(self, file_path):
        """计算文件的 SHA1 哈希值"""
        sha1_hash = hashlib.sha1()
        try:
            with open(file_path, "rb") as f:
                for chunk in iter(lambda: f.read(4096), b""):
                    sha1_hash.update(chunk)
            return sha1_hash.hexdigest()
        except Exception as e:
            self.log_to_console(f"计算 SHA1 失败：{str(e)}")
            return None

    def check_library_rules(self, rules):
        """检查库的下载规则，返回是否应该下载"""
        allow = True
        
        for rule in rules:
            action = rule.get('action', 'allow')
            os_rule = rule.get('os', {})
            
            if os_rule:
                os_name = os_rule.get('name', '')
                
                # 检查操作系统是否匹配
                if os_name == 'windows' and sys.platform != 'win32':
                    continue
                elif os_name == 'osx' and sys.platform != 'darwin':
                    continue
                elif os_name == 'linux' and sys.platform != 'linux':
                    continue
            
            if action == 'allow':
                allow = True
            elif action == 'disallow':
                allow = False
        
        return allow

    def download_libraries(self, libraries_info, libraries_dir):
        """从 Mojang 服务器下载所需的依赖库（多线程非阻塞版本）"""
        if not libraries_info:
            self.log_to_console("警告：无依赖库信息")
            return
        
        total_libs = len(libraries_info)
        lock = threading.Lock()
        progress_queue = Queue()
        
        def should_download(lib):
            if 'rules' in lib:
                if not self.check_library_rules(lib['rules']):
                    return False
            
            lib_name = lib.get('name', '')
            downloads = lib.get('downloads', {})
            artifact = downloads.get('artifact', {})
            
            if not artifact:
                parts = lib_name.split(':')
                if len(parts) >= 3:
                    group_id = parts[0].replace('.', '/')
                    artifact_id = parts[1]
                    version = parts[2]
                    classifier = parts[3] if len(parts) > 3 else None
                    
                    if classifier:
                        lib_path = os.path.join(libraries_dir, group_id, artifact_id, version, 
                                               f"{artifact_id}-{version}-{classifier}.jar")
                    else:
                        lib_path = os.path.join(libraries_dir, group_id, artifact_id, version,
                                               f"{artifact_id}-{version}.jar")
                    
                    return not os.path.exists(lib_path)
                return False
            
            lib_path_rel = artifact.get('path', '')
            lib_url = artifact.get('url', '')
            
            if not lib_path_rel and lib_name:
                parts = lib_name.split(':')
                if len(parts) >= 3:
                    group_id = parts[0].replace('.', '/')
                    artifact_id = parts[1]
                    version = parts[2]
                    classifier = parts[3] if len(parts) > 3 else None
                    
                    if classifier:
                        lib_path_rel = f"{group_id}/{artifact_id}/{version}/{artifact_id}-{version}-{classifier}.jar"
                    else:
                        lib_path_rel = f"{group_id}/{artifact_id}/{version}/{artifact_id}-{version}.jar"
                    lib_full_path = os.path.join(libraries_dir, lib_path_rel)
                else:
                    return False
            else:
                lib_full_path = os.path.join(libraries_dir, lib_path_rel)
            
            if not lib_url:
                return False
            
            return not os.path.exists(lib_full_path)
        
        def download_single_lib(lib, result_dict, index):
            try:
                lib_name = lib.get('name', '')
                downloads = lib.get('downloads', {})
                artifact = downloads.get('artifact', {})
                
                if not artifact:
                    parts = lib_name.split(':')
                    if len(parts) >= 3:
                        group_id = parts[0].replace('.', '/')
                        artifact_id = parts[1]
                        version = parts[2]
                        classifier = parts[3] if len(parts) > 3 else None
                        
                        if classifier:
                            lib_path = os.path.join(libraries_dir, group_id, artifact_id, version, 
                                                   f"{artifact_id}-{version}-{classifier}.jar")
                        else:
                            lib_path = os.path.join(libraries_dir, group_id, artifact_id, version,
                                                   f"{artifact_id}-{version}.jar")
                        
                        if not os.path.exists(lib_path):
                            with lock:
                                result_dict[index] = ('missing', lib_name)
                    return
                
                lib_path_rel = artifact.get('path', '')
                lib_url = artifact.get('url', '')
                lib_sha1 = artifact.get('sha1', '')
                
                if not lib_path_rel and lib_name:
                    parts = lib_name.split(':')
                    if len(parts) >= 3:
                        group_id = parts[0].replace('.', '/')
                        artifact_id = parts[1]
                        version = parts[2]
                        classifier = parts[3] if len(parts) > 3 else None
                        
                        if classifier:
                            lib_path_rel = f"{group_id}/{artifact_id}/{version}/{artifact_id}-{version}-{classifier}.jar"
                        else:
                            lib_path_rel = f"{group_id}/{artifact_id}/{version}/{artifact_id}-{version}.jar"
                        lib_full_path = os.path.join(libraries_dir, lib_path_rel)
                    else:
                        with lock:
                            result_dict[index] = ('failed', lib_name)
                        return
                else:
                    lib_full_path = os.path.join(libraries_dir, lib_path_rel)
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                req = urllib.request.Request(lib_url, headers=headers)
                
                os.makedirs(os.path.dirname(lib_full_path), exist_ok=True)
                
                with urllib.request.urlopen(req, timeout=30) as response:
                    with open(lib_full_path, 'wb') as out_file:
                        out_file.write(response.read())
                
                if lib_sha1 and os.path.exists(lib_full_path):
                    calculated_sha1 = self.calculate_sha1(lib_full_path)
                    if calculated_sha1 != lib_sha1:
                        self.log_to_console(f"警告：{lib_name} SHA1 验证失败")
                
                with lock:
                    result_dict[index] = ('success', lib_name)
                
                progress_queue.put(('downloading', lib_name))
                
            except Exception as e:
                with lock:
                    result_dict[index] = ('failed', lib_name)
                self.log_to_console(f"下载失败 {lib_name}: {str(e)}")
                progress_queue.put(('failed', lib_name))
        
        valid_libs = []
        for lib in libraries_info:
            if should_download(lib):
                valid_libs.append(lib)
        
        if not valid_libs:
            self.log_to_console(f"依赖库检查完成：所有库已就绪")
            return
        
        self.log_to_console(f"开始下载 {len(valid_libs)} 个依赖库...")
        
        result_dict = {}
        max_workers = min(16, len(valid_libs))
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(download_single_lib, lib, result_dict, i): i for i, lib in enumerate(valid_libs)}
            
            completed = 0
            for future in as_completed(futures):
                while not progress_queue.empty():
                    status, lib_name = progress_queue.get()
                    if status == 'downloading':
                        completed += 1
                        percentage = (completed / len(valid_libs)) * 100 if len(valid_libs) > 0 else 0
                        self.log_to_console(f"进度：{completed}/{len(valid_libs)} ({percentage:.1f}%) - {lib_name}")
        
        downloaded = sum(1 for v in result_dict.values() if v[0] == 'success')
        failed = sum(1 for v in result_dict.values() if v[0] == 'failed')
        missing = sum(1 for v in result_dict.values() if v[0] == 'missing')
        
        self.log_to_console(f"依赖库检查完成：{downloaded}/{total_libs} 个库已下载成功")
        if failed > 0:
            self.log_to_console(f"警告：{failed} 个库下载失败")
        if missing > 0:
            self.log_to_console(f"提示：{missing} 个库缺少下载信息但文件不存在")

    def fetch_version_manifest(self):
        """从 Mojang 获取版本清单"""
        manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
        
        try:
            self.log_to_console("正在连接 Mojang 版本清单服务器...")
            
            # 创建请求头
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = urllib.request.Request(manifest_url, headers=headers)
            
            # 获取清单数据
            with urllib.request.urlopen(req, timeout=10) as response:
                manifest_data = json.loads(response.read().decode('utf-8'))
            
            self.log_to_console(f"成功获取版本清单，包含 {len(manifest_data.get('versions', []))} 个版本")
            return manifest_data
            
        except Exception as e:
            self.log_to_console(f"获取版本清单失败：{str(e)}")
            messagebox.showerror("网络错误", f"无法连接 Mojang 服务器:\n{str(e)}")
            return None

    def download_version_from_manifest(self, version_id):
        """从版本清单下载指定版本的详细信息"""
        manifest = self.fetch_version_manifest()
        if not manifest:
            return None
        
        # 查找指定版本
        version_url = None
        for version in manifest.get('versions', []):
            if version.get('id') == version_id:
                version_url = version.get('url')
                break
        
        if not version_url:
            self.log_to_console(f"未在清单中找到版本：{version_id}")
            return None
        
        try:
            self.log_to_console(f"正在下载 {version_id} 的版本信息...")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = urllib.request.Request(version_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                version_data = json.loads(response.read().decode('utf-8'))
            
            self.log_to_console(f"成功下载 {version_id} 的版本配置")
            return version_data
            
        except Exception as e:
            self.log_to_console(f"下载版本信息失败：{str(e)}")
            return None

    def download_all_libraries(self):
        """为当前选择的版本下载所有依赖库"""
        if not self.selected_mc_version:
            messagebox.showwarning("未选择版本", "请先选择一个 Minecraft 版本。")
            self.log_to_console("下载失败：未选择 Minecraft 版本。")
            return
        
        # 在新线程中执行下载，避免界面卡死
        threading.Thread(target=self._do_download_libraries, daemon=True).start()

    def _do_download_libraries(self):
        """在后台线程中执行依赖库下载"""
        self.log_to_console("=" * 50)
        self.log_to_console(f"开始下载 {self.selected_mc_version} 的依赖库...")
        
        # 设置目录
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        libraries_dir = os.path.join(minecraft_dir, "libraries")
        version_dir = os.path.join(minecraft_dir, "versions", self.selected_mc_version)
        version_json = os.path.join(version_dir, f"{self.selected_mc_version}.json")
        
        # 首先尝试读取本地版本配置
        libraries_info = []
        if os.path.exists(version_json):
            try:
                with open(version_json, 'r') as f:
                    version_data = json.load(f)
                libraries_info = version_data.get('libraries', [])
                self.log_to_console(f"从本地配置找到 {len(libraries_info)} 个依赖库")
            except Exception as e:
                self.log_to_console(f"读取本地配置失败：{str(e)}")
        
        # 如果本地没有，则从在线获取
        if not libraries_info:
            self.log_to_console("本地配置无依赖库信息，正在从 Mojang 获取...")
            version_data_online = self.download_version_from_manifest(self.selected_mc_version)
            
            if version_data_online:
                libraries_info = version_data_online.get('libraries', [])
                self.log_to_console(f"从在线清单找到 {len(libraries_info)} 个依赖库")
            else:
                self.log_to_console("无法获取版本依赖库信息")
                return
        
        # 确保 libraries 目录存在
        os.makedirs(libraries_dir, exist_ok=True)
        
        # 下载依赖库
        self.download_libraries(libraries_info, libraries_dir)
        
        self.log_to_console("依赖库下载完成")
        messagebox.showinfo("下载完成", f"依赖库下载完成！\n位置：.minecraft/libraries")

    def download_all_assets(self):
        """下载所有游戏资源"""
        # 确保版本选择
        if not hasattr(self, 'selected_mc_version') or not self.selected_mc_version:
            self.log_to_console("未选择 Minecraft 版本")
            return
        
        # 获取版本配置
        version_data = self.download_version_from_manifest(self.selected_mc_version)
        if not version_data:
            self.log_to_console("无法获取版本配置")
            return
        
        # 下载资源
        self._do_download_assets()

    def _do_download_assets(self):
        """在后台线程中执行资源文件下载（修复UI元素未定义问题）"""
        self.log_to_console("=" * 50)
        self.log_to_console(f"开始下载 {self.selected_mc_version} 的游戏资源...")
        
        # 设置目录
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        assets_dir = os.path.join(minecraft_dir, "assets")
        indexes_dir = os.path.join(assets_dir, "indexes")
        objects_dir = os.path.join(assets_dir, "objects")
        version_dir = os.path.join(minecraft_dir, "versions", self.selected_mc_version)
        version_json = os.path.join(version_dir, f"{self.selected_mc_version}.json")
            
        # 确保目录存在
        os.makedirs(indexes_dir, exist_ok=True)
        os.makedirs(objects_dir, exist_ok=True)
        
        # 读取版本配置获取 assetIndex 信息
        asset_index_id = "legacy"  # 默认值
        asset_index_url = None
        asset_index_info = None
        
        if os.path.exists(version_json):
            try:
                with open(version_json, 'r') as f:
                    version_data = json.load(f)
                    asset_index_info = version_data.get('assetIndex', {})
                    asset_index_id = asset_index_info.get('id', 'legacy')
                    asset_index_url = asset_index_info.get('url')  # 获取资源索引的 URL
                    self.log_to_console(f"检测到资源索引版本：{asset_index_id}")
            except Exception as e:
                self.log_to_console(f"读取版本配置失败：{str(e)}")
        else:
            self.log_to_console("本地版本配置不存在，正在从 Mojang 获取...")
            version_data_online = self.download_version_from_manifest(self.selected_mc_version)
            if version_data_online:
                asset_index_info = version_data_online.get('assetIndex', {})
                asset_index_id = asset_index_info.get('id', 'legacy')
                asset_index_url = asset_index_info.get('url')
        
        index_data = None
        if asset_index_url:
            try:
                self.log_to_console(f"正在下载资源索引: {asset_index_id}")
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                }
                req = urllib.request.Request(asset_index_url, headers=headers)
                
                with urllib.request.urlopen(req, timeout=10) as response:
                    index_data = json.loads(response.read().decode('utf-8'))
                
                # 保存索引文件
                index_file_path = os.path.join(indexes_dir, f"{asset_index_id}.json")
                with open(index_file_path, 'w') as f:
                    json.dump(index_data, f, indent=2)
                
                self.log_to_console(f"资源索引已保存到 {index_file_path}")
                
            except Exception as e:
                self.log_to_console(f"下载资源索引失败：{str(e)}")
                messagebox.showerror("下载失败", f"无法下载资源索引文件：\n{str(e)}")
                return
        
        # 如果没有从版本配置获取索引，尝试使用默认的索引
        if not index_data:
            index_file = os.path.join(indexes_dir, f"{asset_index_id}.json")
            if os.path.exists(index_file):
                try:
                    with open(index_file, 'r') as f:
                        index_data = json.load(f)
                    self.log_to_console(f"使用本地资源索引：{asset_index_id}")
                except Exception as e:
                    self.log_to_console(f"读取本地资源索引失败：{str(e)}")
        
        if not index_data:
            self.log_to_console("无法获取资源索引数据")
            messagebox.showerror("错误", "无法获取游戏资源索引，请检查网络连接或重新下载版本。")
            return
        
        # 获取所有资源对象
        objects = index_data.get('objects', {})
        total_objects = len(objects)
            
        if total_objects == 0:
            self.log_to_console("警告：资源索引中没有任何对象")
            return
        
        self.log_to_console(f"发现 {total_objects} 个基础资源文件，开始下载...")
        
        # 统计需要下载的文件
        files_to_download = []
        for name, obj in objects.items():
            hash_value = obj.get('hash', '')
            if not hash_value:
                continue
                
            hash_prefix = hash_value[:2]
            object_dir = os.path.join(objects_dir, hash_prefix)
            object_path = os.path.join(object_dir, hash_value)
                
            # 如果文件不存在才下载
            if not os.path.exists(object_path):
                files_to_download.append((name, hash_value, hash_prefix))
        
        # 处理新版资源格式 (1.19+) 的 map_to_resources
        if 'map_to_resources' in index_data and index_data['map_to_resources']:
            for name, obj in index_data['map_to_resources'].get('objects', {}).items():
                hash_value = obj.get('hash', '')
                if not hash_value:
                    continue
                    
                hash_prefix = hash_value[:2]
                object_dir = os.path.join(objects_dir, hash_prefix)
                object_path = os.path.join(object_dir, hash_value)
                    
                # 如果文件不存在才下载
                if not os.path.exists(object_path):
                    files_to_download.append((name, hash_value, hash_prefix))
        
        if not files_to_download:
            self.log_to_console("所有资源文件已存在，无需下载")
            messagebox.showinfo("下载完成", f"游戏资源已完整！\n位置：.minecraft/assets")
            return
            
        self.log_to_console(f"需要下载 {len(files_to_download)} 个资源文件...")
        
        # 定义多个下载源，按优先级排序
        download_sources = [
            "https://bmclapi2.bangbang93.com/assets/",
            "https://resources.download.minecraft.net/",
            "https://launcher.mojang.com/v1/packages/"
        ]
        
        # 下载资源文件
        downloaded = 0
        failed = 0
        max_retries = 3  # 每个文件最大重试次数
        
        # 更新UI状态（安全检查）
        if hasattr(self, 'status_label') and self.status_label:
            self.root.after(0, lambda: self.status_label.config(text=f"正在下载游戏资源..."))
        
        for i, (name, hash_value, hash_prefix) in enumerate(files_to_download):
            object_dir = os.path.join(objects_dir, hash_prefix)
            object_path = os.path.join(object_dir, hash_value)
            
            try:
                os.makedirs(object_dir, exist_ok=True)
                
                # 尝试从多个源下载
                success = False
                for source_index, base_url in enumerate(download_sources):
                    for retry in range(max_retries):
                        try:
                            url = f"{base_url}{hash_value}"
                            headers = {
                                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                            }
                            
                            # 实际下载文件
                            req = urllib.request.Request(url, headers=headers)
                            with urllib.request.urlopen(req, timeout=30) as response:
                                data = response.read()
                                
                            # 将下载的数据写入文件
                            with open(object_path, 'wb') as f:
                                f.write(data)
                                
                            downloaded += 1
                            percentage = (downloaded / len(files_to_download)) * 100
                            self.log_to_console(f"进度：{i + 1}/{len(files_to_download)} ({percentage:.1f}%) - 成功 {downloaded} 个")
                            
                            # 更新UI（安全检查）
                            if hasattr(self, 'progress_var') and self.progress_var:
                                self.root.after(0, lambda p=percentage: self.progress_var.set(p))
                            if hasattr(self, 'status_label') and self.status_label:
                                self.root.after(0, lambda msg=f"下载中... {i + 1}/{len(files_to_download)} ({percentage:.1f}%)": 
                                                self.status_label.config(text=msg))
                            
                            success = True
                            break  # 成功下载，跳出重试循环
                        
                        except urllib.error.HTTPError as e:
                            self.log_to_console(f"HTTP 错误下载 {name} (来源 {source_index + 1}): {e.code} - {e.reason}")
                            if e.code == 404 and source_index < len(download_sources) - 1:
                                break  # 跳出重试循环，尝试下一个源
                            elif retry < max_retries - 1:
                                self.log_to_console(f"重试 {retry + 1}/{max_retries}...")
                                time.sleep(1)  # 等待1秒再重试
                        except urllib.error.URLError as e:
                            self.log_to_console(f"URL 错误下载 {name} (来源 {source_index + 1}): {e.reason}")
                            if retry < max_retries - 1:
                                self.log_to_console(f"重试 {retry + 1}/{max_retries}...")
                                time.sleep(2)  # 等待2秒再重试
                        except Exception as e:
                            self.log_to_console(f"未知错误下载 {name} (来源 {source_index + 1}): {str(e)}")
                            if retry < max_retries - 1:
                                self.log_to_console(f"重试 {retry + 1}/{max_retries}...")
                                time.sleep(3)  # 等待3秒再重试
                    
                    if success:
                        break  # 成功下载，跳出源切换循环
                
                if not success:
                    failed += 1
                    self.log_to_console(f"所有来源均无法下载 {name}")
                    
            except Exception as e:
                failed += 1
                self.log_to_console(f"处理 {name} 时发生错误：{str(e)}")
        
        self.log_to_console(f"资源下载完成：成功 {downloaded} 个，失败 {failed} 个")
        
        # 更新UI（安全检查）
        if hasattr(self, 'progress_var') and self.progress_var:
            self.root.after(0, lambda: self.progress_var.set(100))
        
        if failed == 0:
            # 更新UI（安全检查）
            if hasattr(self, 'status_label') and self.status_label:
                self.root.after(0, lambda: self.status_label.config(text="✓ 资源下载完成！"))
            self.log_to_console("所有资源下载成功")
            messagebox.showinfo("下载完成", 
                f"游戏资源下载完成！\n"
                f"成功：{downloaded} 个\n"
                f"位置：.minecraft/assets")
        else:
            # 更新UI（安全检查）
            if hasattr(self, 'status_label') and self.status_label:
                self.root.after(0, lambda: self.status_label.config(text=f"✗ 部分资源下载失败（{failed}个）"))
            self.log_to_console("部分资源下载失败，建议重新尝试下载")
            messagebox.showwarning("下载不完整", 
                f"部分资源下载失败（{failed} 个），游戏可能无法正常运行。\n"
                "建议检查网络连接后重新尝试下载。\n"
                "已成功下载的资源可以正常使用。")
        
        # 检查是否需要下载额外的资源
        if failed > 0:
            self.log_to_console("部分资源下载失败，建议重新尝试下载")
        else:
            self.log_to_console("所有资源下载成功，可以启动游戏")
            
            # 如果是从自动下载触发的，提示用户可以启动
            if self.current_page == self.main_page:
                self.root.after(0, lambda: messagebox.showinfo(
                    "资源准备就绪", 
                    f"游戏资源已全部下载完成！\n"
                    f"现在可以点击'启动游戏'按钮开始游戏。"
                ))
            
    def scan_minecraft_versions(self):
        """扫描 Minecraft 版本并更新下拉框"""
        self.log_to_console("正在扫描 Minecraft 版本...")
        
        current_dir = os.getcwd()
        versions_path = os.path.join(current_dir, ".minecraft", "versions")
        
        if not os.path.exists(versions_path):
            self.log_to_console(f"错误：未找到版本目录 {versions_path}")
            messagebox.showerror("路径错误", f"未找到 Minecraft 版本目录:\n{versions_path}")
            return
        
        try:
            folders = []
            for item in os.listdir(versions_path):
                item_path = os.path.join(versions_path, item)
                if os.path.isdir(item_path):
                    folders.append(item)
            
            if not folders:
                self.version_combo['values'] = []
                self.log_to_console("未找到任何游戏版本。")
                messagebox.showinfo("提示", "未找到任何 Minecraft 版本。")
            else:
                sorted_folders = sorted(folders, reverse=True)
                self.version_combo['values'] = sorted_folders
                self.log_to_console(f"找到 {len(sorted_folders)} 个 Minecraft 版本。")
                
                if sorted_folders:
                    self.version_combo.current(0)
                    self.on_version_select()
                    
        except Exception as e:
            self.log_to_console(f"扫描时发生错误：{str(e)}")
            messagebox.showerror("扫描错误", str(e))

    def check_java_version(self, java_path):
        """检查 Java 版本，返回 (主版本号，完整版本字符串)"""
        try:
            result = subprocess.run(
                [java_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            # Java 8 输出到 stderr，Java 9+ 输出到 stdout
            version_output = result.stderr if result.stderr else result.stdout
            
            # 解析版本号
            for line in version_output.split('\n'):
                if 'version' in line.lower():
                    # 提取版本号，如 "1.8.0_341" 或 "17.0.5"
                    parts = line.split('"')
                    if len(parts) > 1:
                        version_str = parts[1]
                        # 处理 Java 9+ 的新版本格式
                        if version_str.startswith('1.'):
                            major_version = int(version_str.split('.')[1])
                        else:
                            major_version = int(version_str.split('.')[0])
                        
                        self.log_to_console(f"检测到 Java 版本：{version_str} (主版本：{major_version})")
                        return (major_version, version_str)
            
            return None
        except Exception as e:
            self.log_to_console(f"检查 Java 版本失败：{str(e)}")
            return None

    def get_required_java_version(self, mc_version):
        """根据 Minecraft 版本返回所需的最低 Java 版本"""
        try:
            # 解析版本号
            version_parts = mc_version.replace('.', '-').split('-')
            
            # 1.17 及以上需要 Java 17
            if len(version_parts) >= 2:
                try:
                    minor_version = int(version_parts[1])
                    if minor_version >= 17:
                        return 17
                    elif minor_version >= 12:
                        return 8  # 1.12-1.16 推荐 Java 8
                    else:
                        return 8
                except ValueError:
                    pass
            
            # 默认返回 Java 8
            return 8
        except Exception as e:
            self.log_to_console(f"判断 Java 版本需求失败：{str(e)}")
            return 8


    def GetJavaVersions(self):
        """
        查询 Windows 注册表，获取所有已安装的 Java 版本（JDK & JRE）。
        返回一个列表，元素为 (显示名称，安装路径，主版本号)
        """
        java_versions = []
        
        if not WINDOWS_MODE:
            self.log_to_console("警告：非 Windows 系统，无法通过注册表检测 Java。")
            return java_versions

        # === 1. 注册表扫描 ===
        reg_keys = [
            # 64 位 JDK/JRE
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Development Kit"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Runtime Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\JRE"),
            
            # Eclipse Adoptium (Temurin)
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Eclipse Adoptium\JDK"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Eclipse Adoptium\JRE"),
            
            # Oracle OpenJDK
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Oracle\Java"),
            
            # Microsoft Build of OpenJDK
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\JDK"),
            
            # Azul Zulu
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Azul Systems\Zulu"),
            
            # Amazon Corretto
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Amazon\Corretto"),
            
            # 32 位程序在 64 位系统上的重定向
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\JavaSoft\Java Development Kit"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\JavaSoft\Java Runtime Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\JavaSoft\JRE"),
            
            # 当前用户配置
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\JavaSoft\Java Development Kit"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\JavaSoft\Java Runtime Environment"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\JavaSoft\JRE"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Eclipse Adoptium\JDK"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Eclipse Adoptium\JRE"),
        ]

        for hive, subkey in reg_keys:
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    i = 0
                    while True:
                        try:
                            version = winreg.EnumKey(key, i)
                            version_key_path = f"{subkey}\\{version}"
                            with winreg.OpenKey(hive, version_key_path) as ver_key:
                                try:
                                    java_home = None
                                    possible_names = ["JavaHome", "INSTALLDIR", "Path"]
                                    
                                    for name in possible_names:
                                        try:
                                            java_home, _ = winreg.QueryValueEx(ver_key, name)
                                            if java_home and os.path.exists(java_home):
                                                break
                                        except FileNotFoundError:
                                            continue
                                    
                                    if not java_home:
                                        i += 1
                                        continue
                                    
                                    java_exe_path = os.path.join(java_home, "bin", "java.exe")
                                    
                                    if os.path.exists(java_exe_path):
                                        if "Development" in subkey or "JDK" in subkey:
                                            jtype = "JDK"
                                        elif "Eclipse" in subkey:
                                            jtype = "Temurin"
                                        elif "Microsoft" in subkey:
                                            jtype = "Microsoft JDK"
                                        elif "Azul" in subkey:
                                            jtype = "Zulu"
                                        elif "Amazon" in subkey:
                                            jtype = "Corretto"
                                        elif "Oracle" in subkey:
                                            jtype = "Oracle"
                                        else:
                                            jtype = "JRE"
                                        
                                        try:
                                            if version.startswith('1.'):
                                                java_major = int(version.split('.')[1])
                                            else:
                                                java_major = int(version.split('.')[0])
                                        except:
                                            java_major = 0
                                        
                                        display_name = f"Java {version} ({jtype})"
                                        
                                        if not any(v[1] == java_home for v in java_versions):
                                            java_versions.append((display_name, java_home, java_major))
                                            self.log_to_console(f"注册表发现：{display_name}")
                                except FileNotFoundError:
                                    pass
                            i += 1
                        except OSError:
                            break
            except FileNotFoundError:
                continue
            except OSError:
                continue

        # === 2. 环境变量 PATH 扫描 ===
        self.log_to_console("正在扫描环境变量 PATH...")
        path_env = os.environ.get("PATH", "")
        for path_dir in path_env.split(os.pathsep):
            path_dir = path_dir.strip()
            if path_dir and os.path.exists(path_dir):
                java_exe = os.path.join(path_dir, "java.exe")
                if os.path.exists(java_exe):
                    java_home = os.path.dirname(os.path.dirname(java_exe))
                    version_info = self.check_java_version(java_exe)
                    if version_info:
                        java_major = version_info[0]
                        display_name = f"Java {version_info[1]} (PATH)"
                        if not any(v[1] == java_home for v in java_versions):
                            java_versions.append((display_name, java_home, java_major))
                            self.log_to_console(f"PATH 发现：{display_name}")

        # === 3. 遍历所有磁盘驱动器 ===
        self.log_to_console("正在扫描所有磁盘驱动器...")
        drives = self.get_all_drives()
        common_java_paths = [
            "Program Files\\Java",
            "Program Files (x86)\\Java",
            "Program Files\\Eclipse Adoptium",
            "Program Files\\Microsoft\\JDK",
            "Program Files\\Azul\\Zulu",
            "Program Files\\Amazon Corretto",
            "Users\\Public\\jdk",
        ]
        
        for drive in drives:
            for common_path in common_java_paths:
                full_path = os.path.join(drive, common_path)
                if os.path.exists(full_path):
                    found = self.scan_directory_for_java(full_path, java_versions, f"磁盘 {drive}")
                    if found > 0:
                        self.log_to_console(f"磁盘 {drive} 找到 {found} 个 Java")

        # === 4. 搜索 .jdks 文件夹（用户目录） ===
        user_home = os.path.expanduser("~")
        jdks_path = os.path.join(user_home, ".jdks")
        if os.path.exists(jdks_path):
            self.log_to_console(f"正在扫描 .jdks 目录：{jdks_path}")
            self.scan_directory_for_java(jdks_path, java_versions, ".jdks")

        # === 5. 搜索 APPDATA 文件夹 ===
        appdata = os.getenv("APPDATA", "")
        if appdata:
            self.log_to_console(f"正在扫描 APPDATA: {appdata}")
            
            # .minecraft runtime
            minecraft_runtime = os.path.join(appdata, ".minecraft", "runtime")
            if os.path.exists(minecraft_runtime):
                self.scan_directory_for_java(minecraft_runtime, java_versions, "minecraft runtime")
            
            # Eclipse Temurin
            temurin_path = os.path.join(appdata, "..", "Local", "Programs", "Eclipse Adoptium")
            if os.path.exists(temurin_path):
                self.scan_directory_for_java(temurin_path, java_versions, "Temurin")

        # === 6. 搜索启动器目录 ===
        launcher_dirs = [
            os.path.join(user_home, ".hmcl"),
            os.path.join(user_home, ".pcl"),
            os.path.join(os.getcwd(), "runtime"),
            os.path.join(os.getcwd(), "jre"),
            os.path.join(os.getcwd(), "java"),
        ]
        
        for launcher_dir in launcher_dirs:
            if os.path.exists(launcher_dir):
                self.log_to_console(f"扫描启动器目录：{launcher_dir}")
                self.scan_directory_for_java(launcher_dir, java_versions, "launcher")

        # === 7. 搜索 Minecraft 文件夹 ===
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        if os.path.exists(minecraft_dir):
            runtime_dir = os.path.join(minecraft_dir, "runtime")
            jre_dir = os.path.join(minecraft_dir, "jre")
            
            for mc_java_dir in [runtime_dir, jre_dir]:
                if os.path.exists(mc_java_dir):
                    self.log_to_console(f"扫描 Minecraft Java 目录：{mc_java_dir}")
                    self.scan_directory_for_java(mc_java_dir, java_versions, "minecraft")

        self.log_to_console(f"共找到 {len(java_versions)} 个 Java 安装")
        return java_versions

    def get_all_drives(self):
        """获取所有磁盘驱动器"""
        drives = []
        if sys.platform == 'win32':
            import string
            for letter in string.ascii_uppercase:
                drive = f"{letter}:\\"
                if os.path.exists(drive):
                    drives.append(drive)
        else:
            drives = ["/"]
        return drives

    def scan_directory_for_java(self, directory, java_versions, source="未知"):
        """递归扫描目录查找 Java 安装"""
        found_count = 0
        
        if not os.path.exists(directory):
            return 0
        
        try:
            for root, dirs, files in os.walk(directory):
                # 限制递归深度（最多 5 层）
                depth = root.replace(directory, '').count(os.sep)
                if depth > 5:
                    dirs[:] = []  # 停止深入
                else:
                    # 检查当前目录是否有 java.exe
                    java_exe = os.path.join(root, "bin", "java.exe")
                    if os.path.exists(java_exe):
                        version_info = self.check_java_version(java_exe)
                        if version_info:
                            java_major = version_info[0]
                            java_home = os.path.dirname(os.path.dirname(java_exe))
                            
                            # 生成显示名称
                            dir_name = os.path.basename(root)
                            display_name = f"Java {version_info[1]} ({source}: {dir_name})"
                            
                            # 去重
                            if not any(v[1] == java_home for v in java_versions):
                                java_versions.append((display_name, java_home, java_major))
                                self.log_to_console(f"[{source}] 发现：{display_name}")
                                found_count += 1
                    
                    # 优化：跳过一些明显不包含 Java 的目录
                    skip_dirs = ['.git', 'node_modules', '__pycache__', '.vscode', 
                                '.idea', 'target', 'build', 'dist']
                    dirs[:] = [d for d in dirs if d not in skip_dirs]
                
        except PermissionError:
            pass
        except Exception as e:
            self.log_to_console(f"扫描目录失败 {directory}: {str(e)}")
        
        return found_count

    def check_java_version(self, java_path):
        """检查 Java 版本，返回 (主版本号，完整版本字符串)"""
        try:
            result = subprocess.run(
                [java_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            version_output = result.stderr if result.stderr else result.stdout
            
            for line in version_output.split('\n'):
                if 'version' in line.lower():
                    parts = line.split('"')
                    if len(parts) > 1:
                        version_str = parts[1]
                        if version_str.startswith('1.'):
                            major_version = int(version_str.split('.')[1])
                        else:
                            major_version = int(version_str.split('.')[0])
                        
                        self.log_to_console(f"检测到 Java 版本：{version_str} (主版本：{major_version})")
                        return (major_version, version_str)
            
            return None
        except Exception as e:
            self.log_to_console(f"检查 Java 版本失败：{str(e)}")
            return None

    def check_java_version(self, java_path):
        """检查 Java 版本，返回 (主版本号，完整版本字符串)"""
        try:
            result = subprocess.run(
                [java_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0
            )
            
            version_output = result.stderr if result.stderr else result.stdout
            
            for line in version_output.split('\n'):
                if 'version' in line.lower():
                    parts = line.split('"')
                    if len(parts) > 1:
                        version_str = parts[1]
                        if version_str.startswith('1.'):
                            major_version = int(version_str.split('.')[1])
                        else:
                            major_version = int(version_str.split('.')[0])
                        
                        self.log_to_console(f"检测到 Java 版本：{version_str} (主版本：{major_version})")
                        return (major_version, version_str)
            
            return None
        except Exception as e:
            self.log_to_console(f"检查 Java 版本失败：{str(e)}")
            return None

    def launch_game(self):
        """启动游戏"""
        if not self.selected_mc_version:
            messagebox.showwarning("未选择版本", "请先选择一个 Minecraft 版本。")
            self.log_to_console("启动失败：未选择 Minecraft 版本。")
            return

        # 获取玩家昵称
        self.player_nickname = self.nickname_entry.get().strip()
        if not self.player_nickname:
            self.player_nickname = "Player"
            self.nickname_entry.delete(0, tk.END)
            self.nickname_entry.insert(0, "Player")

        self.log_to_console("=" * 50)
        self.log_to_console(f"启动 Minecraft {self.selected_mc_version} ...")
        self.log_to_console(f"玩家昵称：{self.player_nickname}")

        # 1. 确定 Java 路径并检查版本兼容性
        required_java_version = self.get_required_java_version(self.selected_mc_version)
        
        if self.selected_java_info[1]:
            java_exe = os.path.join(self.selected_java_info[1], "bin", "java.exe" if sys.platform == 'win32' else "java")
        else:
            java_exe = "java"
        
        # 检查 Java 版本是否兼容
        java_version_info = self.check_java_version(java_exe)
        if java_version_info:
            current_version = java_version_info[0]
            self.log_to_console(f"当前 Java 版本：{current_version}")
            
            if required_java_version and current_version < required_java_version:
                self.log_to_console(f"警告：Minecraft {self.selected_mc_version} 需要 Java {required_java_version} 或更高版本")
                messagebox.showwarning(
                    "Java 版本不兼容",
                    f"Minecraft {self.selected_mc_version} 需要 Java {required_java_version} 或更高版本。\n"
                    f"当前使用的 Java 版本为 {current_version}。\n\n"
                    f"请在控制面板中选择合适的 Java 版本后重新启动。"
                )
                return

        # 2. 设置 Minecraft 目录结构
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        versions_dir = os.path.join(minecraft_dir, "versions")
        version_dir = os.path.join(versions_dir, self.selected_mc_version)
        assets_dir = os.path.join(minecraft_dir, "assets")
        libraries_dir = os.path.join(minecraft_dir, "libraries")
        
        # 3. 检查必要文件
        version_json = os.path.join(version_dir, f"{self.selected_mc_version}.json")
        version_jar = os.path.join(version_dir, f"{self.selected_mc_version}.jar")
        natives_dir = os.path.join(version_dir, f"{self.selected_mc_version}-natives")
        
        if not os.path.exists(version_json):
            self.log_to_console(f"错误：未找到版本配置文件 {version_json}")
            messagebox.showerror("配置错误", "无法找到版本配置文件。请重新安装该版本。")
            return
        
        if not os.path.exists(version_jar):
            self.log_to_console(f"错误：未找到游戏核心文件 {version_jar}")
            messagebox.showerror("文件缺失", "无法找到游戏核心文件。请重新安装该版本。")
            return
        
        # 检查 libraries 目录
        if not os.path.exists(libraries_dir) or not os.listdir(libraries_dir):
            self.log_to_console("依赖库目录为空，正在从 Mojang 服务器获取...")
            
            # 尝试从 Mojang 版本清单获取版本信息
            version_data_online = self.download_version_from_manifest(self.selected_mc_version)
            
            if version_data_online:
                libraries_info = version_data_online.get('libraries', [])
                if libraries_info:
                    self.log_to_console(f"找到 {len(libraries_info)} 个依赖库，开始下载...")
                    self.download_libraries(libraries_info, libraries_dir)
                else:
                    self.log_to_console("警告：版本清单中未找到依赖库信息")
            else:
                self.log_to_console("无法从在线清单获取版本信息")
            
            # 再次检查 libraries 目录
            if not os.listdir(libraries_dir):
                messagebox.showerror("缺少依赖库", 
                    "未找到 Minecraft 必需的依赖库 (libraries)。\n\n"
                    "解决方法：\n"
                    "1. 确保网络连接正常\n"
                    "2. 检查是否能访问 Mojang 服务器\n"
                    "3. 使用官方启动器运行一次该版本\n"
                    "4. 手动将依赖库放入 .minecraft/libraries 目录")
                return
        
        # 4. 读取版本配置
        try:
            with open(version_json, 'r') as f:
                version_data = json.load(f)
            
            # 获取正确的 assetIndex
            asset_index = version_data.get('assetIndex', {}).get('id', 'legacy')
            # 获取主类
            main_class = version_data.get('mainClass', 'net.minecraft.client.main.Main')
            # 获取 JVM 参数
            jvm_arguments = version_data.get('arguments', {}).get('jvm', [])
            # 获取 natives 信息 (LWJGL 2.x 使用这种方式)
            natives_info = version_data.get('natives', {})
            # 获取 libraries 信息
            libraries_info = version_data.get('libraries', [])
        except Exception as e:
            self.log_to_console(f"读取版本配置失败：{str(e)}")
            messagebox.showerror("配置错误", "无法解析版本配置文件。")
            return

        # 5. 准备用户信息
        offline_username = self.player_nickname
        offline_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, offline_username))

        # 6. 构建 classpath (包含所有依赖)
        classpath = [version_jar]
        
        # 从 libraries 目录添加所有 JAR 文件
        jar_count = 0
        for root, _, files in os.walk(libraries_dir):
            for file in files:
                if file.endswith(".jar"):
                    classpath.append(os.path.join(root, file))
                    jar_count += 1
        
        self.log_to_console(f"已加载 {jar_count} 个库文件")
        
        # 转换为平台特定的 classpath 分隔符
        classpath_str = os.pathsep.join(classpath)

        # 7. 确保 natives 目录存在并提取 natives 文件
        if not os.path.exists(natives_dir):
            os.makedirs(natives_dir, exist_ok=True)
            self.log_to_console(f"已创建 natives 目录：{natives_dir}")
        
        # 检查 natives 目录是否为空，如果为空则尝试从 libraries 中提取
        if not os.listdir(natives_dir):
            self.log_to_console("正在提取 natives 文件...")
            try:
                import zipfile
                
                # Minecraft 1.12.x 使用 LWJGL 2.x，natives 在单独的 JAR 中
                # 查找 Windows natives JAR
                natives_jars = []
                for root, _, files in os.walk(libraries_dir):
                    for file in files:
                        if file.endswith(".jar") and "natives" in file.lower():
                            natives_jars.append(os.path.join(root, file))
                
                # 对于 LWJGL 2.x，natives 文件名通常包含 "windows" 或 "natives"
                for natives_jar in natives_jars:
                    if "windows" in natives_jar.lower() or "natives" in natives_jar.lower():
                        self.log_to_console(f"从 {os.path.basename(natives_jar)} 提取 natives...")
                        with zipfile.ZipFile(natives_jar, 'r') as zip_ref:
                            for member in zip_ref.namelist():
                                # 只提取 .dll 和 .exe 文件
                                if member.endswith('.dll') or member.endswith('.exe'):
                                    # 跳过 META-INF 等目录
                                    if not member.startswith('META-INF/'):
                                        filename = os.path.basename(member)
                                        if filename:
                                            target_path = os.path.join(natives_dir, filename)
                                            with open(target_path, 'wb') as f:
                                                f.write(zip_ref.read(member))
                
                extracted_files = os.listdir(natives_dir)
                if extracted_files:
                    self.log_to_console(f"已提取 {len(extracted_files)} 个 natives 文件")
                else:
                    self.log_to_console("警告：未能提取到 natives 文件")
                    
            except Exception as e:
                self.log_to_console(f"提取 natives 失败：{str(e)}")
                self.log_to_console("提示：请确保 libraries 目录中包含 natives JAR 文件")

        # 8. 组装启动命令
        self.Xmx = "1G"
        self.Xms = "512M"

        launch_cmd = [
            java_exe,
            f"-Xmx{self.Xmx}", 
            f"-Xms{self.Xms}",
            f"-Djava.library.path={natives_dir}",
            f"-Djna.tmpdir={natives_dir}",
            f"-Dorg.lwjgl.system.SharedLibraryExtractPath={natives_dir}",
            f"-Dio.netty.native.workdir={natives_dir}",
            "-Dminecraft.launcher.brand=HKPA1",
            "-Dminecraft.launcher.version=1.0",
            "-cp", classpath_str,
            main_class,
            "--username", offline_username,
            "--version", self.selected_mc_version,
            "--gameDir", version_dir,
            "--assetsDir", assets_dir,
            "--assetIndex", str(asset_index),
            "--uuid", offline_uuid,
            "--accessToken", "0",
            "--userType", "legacy",
            "--versionType", "release",
            "--width", "854",
            "--height", "480"
        ]
        # 9. 添加从版本配置中获取的 JVM 参数
        for arg in jvm_arguments:
            if isinstance(arg, str):
                # 跳过已经包含的参数
                if not any(arg.split('=')[0] in cmd_arg for cmd_arg in launch_cmd if '=' in cmd_arg):
                    launch_cmd.append(arg)
            elif isinstance(arg, dict) and 'rules' in arg:
                # TODO: 处理规则参数
                pass

        # 10. 记录启动命令和目录信息
        command_str = " ".join(launch_cmd)
        self.log_to_console(f"Java 路径：{java_exe}")
        self.log_to_console(f"游戏目录：{minecraft_dir}")
        self.log_to_console(f"版本目录：{version_dir}")
        self.log_to_console(f"启动命令：{command_str}")

        # 11. 启动游戏进程并监控输出
        try:
            self.log_to_console("正在启动游戏...")
            
            process = subprocess.Popen(
                launch_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == 'win32' else 0,
                cwd=minecraft_dir  # 关键：设置进程的工作目录为 .minecraft 根目录
            )
            
            self.log_to_console(f"游戏进程已启动 (PID: {process.pid})")
            
            # 在后台线程中监控进程输出
            def monitor_process():
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    self.log_to_console(line.strip())
                
                return_code = process.wait()
                self.log_to_console(f"游戏进程已退出，返回码：{return_code}")
                
                if return_code != 0:
                    self.log_to_console("游戏启动失败，请检查错误日志")
                    messagebox.showerror("启动失败", "游戏启动失败，请查看控制台日志获取详细信息")
                else:
                    self.log_to_console("游戏已正常退出")
            
            # 启动监控线程
            threading.Thread(target=monitor_process, daemon=True).start()
            
            # 检查进程是否立即退出
            def check_process_status():
                if process.poll() is not None:
                    return_code = process.poll()
                    self.log_to_console(f"游戏进程意外退出，返回码：{return_code}")
                    messagebox.showerror("启动失败", f"游戏进程意外退出，返回码：{return_code}")
                else:
                    self.log_to_console(f"游戏运行中 (PID: {process.pid})")
                    messagebox.showinfo("启动成功", f"游戏版本 {self.selected_mc_version} 已启动。\n用户名：{offline_username}")
            
            # 2 秒后检查进程状态
            self.root.after(2000, check_process_status)
            
        except FileNotFoundError as e:
            self.log_to_console(f"错误：未找到 Java 运行时。{str(e)}")
            messagebox.showerror("启动失败", "无法找到 Java 运行时。请检查 Java 安装或手动指定路径。")
        except Exception as e:
            self.log_to_console(f"启动过程中发生未知错误：{str(e)}")
            messagebox.showerror("启动失败", str(e))

    def toggle_settings_page(self):
        """切换设置页面显示"""
        if self.current_page == self.main_page:
            # 显示设置页面
            self.main_page.pack_forget()
            self.settings_page.pack(fill=tk.BOTH, expand=True)
            self.current_page = self.settings_page
            # 初始化设置页面内容
            if not self.settings_page.winfo_children():
                self.init_settings_page()
        else:
            # 显示主页面
            self.settings_page.pack_forget()
            self.main_page.pack(fill=tk.BOTH, expand=True)
            self.current_page = self.main_page
    
    def init_settings_page(self):
        """初始化设置页面内容"""
        # 创建左右分栏布局
        main_container = ttk.Frame(self.settings_page)
        main_container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # 左侧导航栏
        nav_frame = ttk.Frame(main_container, width=180)
        nav_frame.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 5))
        nav_frame.pack_propagate(False)
        
        # 右侧内容区域
        content_frame = ttk.Frame(main_container)
        content_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 创建导航按钮
        nav_buttons = []
        
        java_btn = tk.Button(nav_frame, text="🟢 Java 配置", 
                            font=('Microsoft YaHei', 10),
                            bd=0, bg='#e3f2fd', cursor='hand2',
                            command=lambda: self.show_java_config(content_frame, nav_buttons, 0))
        java_btn.pack(fill=tk.X, pady=2, padx=5)
        nav_buttons.append(java_btn)
        
        game_btn = tk.Button(nav_frame, text="⚙️ 游戏设置", 
                            font=('Microsoft YaHei', 10),
                            bd=0, bg='#f5f5f5', cursor='hand2',
                            command=lambda: self.show_game_page(content_frame, nav_buttons, 1, "游戏设置"))
        game_btn.pack(fill=tk.X, pady=2, padx=5)
        nav_buttons.append(game_btn)
        
        account_btn = tk.Button(nav_frame, text="👤 账户设置", 
                               font=('Microsoft YaHei', 10),
                               bd=0, bg='#f5f5f5', cursor='hand2',
                               command=lambda: self.show_placeholder_page(content_frame, nav_buttons, 2, "账户设置"))
        account_btn.pack(fill=tk.X, pady=2, padx=5)
        nav_buttons.append(account_btn)
        
        ui_btn = tk.Button(nav_frame, text="🎨 界面设置", 
                          font=('Microsoft YaHei', 10),
                          bd=0, bg='#f5f5f5', cursor='hand2',
                          command=lambda: self.show_placeholder_page(content_frame, nav_buttons, 3, "界面设置"))
        ui_btn.pack(fill=tk.X, pady=2, padx=5)
        nav_buttons.append(ui_btn)
        
        about_btn = tk.Button(nav_frame, text="ℹ️ 关于", 
                             font=('Microsoft YaHei', 10),
                             bd=0, bg='#f5f5f5', cursor='hand2',
                             command=lambda: self.show_about_page(content_frame, nav_buttons, 4))
        about_btn.pack(fill=tk.X, pady=2, padx=5)
        nav_buttons.append(about_btn)
        
        # 存储导航按钮列表和内容框架引用
        self.settings_nav_buttons = nav_buttons
        self.settings_content_frame = content_frame
        
        # 默认显示 Java 配置页面
        self.show_java_config(content_frame, nav_buttons, 0)
    
    def open_settings(self):
        """打开设置窗口（已废弃，使用 toggle_settings_page 替代）"""
        self.toggle_settings_page()
    
    def toggle_download_page(self):
        """切换下载页面显示"""
        if self.current_page == self.main_page or self.current_page == self.settings_page:
            # 显示下载页面
            if self.current_page == self.main_page:
                self.main_page.pack_forget()
            else:
                self.settings_page.pack_forget()
            self.download_page.pack(fill=tk.BOTH, expand=True)
            self.current_page = self.download_page
            # 初始化下载页面内容
            if not self.download_page.winfo_children():
                self.init_download_page()
        else:
            # 返回主页面
            self.download_page.pack_forget()
            self.main_page.pack(fill=tk.BOTH, expand=True)
            self.current_page = self.main_page
    
    def init_download_page(self):
        """初始化下载页面内容"""
        main_frame = ttk.Frame(self.download_page, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="⬇️ 下载 Minecraft 客户端", 
                               font=('Microsoft YaHei', 16, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 20))
        
        # 版本输入区域
        input_card = ttk.LabelFrame(main_frame, text="选择版本", padding="15")
        input_card.pack(fill=tk.X, pady=(0, 15))
        
        input_frame = ttk.Frame(input_card)
        input_frame.pack(fill=tk.X)
        
        ttk.Label(input_frame, text="Minecraft 版本:", 
                 font=('Microsoft YaHei', 10)).grid(row=0, column=0, sticky=tk.W, pady=5, padx=(0, 10))
        
        self.download_version_entry = ttk.Entry(input_frame, width=40, font=('Consolas', 9))
        self.download_version_entry.grid(row=0, column=1, sticky=tk.W, pady=5)
        self.download_version_entry.insert(0, "1.12.1")  # 默认版本
        
        # 进度显示
        progress_card = ttk.LabelFrame(main_frame, text="下载进度", padding="15")
        progress_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(progress_card, variable=self.progress_var, 
                                           maximum=100, mode='determinate')
        self.progress_bar.pack(fill=tk.X, pady=10)
        
        self.status_label = ttk.Label(progress_card, text="等待开始...", 
                                     font=('Microsoft YaHei', 10))
        self.status_label.pack(anchor=tk.W)
        
        # 按钮区域
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(15, 0))
        
        left_btn_frame = ttk.Frame(btn_frame)
        left_btn_frame.pack(side=tk.LEFT)
        
        back_btn = ttk.Button(left_btn_frame, text="← 返回主页", 
                             command=self.toggle_download_page)
        back_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        right_btn_frame = ttk.Frame(btn_frame)
        right_btn_frame.pack(side=tk.RIGHT)
        
        cancel_btn = ttk.Button(right_btn_frame, text="取消", 
                               command=lambda: self.status_label.config(text="已取消下载"),
                               width=15)
        cancel_btn.pack(side=tk.RIGHT, padx=(0, 10))
        
        download_btn = ttk.Button(right_btn_frame, text="开始下载", 
                                 command=self.start_download,
                                 style="Accent.TButton", width=15)
        download_btn.pack(side=tk.RIGHT, padx=(0, 10))
        
        # 保存下载按钮引用以便禁用
        self.download_page_download_btn = download_btn
    
    def start_download(self):
        """开始下载"""
        version = self.download_version_entry.get().strip()
        if not version:
            messagebox.showwarning("警告", "请输入 Minecraft 版本号")
            return
        
        # 禁用按钮防止重复点击
        if hasattr(self, 'download_page_download_btn'):
            self.download_page_download_btn.config(state='disabled')
        
        # 在新线程中下载
        threading.Thread(target=lambda: self.do_download_client(version), daemon=True).start()
    
    def do_download_client(self, version):
        """执行 Minecraft 客户端下载"""
        try:
            # 构建 URL - 使用 bmclapi2 API
            base_api_url = f"https://bmclapi2.bangbang93.com/version/{version}/client"
            
            self.log_to_console("=" * 50)
            self.log_to_console(f"开始下载 Minecraft {version} 客户端...")
            self.log_to_console(f"API 地址：{base_api_url}")
            
            # 设置保存路径
            minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
            versions_dir = os.path.join(minecraft_dir, "versions")
            version_dir = os.path.join(versions_dir, version)
            
            # 确保目录存在
            os.makedirs(version_dir, exist_ok=True)
            
            jar_path = os.path.join(version_dir, f"{version}.jar")
            
            # 更新状态
            self.status_label.config(text=f"正在连接服务器...")
            self.root.update_idletasks()
            
            # 创建请求并获取文件大小
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            req = urllib.request.Request(base_api_url, headers=headers)
            
            with urllib.request.urlopen(req, timeout=10) as response:
                total_size = int(response.headers.get('content-length', 0))
                
                self.status_label.config(text=f"文件大小：{total_size / 1024 / 1024:.2f} MB")
                self.root.update_idletasks()
                
                # 开始下载
                downloaded = 0
                block_size = 8192
                
                with open(jar_path, 'wb') as f:
                    while True:
                        buffer = response.read(block_size)
                        if not buffer:
                            break
                        
                        f.write(buffer)
                        downloaded += len(buffer)
                        
                        # 更新进度条
                        if total_size > 0:
                            progress = (downloaded / total_size) * 100
                            self.progress_var.set(progress)
                            self.status_label.config(
                                text=f"下载中... {downloaded / 1024 / 1024:.2f} MB / {total_size / 1024 / 1024:.2f} MB ({progress:.1f}%)"
                            )
                        else:
                            self.status_label.config(
                                text=f"下载中... {downloaded / 1024 / 1024:.2f} MB"
                            )
                        self.root.update_idletasks()
            
            # 下载完成
            self.status_label.config(text=f"✓ 下载完成！")
            self.progress_var.set(100)
            
            self.log_to_console(f"Minecraft {version} 客户端下载完成")
            self.log_to_console(f"保存位置：{jar_path}")
            
            # 尝试下载版本配置文件
            self.log_to_console(f"正在获取 {version} 的版本配置...")
            version_data = self.download_version_from_manifest(version)
            
            if version_data:
                json_path = os.path.join(version_dir, f"{version}.json")
                with open(json_path, 'w') as f:
                    json.dump(version_data, f, indent=2)
                self.log_to_console(f"版本配置文件已保存：{json_path}")
            else:
                self.log_to_console("警告：未能获取版本配置文件，可能需要手动配置")
            
            # 在主线程中显示完成消息
            def show_complete():
                messagebox.showinfo("下载完成", 
                    f"Minecraft {version} 客户端下载完成！\n\n"
                    f"文件位置：.minecraft/versions/{version}/\n"
                    f"客户端 JAR: {version}.jar\n"
                    f"{'配置文件：' + version + '.json' if version_data else '配置文件：未获取'}")
                
                # 刷新版本列表并返回主页
                self.scan_minecraft_versions()
                self.toggle_download_page()
            
            self.root.after(100, show_complete)
            
        except urllib.error.HTTPError as e:
            self.status_label.config(text=f"✗ 下载失败：HTTP {e.code}")
            self.log_to_console(f"下载失败：HTTP 错误 {e.code}")
            error_msg = f"无法下载 Minecraft {version}\n\n"
            if e.code == 404:
                error_msg += "该版本不存在或 API 不支持"
            elif e.code == 503:
                error_msg += "服务器暂时不可用，请稍后重试"
            else:
                error_msg += f"HTTP 错误代码：{e.code}"
            messagebox.showerror("下载失败", error_msg)
            
            # 重新启用下载按钮
            if hasattr(self, 'download_page_download_btn'):
                self.download_page_download_btn.config(state='normal')
            
        except Exception as e:
            self.status_label.config(text=f"✗ 下载失败")
            self.log_to_console(f"下载过程中发生错误：{str(e)}")
            messagebox.showerror("下载失败", f"下载过程中发生错误:\n{str(e)}")
            
            # 重新启用下载按钮
            if hasattr(self, 'download_page_download_btn'):
                self.download_page_download_btn.config(state='normal')
    
    def update_nav_button_colors(self, nav_buttons, selected_index):
        """更新导航按钮的颜色"""
        for i, btn in enumerate(nav_buttons):
            if i == selected_index:
                btn.config(bg='#e3f2fd', font=('Microsoft YaHei', 10, 'bold'))
            else:
                btn.config(bg='#f5f5f5', font=('Microsoft YaHei', 10))
    
    def show_java_config(self, parent, nav_buttons=None, selected_index=0):
        """显示 Java 配置页面"""
        if nav_buttons:
            self.update_nav_button_colors(nav_buttons, selected_index)
        
        # 清空内容区域
        for widget in parent.winfo_children():
            widget.destroy()
        
        # 创建主滚动框架
        main_frame = ttk.Frame(parent, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # 标题
        title_label = ttk.Label(main_frame, text="☕ Java 运行时配置", 
                               font=('Microsoft YaHei', 16, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 10))
        
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 15))
        
        # 兼容性提示卡片
        info_card = ttk.LabelFrame(main_frame, text="💡 版本兼容性提示", padding="12")
        info_card.pack(fill=tk.X, pady=(0, 15))
        
        compatibility_info = [
            ("Minecraft 1.20+", "需要 Java 17 或更高版本", "🟢"),
            ("Minecraft 1.17 - 1.19", "需要 Java 17", "🟢"),
            ("Minecraft 1.12 - 1.16", "推荐 Java 8", "🟡"),
            ("Minecraft 1.8 - 1.11", "需要 Java 8", "🟡"),
        ]
        
        for i, (mc_version, requirement, icon) in enumerate(compatibility_info):
            row_frame = ttk.Frame(info_card)
            row_frame.pack(fill=tk.X, pady=2)
            ttk.Label(row_frame, text=icon, font=('Segoe UI Emoji', 12), width=3).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=f"{mc_version:20}", font=('Microsoft YaHei', 9, 'bold'), 
                     width=25, anchor=tk.W).pack(side=tk.LEFT)
            ttk.Label(row_frame, text=requirement, font=('Microsoft YaHei', 9), 
                     foreground='#555').pack(side=tk.LEFT, padx=10)
        
        # Java 版本列表
        list_card = ttk.LabelFrame(main_frame, text="📦 已发现的 Java 版本", padding="10")
        list_card.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # 扫描 Java 版本
        java_versions = self.GetJavaVersions()
        
        if not java_versions:
            ttk.Label(list_card, text="⚠️ 未找到 Java 安装\n\n请确保已安装 Java 8 或更高版本。", 
                     font=('Microsoft YaHei', 10), foreground='#c62828').pack(pady=30)
        else:
            tree_frame = ttk.Frame(list_card)
            tree_frame.pack(fill=tk.BOTH, expand=True)
            
            columns = ('version', 'type', 'path', 'compatibility')
            tree = ttk.Treeview(tree_frame, columns=columns, show='headings', height=10)
            
            tree.heading('version', text='Java 版本')
            tree.heading('type', text='发行版类型')
            tree.heading('path', text='安装路径')
            tree.heading('compatibility', text='兼容性')
            
            tree.column('version', width=100, anchor='center')
            tree.column('type', width=100, anchor='center')
            tree.column('path', width=300, anchor='w')
            tree.column('compatibility', width=120, anchor='center')
            
            vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
            hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
            tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
            
            tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
            vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
            hsb.grid(row=1, column=0, sticky=(tk.W, tk.E))
            tree_frame.columnconfigure(0, weight=1)
            tree_frame.rowconfigure(0, weight=1)
            
            for display_name, java_home, java_major in java_versions:
                version_str = display_name.split('(')[0].strip().replace('Java ', '')
                
                type_icon = "☕ Oracle"
                if "Temurin" in display_name or "Eclipse" in display_name:
                    type_icon = "🔷 Temurin"
                elif "Microsoft" in display_name:
                    type_icon = "🔵 Microsoft"
                elif "Zulu" in display_name or "Azul" in display_name:
                    type_icon = "🟣 Zulu"
                elif "Corretto" in display_name or "Amazon" in display_name:
                    type_icon = "🟠 Corretto"
                elif "PATH" in display_name:
                    type_icon = "⚙️ 环境变量"
                elif "JDK" in display_name:
                    type_icon = "🛠️ JDK"
                else:
                    type_icon = "☕ JRE"
                
                if java_major >= 17:
                    compat_text = "✓ 支持新版 MC"
                    compat_color = '#2e7d32'
                elif java_major >= 8:
                    compat_text = "✓ 支持旧版 MC"
                    compat_color = '#f57c00'
                else:
                    compat_text = "⚠ 版本过旧"
                    compat_color = '#c62828'
                
                tree.insert('', 'end', values=(version_str, type_icon, java_home, compat_text),
                           tags=(compat_text,))
            
            style = ttk.Style()
            style.configure("Green.Treeview", background='#e8f5e9', foreground='#2e7d32')
            style.configure("Orange.Treeview", background='#fff3e0', foreground='#f57c00')
            style.configure("Red.Treeview", background='#ffebee', foreground='#c62828')
            
            for item in tree.get_children():
                tags = tree.item(item)['tags']
                if tags:
                    if "支持新版" in tags[0]:
                        tree.item(item, tags=('Green.Treeview',))
                    elif "支持旧版" in tags[0]:
                        tree.item(item, tags=('Orange.Treeview',))
                    else:
                        tree.item(item, tags=('Red.Treeview',))
            
            selected_item = None
            
            def on_select(event=None):
                nonlocal selected_item
                selection = tree.selection()
                if selection:
                    selected_item = tree.item(selection[0])['values']
            
            tree.bind('<<TreeviewSelect>>', on_select)
            tree.bind('<Double-Button-1>', lambda e: confirm_selection())
            
            def confirm_selection():
                if selected_item:
                    version_str = selected_item[0]
                    path = selected_item[2]
                    
                    full_display = f"Java {version_str}"
                    self.selected_java_info = (full_display, path)
                    self.log_to_console(f"已选择 Java: {full_display}")
                    self.log_to_console(f"Java 路径：{path}")
                    messagebox.showinfo("成功", f"已选择:\n{full_display}\n路径：{path}")
                else:
                    messagebox.showwarning("未选择", "请先选择一个 Java 版本")
            
            # 按钮区域
            btn_frame = ttk.Frame(main_frame)
            btn_frame.pack(fill=tk.X, pady=(10, 0))
            
            left_btn_frame = ttk.Frame(btn_frame)
            left_btn_frame.pack(side=tk.LEFT)
            
            refresh_btn = ttk.Button(left_btn_frame, text="🔄 刷新列表", 
                                    command=lambda: self.show_java_config(parent, nav_buttons, selected_index))
            refresh_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            right_btn_frame = ttk.Frame(btn_frame)
            right_btn_frame.pack(side=tk.RIGHT)
            
            confirm_btn = ttk.Button(right_btn_frame, text="确认选择", 
                                    command=confirm_selection, 
                                    style="Accent.TButton")
            confirm_btn.pack(side=tk.RIGHT)
        
        # 状态信息
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=(15, 0))
        
        if java_versions:
            ttk.Label(status_frame, text=f"共发现 {len(java_versions)} 个 Java 安装", 
                     font=('Microsoft YaHei', 9), foreground='#666').pack(side=tk.LEFT)
    
    def show_placeholder_page(self, parent, nav_buttons=None, selected_index=0, page_title=""):

        """显示占位页面"""
        if nav_buttons:
            self.update_nav_button_colors(nav_buttons, selected_index)
        
        # 清空内容区域
        for widget in parent.winfo_children():
            widget.destroy()
        
        main_frame = ttk.Frame(parent, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text=f"⚙️ {page_title}", 
                               font=('Microsoft YaHei', 16, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 20))
        
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 20))
        
        placeholder_frame = ttk.LabelFrame(main_frame, text="功能开发中", padding="30")
        placeholder_frame.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(placeholder_frame, text="🚧", font=('Segoe UI Emoji', 48)).pack(pady=20)
        ttk.Label(placeholder_frame, text=f"{page_title}功能即将推出", 
                 font=('Microsoft YaHei', 12), foreground='#666').pack(pady=10)
        ttk.Label(placeholder_frame, text="此功能正在开发中，敬请期待！", 
                 font=('Microsoft YaHei', 10), foreground='#999').pack()
    
    def show_game_page(self, parent, nav_buttons=None, selected_index=4, page_title="游戏设置"):
        """显示游戏设置页面"""
        if nav_buttons:
            self.update_nav_button_colors(nav_buttons, selected_index)

        # 清空内容区域
        for widget in parent.winfo_children():
            widget.destroy()
        
        main_frame = ttk.Frame(parent, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text=f"⚙️ {page_title}", 
                            font=('Microsoft YaHei', 16, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 20))
        
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 20))
        
        ttk.Button(main_frame, text="目录状态检查", command=self.debug_directories).pack(pady=(0, 20))


    def show_about_page(self, parent, nav_buttons=None, selected_index=4):
        """显示关于页面"""
        if nav_buttons:
            self.update_nav_button_colors(nav_buttons, selected_index)
        
        # 清空内容区域
        for widget in parent.winfo_children():
            widget.destroy()
        
        main_frame = ttk.Frame(parent, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        title_label = ttk.Label(main_frame, text="ℹ️ 关于启动器", 
                               font=('Microsoft YaHei', 16, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 20))
        
        separator = ttk.Separator(main_frame, orient='horizontal')
        separator.pack(fill=tk.X, pady=(0, 20))
        
        about_card = ttk.LabelFrame(main_frame, text="HKPA1 启动器", padding="20")
        about_card.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(about_card, text="HKPA1 Minecraft 启动器", 
                 font=('Microsoft YaHei', 14, 'bold')).pack(pady=10)
        ttk.Label(about_card, text="版本：1.0", 
                 font=('Microsoft YaHei', 10), foreground='#666').pack(pady=5)
        ttk.Label(about_card, text="一个简单、易用的 Minecraft 第三方启动器", 
                 font=('Microsoft YaHei', 10), foreground='#666').pack(pady=10)
        ttk.Label(about_card, text="开发者:Zy,部分内容由AI辅助编写", 
                 font=('Microsoft YaHei', 10), foreground='#666').pack(pady=10)
        
        sep2 = ttk.Separator(main_frame, orient='horizontal')
        sep2.pack(fill=tk.X, pady=(0, 15))
        
        info_card = ttk.LabelFrame(main_frame, text="技术栈", padding="15")
        info_card.pack(fill=tk.X)
        
        tech_info = [
            "Python 3.x",
            "Tkinter GUI",
            "Pillow 图像处理"
        ]
        
        for tech in tech_info:
            ttk.Label(info_card, text=f"• {tech}", 
                     font=('Microsoft YaHei', 9)).pack(anchor=tk.W, pady=2)

    def open_minecraft_dir(self):
        """打开.minecraft 目录"""
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        if os.path.exists(minecraft_dir):
            os.startfile(minecraft_dir)
        else:
            messagebox.showerror("错误", f"未找到.minecraft 目录:\n{minecraft_dir}")

    def show_about(self):
        """显示关于对话框"""
        messagebox.showinfo("关于", "Minecraft 启动器 - HKPA1\n版本：1.0")

    def select_skin(self):
        """选择自定义皮肤文件"""
        try:
            from tkinter import filedialog
            
            file_path = filedialog.askopenfilename(
                title="选择 Minecraft 皮肤文件",
                filetypes=[("PNG 图片文件", "*.png"), ("所有文件", "*.*")],
                initialdir=os.path.expanduser("~")
            )
            
            if not file_path:
                return
            
            if not file_path.lower().endswith('.png'):
                messagebox.showwarning("文件格式错误", "请选择 PNG 格式的皮肤文件！")
                return
            
            try:
                img = Image.open(file_path)
                width, height = img.size
                
                if width != height * 2 and width != height:
                    response = messagebox.askyesno(
                        "尺寸警告",
                        f"该图片尺寸 ({width}x{height}) 可能不是标准的 Minecraft 皮肤。\n"
                        f"标准皮肤尺寸为 64x64 或 64x32 像素。\n\n"
                        f"是否继续使用？"
                    )
                    if not response:
                        return
                
                self.player_skin_path = file_path
                
                head_img = img.crop((8, 8, 24, 24))
                head_img = head_img.resize((64, 64), Image.Resampling.LANCZOS)
                
                photo = ImageTk.PhotoImage(head_img)
                self.skin_preview_label.config(image=photo, text="")
                self.skin_preview_label.image = photo
                
                self.log_to_console(f"已加载皮肤：{os.path.basename(file_path)}")
                self.log_to_console(f"皮肤路径：{file_path}")
                
            except Exception as e:
                messagebox.showerror("文件读取失败", f"无法读取皮肤文件：\n{str(e)}")
                return
                
        except Exception as e:
            self.log_to_console(f"选择皮肤失败：{str(e)}")
            messagebox.showerror("错误", f"选择皮肤时发生错误：\n{str(e)}")

    def clear_skin(self):
        """清除已选择的皮肤"""
        self.player_skin_path = None
        self.skin_preview_label.config(
            image="",
            text="👤",
            bg='#E3F2FD'
        )
        if hasattr(self.skin_preview_label, 'image'):
            del self.skin_preview_label.image
        self.log_to_console("已清除皮肤选择")

    def show_skin_browser(self):
        """显示皮肤浏览器窗口"""
        browser_window = tk.Toplevel(self.root)
        browser_window.title("🎨 皮肤浏览器")
        browser_window.geometry("600x500")
        browser_window.transient(self.root)
        browser_window.grab_set()
        
        main_frame = ttk.Frame(browser_window, padding="15")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        browser_window.columnconfigure(0, weight=1)
        browser_window.rowconfigure(0, weight=1)
        
        title_label = ttk.Label(main_frame, text="选择 Minecraft 皮肤", 
                               font=('Microsoft YaHei', 14, 'bold'))
        title_label.pack(anchor=tk.W, pady=(0, 15))
        
        info_card = ttk.LabelFrame(main_frame, text="💡 皮肤信息", padding="10")
        info_card.pack(fill=tk.X, pady=(0, 15))
        
        ttk.Label(info_card, 
                 text="• 标准皮肤尺寸：64x64 或 64x32 像素\n"
                      "• 支持的格式：PNG\n"
                      "• 可以从皮肤网站下载或使用自己设计的皮肤",
                 font=('Microsoft YaHei', 9), foreground='#555').pack(anchor=tk.W)
        
        list_frame = ttk.LabelFrame(main_frame, text="本地皮肤文件", padding="10")
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        tree = ttk.Treeview(list_frame, columns=('name', 'size'), show='headings', height=10)
        tree.heading('name', text='文件名')
        tree.heading('size', text='尺寸')
        tree.column('name', width=400)
        tree.column('size', width=100, anchor='center')
        
        vsb = ttk.Scrollbar(list_frame, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=vsb.set)
        
        tree.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        vsb.grid(row=0, column=1, sticky=(tk.N, tk.S))
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)
        
        skins_dir = os.path.join(os.getcwd(), ".minecraft", "skins")
        if os.path.exists(skins_dir):
            for filename in os.listdir(skins_dir):
                if filename.lower().endswith('.png'):
                    file_path = os.path.join(skins_dir, filename)
                    try:
                        img = Image.open(file_path)
                        size = f"{img.size[0]}x{img.size[1]}"
                        tree.insert('', 'end', values=(filename, size))
                    except:
                        tree.insert('', 'end', values=(filename, '未知'))
        
        selected_file = None
        
        def on_select(event=None):
            nonlocal selected_file
            selection = tree.selection()
            if selection:
                values = tree.item(selection[0])['values']
                selected_file = os.path.join(skins_dir, values[0])
        
        tree.bind('<<TreeviewSelect>>', on_select)
        tree.bind('<Double-Button-1>', lambda e: confirm_selection())
        
        def confirm_selection():
            if selected_file and os.path.exists(selected_file):
                self.player_skin_path = selected_file
                self.skin_preview_label.config(
                    text="✓",
                    bg='#C8E6C9'
                )
                self.log_to_console(f"已选择皮肤：{os.path.basename(selected_file)}")
                browser_window.destroy()
            else:
                messagebox.showwarning("未选择", "请先选择一个皮肤文件", parent=browser_window)
        
        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(fill=tk.X, pady=(10, 0))
        
        left_frame = ttk.Frame(btn_frame)
        left_frame.pack(side=tk.LEFT)
        
        ttk.Button(left_frame, text="📂 打开文件夹", 
                  command=lambda: os.startfile(skins_dir) if os.path.exists(skins_dir) else None,
                  width=15).pack(side=tk.LEFT, padx=(0, 10))
        
        right_frame = ttk.Frame(btn_frame)
        right_frame.pack(side=tk.RIGHT)
        
        ttk.Button(right_frame, text="取消", command=browser_window.destroy, width=15).pack(side=tk.RIGHT, padx=(0, 10))
        ttk.Button(right_frame, text="确认", command=confirm_selection, 
                  style="Accent.TButton", width=15).pack(side=tk.RIGHT, padx=(0, 10))

    def validate_skin_file(self, skin_path):
        """验证皮肤文件是否有效"""
        if not skin_path or not os.path.exists(skin_path):
            return False
        
        try:
            img = Image.open(skin_path)
            width, height = img.size
            
            if width != height * 2 and width != height:
                self.log_to_console(f"警告：皮肤尺寸异常 ({width}x{height})")
            
            return True
        except Exception as e:
            self.log_to_console(f"皮肤文件验证失败：{str(e)}")
            return False

    def apply_custom_skin(self, version_data, minecraft_dir):
        """应用自定义皮肤到游戏配置"""
        if not self.player_skin_path or not os.path.exists(self.player_skin_path):
            return False
        
        try:
            skins_dir = os.path.join(minecraft_dir, "skins")
            os.makedirs(skins_dir, exist_ok=True)
            
            custom_skin_name = f"custom_skin_{uuid.uuid4().hex[:8]}.png"
            target_path = os.path.join(skins_dir, custom_skin_name)
            
            import shutil
            shutil.copy2(self.player_skin_path, target_path)
            
            self.log_to_console(f"皮肤已复制到：{target_path}")
            
            assets_dir = os.path.join(minecraft_dir, "assets")
            
            user_properties_path = os.path.join(minecraft_dir, "usercache.json")
            
            self.log_to_console("自定义皮肤已准备就绪")
            return True
            
        except Exception as e:
            self.log_to_console(f"应用皮肤失败：{str(e)}")
            return False

    def debug_directories(self):
        """调试目录状态"""
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        assets_dir = os.path.join(minecraft_dir, "assets")
        indexes_dir = os.path.join(assets_dir, "indexes")
        objects_dir = os.path.join(assets_dir, "objects")
           
        # 收集所有信息
        info_text = f"""Minecraft 启动器 - 目录状态检查
    ========================================

    📁 Minecraft 目录
    存在：{os.path.exists(minecraft_dir)}
    路径：{minecraft_dir}

    📁 Assets 目录
    存在：{os.path.exists(assets_dir)}
    路径：{assets_dir}

    📁 Indexes 目录
    存在：{os.path.exists(indexes_dir)}
    路径：{indexes_dir}
    文件数：{len(os.listdir(indexes_dir)) if os.path.exists(indexes_dir) else 0}

    📁 Objects 目录
    存在：{os.path.exists(objects_dir)}
    路径：{objects_dir}
    文件数：{len(os.listdir(objects_dir)) if os.path.exists(objects_dir) else 0}

    ========================================
    提示：如果目录不存在，请确保已下载 Minecraft 版本
    """
            
        messagebox.showinfo("目录状态检查", info_text)

# 程序入口
if __name__ == "__main__":
    game = Game()
    game.Run()