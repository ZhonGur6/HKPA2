"""Tkinter UI for the HKPA1 launcher."""

import os
import sys
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk

from .config import APP_NAME, DEFAULT_GEOMETRY, WINDOW_MIN_SIZE
from .java_manager import JavaManager
from .minecraft_manager import MinecraftManager
from .utils import resource_path


class Game:
    """Main launcher window."""

    def __init__(self):
        self.root = tk.Tk(className=APP_NAME)
        self.root.geometry(DEFAULT_GEOMETRY)
        self.root.minsize(*WINDOW_MIN_SIZE)
        self.root.update_idletasks()
        self.initial_x = self.root.winfo_x()
        self.initial_y = self.root.winfo_y()

        self.selected_mc_version = ""
        self.selected_java_info = ("", "")
        self.player_nickname = "Player"
        self.player_skin_path = None
        self.tree = None
        self.style = ttk.Style()
        self.style.configure("Accent.TButton", font=("Microsoft YaHei", 10, "bold"))
        self.style.configure("Header.TLabel", font=("Microsoft YaHei", 12, "bold"))
        self.style.configure("Nav.TButton", font=("Microsoft YaHei", 10), padding=10)

        self.java_manager = JavaManager(self)
        self.minecraft_manager = MinecraftManager(self)
        self.init_minecraft_directory()
        self.create_widgets()

    def Run(self):
        self.root.mainloop()

    def log_to_console(self, message: str):
        """Append a message to the main console if available."""
        if hasattr(self, "console_text") and self.console_text:
            try:
                self.console_text.configure(state="normal")
                self.console_text.insert(tk.END, str(message) + "\n")
                self.console_text.see(tk.END)
                self.console_text.configure(state="disabled")
            except Exception:
                pass

    def init_minecraft_directory(self):
        """Create the .minecraft directory tree used by the launcher."""
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        for directory in [
            minecraft_dir,
            os.path.join(minecraft_dir, "versions"),
            os.path.join(minecraft_dir, "libraries"),
            os.path.join(minecraft_dir, "assets"),
            os.path.join(minecraft_dir, "assets", "indexes"),
            os.path.join(minecraft_dir, "assets", "objects"),
        ]:
            os.makedirs(directory, exist_ok=True)
        self.log_to_console("Minecraft 目录已就绪")

    def create_widgets(self):
        """Create a compact launcher layout."""
        self.root.overrideredirect(True)

        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        header_frame = tk.Frame(main_container, height=50, bg="#1976D2")
        header_frame.pack(fill=tk.X)
        header_frame.pack_propagate(False)

        try:
            logo_path = resource_path("Grass.ico")
            logo_image = Image.open(logo_path).resize((32, 32), Image.Resampling.LANCZOS)
            self.logo_photo = ImageTk.PhotoImage(logo_image)
            logo_label = tk.Label(header_frame, image=self.logo_photo, bg="#1976D2")
        except Exception:
            self.logo_photo = None
            logo_label = tk.Label(header_frame, text="🎮", bg="#1976D2", font=("Segoe UI Emoji", 24))
        logo_label.pack(side=tk.LEFT, padx=15, pady=9)

        title_label = tk.Label(header_frame, text="HKPA1", bg="#1976D2", fg="white", font=("Microsoft YaHei", 14, "bold"))
        title_label.pack(side=tk.LEFT, padx=(0, 20), pady=10)

        nav_frame = tk.Frame(header_frame, bg="#1976D2")
        nav_frame.pack(side=tk.LEFT, padx=20)

        tk.Button(nav_frame, text="⬇ 下载", bg="#1976D2", fg="white", bd=0, cursor="hand2", command=self.toggle_download_page).pack(side=tk.LEFT, padx=5)
        tk.Button(nav_frame, text="⚙ 设置", bg="#1976D2", fg="white", bd=0, cursor="hand2", command=self.toggle_settings_page).pack(side=tk.LEFT, padx=5)
        tk.Button(nav_frame, text="⋮ 更多", bg="#1976D2", fg="white", bd=0, cursor="hand2", command=self.show_more_menu).pack(side=tk.LEFT, padx=5)

        window_btn_frame = tk.Frame(header_frame, bg="#1976D2")
        window_btn_frame.pack(side=tk.RIGHT, padx=15, pady=5)

        def toggle_maximize():
            if getattr(self, "maximized", False):
                self.root.geometry(self._old_geometry)
                self.maximized = False
                maximize_btn.config(text="◻")
            else:
                self._old_geometry = self.root.geometry()
                screen_width = self.root.winfo_screenwidth()
                screen_height = self.root.winfo_screenheight()
                self.root.geometry(f"{screen_width}x{screen_height}+0+0")
                self.maximized = True
                maximize_btn.config(text="❐")

        self.maximized = False
        minimize_btn = tk.Button(window_btn_frame, text="─", bg="#1976D2", fg="white", font=("Arial", 12), bd=0, cursor="hand2", command=self.minimize_window)
        minimize_btn.pack(side=tk.LEFT, padx=5)
        maximize_btn = tk.Button(window_btn_frame, text="◻", bg="#1976D2", fg="white", font=("Arial", 12), bd=0, cursor="hand2", command=toggle_maximize)
        maximize_btn.pack(side=tk.LEFT, padx=5)
        close_btn = tk.Button(window_btn_frame, text="✕", bg="#1976D2", fg="white", font=("Arial", 12), bd=0, cursor="hand2", command=self.root.quit)
        close_btn.pack(side=tk.LEFT, padx=5)

        content_frame = tk.Frame(main_container, bg="#f5f5f5")
        content_frame.pack(fill=tk.BOTH, expand=True)

        left_panel = tk.Frame(content_frame, width=320, bg="white")
        left_panel.pack(side=tk.LEFT, fill=tk.Y)
        left_panel.pack_propagate(False)

        right_container = tk.Frame(content_frame, bg="#E3F2FD")
        right_container.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.main_page = tk.Frame(right_container, bg="#E3F2FD")
        self.main_page.pack(fill=tk.BOTH, expand=True)
        self.settings_page = ttk.Frame(right_container)
        self.download_page = ttk.Frame(right_container)
        self.current_page = self.main_page

        mode_frame = tk.Frame(left_panel, bg="white")
        mode_frame.pack(fill=tk.X, padx=20, pady=15)

        self.online_btn = tk.Button(mode_frame, text="🛡 正版", bg="white", fg="#1976D2", font=("Microsoft YaHei", 10), bd=1, relief="solid", cursor="hand2", command=self.show_no_open)
        self.online_btn.pack(side=tk.LEFT, padx=(0, 10))
        self.offline_btn = tk.Button(mode_frame, text="🔗 离线", bg="#1976D2", fg="white", font=("Microsoft YaHei", 10, "bold"), bd=1, relief="solid", cursor="hand2", command=self.toggle_offline_mode)
        self.offline_btn.pack(side=tk.LEFT)

        ttk.Label(left_panel, text="游戏版本:", font=("Microsoft YaHei", 9)).pack(anchor=tk.W, pady=(10, 5), padx=20)
        self.version_combo = ttk.Combobox(left_panel, font=("Microsoft YaHei", 10), state="readonly")
        self.version_combo.pack(fill=tk.X, padx=20, pady=(0, 10), ipady=5)
        self.version_combo.bind("<<ComboboxSelected>>", self.on_version_select)

        self.big_launch_btn = tk.Button(left_panel, text="启动游戏", bg="white", fg="#1976D2", font=("Microsoft YaHei", 12, "bold"), bd=2, relief="solid", cursor="hand2", command=self.launch_game, height=2)
        self.big_launch_btn.pack(fill=tk.X, padx=20, ipady=10)

        self.version_info_label = tk.Label(left_panel, text="未选择版本", bg="white", fg="#999", font=("Microsoft YaHei", 9))
        self.version_info_label.pack(pady=(5, 0))

        self.console_text = tk.Text(self.main_page, height=12, width=50, state="disabled", bg="white", fg="#333", font=("Consolas", 9), relief="flat")
        self.console_text.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        self.root.after(100, self.scan_minecraft_versions)
        self.root.after(500, self.auto_select_java)

    def auto_select_java(self):
        """Pick the best available Java version after scanning."""
        java_versions = self.java_manager.GetJavaVersions()
        if not java_versions:
            self.selected_java_info = ("", "")
            return
        if self.selected_mc_version:
            required_java = self.java_manager.get_required_java_version(self.selected_mc_version)
            suitable = None
            fallback = None
            for display_name, java_home, java_major in java_versions:
                if java_major >= required_java:
                    if suitable is None or java_major > suitable[2]:
                        suitable = (display_name, java_home, java_major)
                elif java_major >= 8:
                    if fallback is None or java_major > fallback[2]:
                        fallback = (display_name, java_home, java_major)
            if suitable:
                self.selected_java_info = (f"Java {suitable[0]}", suitable[1])
            elif fallback:
                self.selected_java_info = (f"Java {fallback[0]}", fallback[1])
            else:
                best_java = max(java_versions, key=lambda item: item[2])
                self.selected_java_info = (f"Java {best_java[0]}", best_java[1])
        else:
            best_java = max(java_versions, key=lambda item: item[2])
            self.selected_java_info = (f"Java {best_java[0]}", best_java[1])

    def scan_minecraft_versions(self):
        self.minecraft_manager.scan_minecraft_versions()

    def show_no_open(self):
        messagebox.showinfo("提示", "功能开发中，敬请期待！")

    def toggle_offline_mode(self):
        if self.offline_btn.cget("bg") == "#1976D2":
            self.offline_btn.config(bg="white", fg="#1976D2", font=("Microsoft YaHei", 10))
            self.online_btn.config(bg="#1976D2", fg="white", font=("Microsoft YaHei", 10, "bold"))
        else:
            self.offline_btn.config(bg="#1976D2", fg="white", font=("Microsoft YaHei", 10, "bold"))
            self.online_btn.config(bg="white", fg="#1976D2", font=("Microsoft YaHei", 10))

    def show_more_menu(self):
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="📁 打开 .minecraft", command=self.open_minecraft_dir)
        menu.add_command(label="🌐 下载依赖库", command=self.download_all_libraries)
        menu.add_command(label="📦 下载游戏资源", command=self.download_all_assets)
        menu.add_separator()
        menu.add_command(label="ℹ️ 关于", command=self.show_about)
        menu.add_command(label="退出", command=self.root.quit)
        menu.post(self.root.winfo_rootx() + 600, self.root.winfo_rooty() + 40)

    def minimize_window(self):
        try:
            self.root.wm_state("iconic")
        except Exception:
            pass

    def on_version_select(self, event=None):
        selected = self.version_combo.get()
        if selected:
            self.selected_mc_version = selected
            self.version_info_label.config(text=selected)
            self.log_to_console(f"已选择版本：{selected}")

    def GetJavaVersions(self):
        return self.java_manager.GetJavaVersions()

    def check_java_version(self, java_path):
        return self.java_manager.check_java_version(java_path)

    def get_required_java_version(self, mc_version):
        return self.java_manager.get_required_java_version(mc_version)

    def download_all_libraries(self):
        if not self.selected_mc_version:
            messagebox.showwarning("未选择版本", "请先选择一个 Minecraft 版本。")
            return
        threading.Thread(target=self._do_download_libraries, daemon=True).start()

    def _do_download_libraries(self):
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        libraries_dir = os.path.join(minecraft_dir, "libraries")
        version_dir = os.path.join(minecraft_dir, "versions", self.selected_mc_version)
        version_json = os.path.join(version_dir, f"{self.selected_mc_version}.json")
        libraries_info = []
        if os.path.exists(version_json):
            try:
                with open(version_json, "r") as handle:
                    version_data = json.load(handle)
                libraries_info = version_data.get("libraries", [])
            except Exception:
                pass
        if not libraries_info:
            version_data_online = self.minecraft_manager.download_version_from_manifest(self.selected_mc_version)
            if version_data_online:
                libraries_info = version_data_online.get("libraries", [])
        self.minecraft_manager.download_libraries(libraries_info, libraries_dir)

    def download_all_assets(self):
        if not self.selected_mc_version:
            messagebox.showwarning("未选择版本", "请先选择一个 Minecraft 版本。")
            return
        threading.Thread(target=self.minecraft_manager._do_download_assets, daemon=True).start()

    def launch_game(self):
        self.minecraft_manager.launch_game()

    def open_minecraft_dir(self):
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        if os.path.exists(minecraft_dir):
            os.startfile(minecraft_dir)
        else:
            messagebox.showerror("错误", f"未找到.minecraft 目录:\n{minecraft_dir}")

    def show_about(self):
        messagebox.showinfo("关于", "Minecraft 启动器 - HKPA1\n版本：1.0")

    def toggle_settings_page(self):
        if self.current_page == self.main_page:
            self.main_page.pack_forget()
            self.settings_page.pack(fill=tk.BOTH, expand=True)
            self.current_page = self.settings_page
        else:
            self.settings_page.pack_forget()
            self.main_page.pack(fill=tk.BOTH, expand=True)
            self.current_page = self.main_page

    def toggle_download_page(self):
        if self.current_page == self.main_page:
            self.main_page.pack_forget()
            self.download_page.pack(fill=tk.BOTH, expand=True)
            self.current_page = self.download_page
        else:
            self.download_page.pack_forget()
            self.main_page.pack(fill=tk.BOTH, expand=True)
            self.current_page = self.main_page

    def init_settings_page(self):
        pass


if __name__ == "__main__":
    game = Game()
    game.Run()
