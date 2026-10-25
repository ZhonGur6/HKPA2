"""Minecraft download, asset, and launch helpers."""

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from queue import Queue
import zipfile

from .utils import calculate_sha1, ensure_dir


class MinecraftManager:
    """Manage version metadata, downloads and launching."""

    def __init__(self, app):
        self.app = app

    def log(self, message: str) -> None:
        if hasattr(self.app, "log_to_console"):
            self.app.log_to_console(message)

    def fetch_version_manifest(self):
        """Fetch the Mojang version manifest."""
        manifest_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
        try:
            self.log("正在连接 Mojang 版本清单服务器...")
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            request = urllib.request.Request(manifest_url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            self.log(f"获取版本清单失败：{exc}")
            return None

    def download_version_from_manifest(self, version_id: str):
        """Download the metadata for a specific Minecraft version."""
        manifest = self.fetch_version_manifest()
        if not manifest:
            return None

        version_url = None
        for version in manifest.get("versions", []):
            if version.get("id") == version_id:
                version_url = version.get("url")
                break

        if not version_url:
            self.log(f"未在清单中找到版本：{version_id}")
            return None

        try:
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
            request = urllib.request.Request(version_url, headers=headers)
            with urllib.request.urlopen(request, timeout=10) as response:
                return json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # pragma: no cover
            self.log(f"下载版本信息失败：{exc}")
            return None

    def check_library_rules(self, rules):
        """Return whether a library should be included for the current platform."""
        allow = True
        for rule in rules:
            action = rule.get("action", "allow")
            os_rule = rule.get("os", {})
            if os_rule:
                os_name = os_rule.get("name", "")
                if os_name == "windows" and sys.platform != "win32":
                    continue
                if os_name == "osx" and sys.platform != "darwin":
                    continue
                if os_name == "linux" and sys.platform != "linux":
                    continue
            if action == "allow":
                allow = True
            elif action == "disallow":
                allow = False
        return allow

    def download_libraries(self, libraries_info, libraries_dir: str):
        """Download libraries from Mojang / BMCL mirrors."""
        if not libraries_info:
            self.log("警告：无依赖库信息")
            return

        lock = threading.Lock()
        progress_queue = Queue()

        def should_download(lib):
            if "rules" in lib and not self.check_library_rules(lib["rules"]):
                return False
            lib_name = lib.get("name", "")
            downloads = lib.get("downloads", {})
            artifact = downloads.get("artifact", {})
            if not artifact:
                parts = lib_name.split(":")
                if len(parts) >= 3:
                    group_id = parts[0].replace(".", "/")
                    artifact_id = parts[1]
                    version = parts[2]
                    classifier = parts[3] if len(parts) > 3 else None
                    if classifier:
                        lib_path = os.path.join(libraries_dir, group_id, artifact_id, version, f"{artifact_id}-{version}-{classifier}.jar")
                    else:
                        lib_path = os.path.join(libraries_dir, group_id, artifact_id, version, f"{artifact_id}-{version}.jar")
                    return not os.path.exists(lib_path)
                return False

            lib_path_rel = artifact.get("path", "")
            lib_url = artifact.get("url", "")
            if not lib_path_rel and lib_name:
                parts = lib_name.split(":")
                if len(parts) >= 3:
                    group_id = parts[0].replace(".", "/")
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
                lib_name = lib.get("name", "")
                downloads = lib.get("downloads", {})
                artifact = downloads.get("artifact", {})
                if not artifact:
                    parts = lib_name.split(":")
                    if len(parts) >= 3:
                        group_id = parts[0].replace(".", "/")
                        artifact_id = parts[1]
                        version = parts[2]
                        classifier = parts[3] if len(parts) > 3 else None
                        if classifier:
                            lib_path = os.path.join(libraries_dir, group_id, artifact_id, version, f"{artifact_id}-{version}-{classifier}.jar")
                        else:
                            lib_path = os.path.join(libraries_dir, group_id, artifact_id, version, f"{artifact_id}-{version}.jar")
                        if not os.path.exists(lib_path):
                            with lock:
                                result_dict[index] = ("missing", lib_name)
                    return

                lib_path_rel = artifact.get("path", "")
                lib_url = artifact.get("url", "")
                lib_sha1 = artifact.get("sha1", "")

                if not lib_path_rel and lib_name:
                    parts = lib_name.split(":")
                    if len(parts) >= 3:
                        group_id = parts[0].replace(".", "/")
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
                            result_dict[index] = ("failed", lib_name)
                        return
                else:
                    lib_full_path = os.path.join(libraries_dir, lib_path_rel)

                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                req = urllib.request.Request(lib_url, headers=headers)
                os.makedirs(os.path.dirname(lib_full_path), exist_ok=True)
                with urllib.request.urlopen(req, timeout=30) as response:
                    with open(lib_full_path, "wb") as out_file:
                        out_file.write(response.read())
                if lib_sha1 and os.path.exists(lib_full_path):
                    calc_sha1 = calculate_sha1(lib_full_path)
                    if calc_sha1 != lib_sha1:
                        self.log(f"警告：{lib_name} SHA1 验证失败")
                with lock:
                    result_dict[index] = ("success", lib_name)
                progress_queue.put(("downloading", lib_name))
            except Exception as exc:  # pragma: no cover
                with lock:
                    result_dict[index] = ("failed", lib_name)
                self.log(f"下载失败 {lib_name}: {exc}")
                progress_queue.put(("failed", lib_name))

        valid_libs = [lib for lib in libraries_info if should_download(lib)]
        if not valid_libs:
            self.log("依赖库检查完成：所有库已就绪")
            return

        self.log(f"开始下载 {len(valid_libs)} 个依赖库...")
        result_dict = {}
        max_workers = min(16, len(valid_libs))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(download_single_lib, lib, result_dict, i): i for i, lib in enumerate(valid_libs)}
            completed = 0
            for _ in as_completed(futures):
                while not progress_queue.empty():
                    status, lib_name = progress_queue.get()
                    if status == "downloading":
                        completed += 1
                        percentage = (completed / len(valid_libs)) * 100 if valid_libs else 0
                        self.log(f"进度：{completed}/{len(valid_libs)} ({percentage:.1f}%) - {lib_name}")

        downloaded = sum(1 for value in result_dict.values() if value[0] == "success")
        failed = sum(1 for value in result_dict.values() if value[0] == "failed")
        missing = sum(1 for value in result_dict.values() if value[0] == "missing")
        self.log(f"依赖库检查完成：{downloaded}/{len(libraries_info)} 个库已下载成功")
        if failed > 0:
            self.log(f"警告：{failed} 个库下载失败")
        if missing > 0:
            self.log(f"提示：{missing} 个库缺少下载信息但文件不存在")

    def _do_download_assets(self):
        """Download the Minecraft asset index and object files."""
        self.log("=" * 50)
        self.log(f"开始下载 {self.app.selected_mc_version} 的游戏资源...")

        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        assets_dir = os.path.join(minecraft_dir, "assets")
        indexes_dir = os.path.join(assets_dir, "indexes")
        objects_dir = os.path.join(assets_dir, "objects")
        version_dir = os.path.join(minecraft_dir, "versions", self.app.selected_mc_version)
        version_json = os.path.join(version_dir, f"{self.app.selected_mc_version}.json")
        ensure_dir(indexes_dir)
        ensure_dir(objects_dir)

        asset_index_id = "legacy"
        asset_index_url = None
        if os.path.exists(version_json):
            try:
                with open(version_json, "r") as handle:
                    version_data = json.load(handle)
                asset_index_info = version_data.get("assetIndex", {})
                asset_index_id = asset_index_info.get("id", "legacy")
                asset_index_url = asset_index_info.get("url")
                self.log(f"检测到资源索引版本：{asset_index_id}")
            except Exception as exc:  # pragma: no cover
                self.log(f"读取版本配置失败：{exc}")
        else:
            version_data_online = self.download_version_from_manifest(self.app.selected_mc_version)
            if version_data_online:
                asset_index_info = version_data_online.get("assetIndex", {})
                asset_index_id = asset_index_info.get("id", "legacy")
                asset_index_url = asset_index_info.get("url")

        index_data = None
        if asset_index_url:
            try:
                self.log(f"正在下载资源索引: {asset_index_id}")
                headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
                request = urllib.request.Request(asset_index_url, headers=headers)
                with urllib.request.urlopen(request, timeout=10) as response:
                    index_data = json.loads(response.read().decode("utf-8"))
                index_file = os.path.join(indexes_dir, f"{asset_index_id}.json")
                with open(index_file, "w") as handle:
                    json.dump(index_data, handle, indent=2)
            except Exception as exc:  # pragma: no cover
                self.log(f"下载资源索引失败：{exc}")
                return

        if not index_data:
            index_file = os.path.join(indexes_dir, f"{asset_index_id}.json")
            if os.path.exists(index_file):
                with open(index_file, "r") as handle:
                    index_data = json.load(handle)

        if not index_data:
            self.log("无法获取资源索引数据")
            return

        objects = index_data.get("objects", {})
        files_to_download = []
        for name, obj in objects.items():
            hash_value = obj.get("hash", "")
            if not hash_value:
                continue
            hash_prefix = hash_value[:2]
            object_path = os.path.join(objects_dir, hash_prefix, hash_value)
            if not os.path.exists(object_path):
                files_to_download.append((name, hash_value, hash_prefix))

        if not files_to_download:
            self.log("所有资源文件已存在，无需下载")
            return

        self.log(f"需要下载 {len(files_to_download)} 个资源文件...")
        download_sources = [
            "https://bmclapi2.bangbang93.com/assets/",
            "https://resources.download.minecraft.net/",
            "https://launcher.mojang.com/v1/packages/",
        ]

        downloaded = 0
        failed = 0
        for index, (name, hash_value, hash_prefix) in enumerate(files_to_download):
            object_dir = os.path.join(objects_dir, hash_prefix)
            object_path = os.path.join(object_dir, hash_value)
            ensure_dir(object_dir)
            try:
                success = False
                for source_index, base_url in enumerate(download_sources):
                    for retry in range(3):
                        try:
                            url = f"{base_url}{hash_value}"
                            request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                            with urllib.request.urlopen(request, timeout=30) as response:
                                payload = response.read()
                            with open(object_path, "wb") as handle:
                                handle.write(payload)
                            downloaded += 1
                            percentage = (downloaded / len(files_to_download)) * 100
                            self.log(f"进度：{index + 1}/{len(files_to_download)} ({percentage:.1f}%) - 成功 {downloaded} 个")
                            success = True
                            break
                        except (urllib.error.HTTPError, urllib.error.URLError):
                            if retry < 2:
                                time.sleep(1)
                            continue
                        except Exception:
                            if retry < 2:
                                time.sleep(1)
                            continue
                    if success:
                        break
                if not success:
                    failed += 1
                    self.log(f"所有来源均无法下载 {name}")
            except Exception as exc:  # pragma: no cover
                failed += 1
                self.log(f"处理 {name} 时发生错误：{exc}")

        self.log(f"资源下载完成：成功 {downloaded} 个，失败 {failed} 个")

    def launch_game(self):
        """Start a Minecraft instance with the selected version and Java runtime."""
        if not self.app.selected_mc_version:
            self.app.root.bell()
            return

        self.app.player_nickname = self.app.nickname_entry.get().strip() or "Player"
        minecraft_dir = os.path.join(os.getcwd(), ".minecraft")
        versions_dir = os.path.join(minecraft_dir, "versions")
        version_dir = os.path.join(versions_dir, self.app.selected_mc_version)
        assets_dir = os.path.join(minecraft_dir, "assets")
        libraries_dir = os.path.join(minecraft_dir, "libraries")
        version_json = os.path.join(version_dir, f"{self.app.selected_mc_version}.json")
        version_jar = os.path.join(version_dir, f"{self.app.selected_mc_version}.jar")
        natives_dir = os.path.join(version_dir, f"{self.app.selected_mc_version}-natives")

        if not os.path.exists(version_json):
            self.log(f"错误：未找到版本配置文件 {version_json}")
            return
        if not os.path.exists(version_jar):
            self.log(f"错误：未找到游戏核心文件 {version_jar}")
            return

        with open(version_json, "r") as handle:
            version_data = json.load(handle)

        asset_index = version_data.get("assetIndex", {}).get("id", "legacy")
        main_class = version_data.get("mainClass", "net.minecraft.client.main.Main")
        jvm_arguments = version_data.get("arguments", {}).get("jvm", [])
        libraries_info = version_data.get("libraries", [])

        if not os.path.exists(libraries_dir) or not os.listdir(libraries_dir):
            online_data = self.download_version_from_manifest(self.app.selected_mc_version)
            if online_data:
                libraries_info = online_data.get("libraries", [])
                self.download_libraries(libraries_info, libraries_dir)

        classpath = [version_jar]
        for root, _, files in os.walk(libraries_dir):
            for file_name in files:
                if file_name.endswith(".jar"):
                    classpath.append(os.path.join(root, file_name))
        classpath_str = os.pathsep.join(classpath)

        ensure_dir(natives_dir)
        if not os.listdir(natives_dir):
            natives_jars = []
            for root, _, files in os.walk(libraries_dir):
                for file_name in files:
                    if file_name.endswith(".jar") and "natives" in file_name.lower():
                        natives_jars.append(os.path.join(root, file_name))
            for natives_jar in natives_jars:
                if "windows" in natives_jar.lower() or "natives" in natives_jar.lower():
                    with zipfile.ZipFile(natives_jar, "r") as zip_ref:
                        for member in zip_ref.namelist():
                            if member.endswith((".dll", ".exe")) and not member.startswith("META-INF/"):
                                filename = os.path.basename(member)
                                if filename:
                                    target_path = os.path.join(natives_dir, filename)
                                    with open(target_path, "wb") as out_file:
                                        out_file.write(zip_ref.read(member))

        required_java_version = self.app.java_manager.get_required_java_version(self.app.selected_mc_version)
        if self.app.selected_java_info[1]:
            java_exe = os.path.join(self.app.selected_java_info[1], "bin", "java.exe" if sys.platform == "win32" else "java")
        else:
            java_exe = "java"

        java_version_info = self.app.java_manager.check_java_version(java_exe)
        if java_version_info and required_java_version and java_version_info[0] < required_java_version:
            self.log(f"警告：Minecraft {self.app.selected_mc_version} 需要 Java {required_java_version} 或更高版本")
            return

        offline_username = self.app.player_nickname
        offline_uuid = str(uuid.uuid3(uuid.NAMESPACE_DNS, offline_username))
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
            "-cp",
            classpath_str,
            main_class,
            "--username",
            offline_username,
            "--version",
            self.app.selected_mc_version,
            "--gameDir",
            version_dir,
            "--assetsDir",
            assets_dir,
            "--assetIndex",
            str(asset_index),
            "--uuid",
            offline_uuid,
            "--accessToken",
            "0",
            "--userType",
            "legacy",
            "--versionType",
            "release",
            "--width",
            "854",
            "--height",
            "480",
        ]

        for arg in jvm_arguments:
            if isinstance(arg, str):
                if not any(arg.split("=")[0] in cmd_arg for cmd_arg in launch_cmd if "=" in cmd_arg):
                    launch_cmd.append(arg)

        self.log(f"Java 路径：{java_exe}")
        self.log(f"启动命令：{' '.join(launch_cmd)}")

        try:
            process = subprocess.Popen(
                launch_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
                cwd=minecraft_dir,
            )
            self.log(f"游戏进程已启动 (PID: {process.pid})")

            def monitor_process():
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    self.log(line.strip())
                return_code = process.wait()
                self.log(f"游戏进程已退出，返回码：{return_code}")

            threading.Thread(target=monitor_process, daemon=True).start()
        except FileNotFoundError as exc:
            self.log(f"错误：未找到 Java 运行时。{exc}")
        except Exception as exc:  # pragma: no cover
            self.log(f"启动过程中发生未知错误：{exc}")

    def scan_minecraft_versions(self):
        """Scan installed Minecraft versions and populate the combo box."""
        versions_path = os.path.join(os.getcwd(), ".minecraft", "versions")
        if not os.path.exists(versions_path):
            self.app.version_combo["values"] = []
            self.log(f"错误：未找到版本目录 {versions_path}")
            return

        folders = []
        for item in os.listdir(versions_path):
            item_path = os.path.join(versions_path, item)
            if os.path.isdir(item_path):
                folders.append(item)

        if folders:
            sorted_folders = sorted(folders, reverse=True)
            self.app.version_combo["values"] = sorted_folders
            self.app.version_combo.current(0)
            self.app.on_version_select()
        else:
            self.app.version_combo["values"] = []
            self.log("未找到任何游戏版本。")
