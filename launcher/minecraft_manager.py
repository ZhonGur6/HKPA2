"""Java detection and compatibility helpers."""

import os
import subprocess
import sys

if sys.platform == "win32":
    try:
        import winreg
    except ImportError:  # pragma: no cover - this branch is only for Python without winreg
        winreg = None
else:
    winreg = None


class JavaManager:
    """Encapsulate Java detection and version compatibility logic."""

    def __init__(self, app):
        self.app = app

    def log(self, message: str) -> None:
        if hasattr(self.app, "log_to_console"):
            self.app.log_to_console(message)

    def check_java_version(self, java_path: str):
        """Check the version of a specific Java executable."""
        try:
            result = subprocess.run(
                [java_path, "-version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
            )
            version_output = result.stderr if result.stderr else result.stdout
            for line in version_output.split("\n"):
                if "version" in line.lower():
                    parts = line.split('"')
                    if len(parts) > 1:
                        version_str = parts[1]
                        if version_str.startswith("1."):
                            major_version = int(version_str.split(".")[1])
                        else:
                            major_version = int(version_str.split(".")[0])
                        self.log(f"检测到 Java 版本：{version_str} (主版本：{major_version})")
                        return (major_version, version_str)
            return None
        except Exception as exc:  # pragma: no cover - environment-specific
            self.log(f"检查 Java 版本失败：{exc}")
            return None

    def get_required_java_version(self, mc_version: str) -> int:
        """Return the minimum Java version required by a Minecraft version."""
        try:
            version_parts = mc_version.replace(".", "-").split("-")
            if len(version_parts) >= 2:
                minor = int(version_parts[1])
                if minor >= 17:
                    return 17
                return 8
            return 8
        except Exception:  # pragma: no cover
            return 8

    def get_all_drives(self):
        """List available drives on the current platform."""
        if sys.platform == "win32":
            import string
            return [f"{letter}:\\" for letter in string.ascii_uppercase if os.path.exists(f"{letter}:\\")]
        return ["/"]

    def scan_directory_for_java(self, directory: str, java_versions: list, source="未知") -> int:
        """Recursively scan a directory for Java installations."""
        found_count = 0
        if not os.path.exists(directory):
            return 0

        try:
            for root, dirs, files in os.walk(directory):
                depth = root.replace(directory, "").count(os.sep)
                if depth > 5:
                    dirs[:] = []
                    continue

                java_exe = os.path.join(root, "bin", "java.exe")
                if os.path.exists(java_exe):
                    version_info = self.check_java_version(java_exe)
                    if version_info:
                        java_major = version_info[0]
                        java_home = os.path.dirname(os.path.dirname(java_exe))
                        dir_name = os.path.basename(root)
                        display_name = f"Java {version_info[1]} ({source}: {dir_name})"
                        if not any(value[1] == java_home for value in java_versions):
                            java_versions.append((display_name, java_home, java_major))
                            self.log(f"[{source}] 发现：{display_name}")
                            found_count += 1

                skip_dirs = [".git", "node_modules", "__pycache__", ".vscode", ".idea", "target", "build", "dist"]
                dirs[:] = [d for d in dirs if d not in skip_dirs]
        except PermissionError:
            pass
        except Exception as exc:  # pragma: no cover
            self.log(f"扫描目录失败 {directory}: {exc}")

        return found_count

    def GetJavaVersions(self):
        """Find installed Java versions on the system."""
        java_versions = []

        if sys.platform != "win32" or winreg is None:
            self.log("警告：非 Windows 系统，无法通过注册表检测 Java。")
            return java_versions

        reg_keys = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Development Kit"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\Java Runtime Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\JavaSoft\JRE"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Eclipse Adoptium\JDK"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Eclipse Adoptium\JRE"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Oracle\Java"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\JDK"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Azul Systems\Zulu"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Amazon\Corretto"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\JavaSoft\Java Development Kit"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\JavaSoft\Java Runtime Environment"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\JavaSoft\JRE"),
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
                                    for name in ["JavaHome", "INSTALLDIR", "Path"]:
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
                                            if version.startswith("1."):
                                                java_major = int(version.split(".")[1])
                                            else:
                                                java_major = int(version.split(".")[0])
                                        except Exception:
                                            java_major = 0
                                        display_name = f"Java {version} ({jtype})"
                                        if not any(item[1] == java_home for item in java_versions):
                                            java_versions.append((display_name, java_home, java_major))
                                            self.log(f"注册表发现：{display_name}")
                                except FileNotFoundError:
                                    pass
                            i += 1
                        except OSError:
                            break
            except FileNotFoundError:
                continue
            except OSError:
                continue

        self.log("正在扫描环境变量 PATH...")
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
                        if not any(item[1] == java_home for item in java_versions):
                            java_versions.append((display_name, java_home, java_major))
                            self.log(f"PATH 发现：{display_name}")

        self.log("正在扫描所有磁盘驱动器...")
        for drive in self.get_all_drives():
            for common_path in [
                r"Program Files\Java",
                r"Program Files (x86)\Java",
                r"Program Files\Eclipse Adoptium",
                r"Program Files\Microsoft\JDK",
                r"Program Files\Azul\Zulu",
                r"Program Files\Amazon Corretto",
                r"Users\Public\jdk",
            ]:
                full_path = os.path.join(drive, common_path)
                if os.path.exists(full_path):
                    self.scan_directory_for_java(full_path, java_versions, f"磁盘 {drive}")

        user_home = os.path.expanduser("~")
        jdks_path = os.path.join(user_home, ".jdks")
        if os.path.exists(jdks_path):
            self.log(f"正在扫描 .jdks 目录：{jdks_path}")
            self.scan_directory_for_java(jdks_path, java_versions, ".jdks")

        appdata = os.getenv("APPDATA", "")
        if appdata:
            minecraft_runtime = os.path.join(appdata, ".minecraft", "runtime")
            if os.path.exists(minecraft_runtime):
                self.scan_directory_for_java(minecraft_runtime, java_versions, "minecraft runtime")
            temurin_path = os.path.join(appdata, "..", "Local", "Programs", "Eclipse Adoptium")
            if os.path.exists(temurin_path):
                self.scan_directory_for_java(temurin_path, java_versions, "Temurin")

        for launcher_dir in [
            os.path.join(user_home, ".hmcl"),
            os.path.join(user_home, ".pcl"),
            os.path.join(os.getcwd(), "runtime"),
            os.path.join(os.getcwd(), "jre"),
            os.path.join(os.getcwd(), "java"),
        ]:
            if os.path.exists(launcher_dir):
                self.scan_directory_for_java(launcher_dir, java_versions, "launcher")

        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        if os.path.exists(minecraft_dir):
            for mc_java_dir in [os.path.join(minecraft_dir, "runtime"), os.path.join(minecraft_dir, "jre")]:
                if os.path.exists(mc_java_dir):
                    self.scan_directory_for_java(mc_java_dir, java_versions, "minecraft")

        self.log(f"共找到 {len(java_versions)} 个 Java 安装")
        return java_versions
