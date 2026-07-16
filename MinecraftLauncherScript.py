import json
import os
import shutil
import threading
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import zipfile

import requests

# ================= КОНФИГУРАЦИЯ ЗАПУСКА (launcher_config.json) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.dirname(sys.executable)
LAUNCHER_CONFIG_PATH = os.path.join(BASE_DIR, "launcher_config.json")

DEFAULT_LAUNCHER_CONFIG = {
    "minecraft_version": "1.21.1",
    "loader": "neoforge",
    "loader_version": "21.1.228",
    "jvm_flags": (
        "-Xms128M -Xmx8755M -XX:+UnlockExperimentalVMOptions -XX:+UseZGC "
        "-XX:ZAllocationSpikeTolerance=5 -XX:+AlwaysPreTouch -XX:+DisableExplicitGC "
        "-XX:+PerfDisableSharedMem -Dusing.aikars.flags=https://emc.gs -Daikars.new.flags=true "
        "-Duser.timezone=Europe/Moscow -Dfile.encoding=UTF-8"
    ),
    "default_public_url": "https://disk.yandex.ru/d/tenAj8XlAQEPXA",
    "default_nickname": "ManticGaga",
    "server": ""  # IP:port сервера, если нужно автоматическое подключение
}

def load_launcher_config():
    if not os.path.exists(LAUNCHER_CONFIG_PATH):
        try:
            with open(LAUNCHER_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_LAUNCHER_CONFIG, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showwarning("Ошибка", f"Не удалось создать {LAUNCHER_CONFIG_PATH}:\n{e}")
            return DEFAULT_LAUNCHER_CONFIG
        return DEFAULT_LAUNCHER_CONFIG

    try:
        with open(LAUNCHER_CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        for key, value in DEFAULT_LAUNCHER_CONFIG.items():
            if key not in config:
                config[key] = value
        return config
    except Exception as e:
        messagebox.showwarning("Ошибка", f"Не удалось загрузить {LAUNCHER_CONFIG_PATH}:\n{e}\nИспользуются значения по умолчанию.")
        return DEFAULT_LAUNCHER_CONFIG

LAUNCHER_CONFIG = load_launcher_config()

MC_VERSION = LAUNCHER_CONFIG["minecraft_version"]
LOADER = LAUNCHER_CONFIG["loader"]
LOADER_VERSION = LAUNCHER_CONFIG["loader_version"]
JVM_FLAGS = LAUNCHER_CONFIG["jvm_flags"]
DEFAULT_PUBLIC_URL = LAUNCHER_CONFIG["default_public_url"]
DEFAULT_NICKNAME = LAUNCHER_CONFIG["default_nickname"]
SERVER_ADDRESS = LAUNCHER_CONFIG.get("server", "")
# ================================================================================

DEFAULT_ROOT_DIR = BASE_DIR

# Только моды, конфиг теперь через отдельную кнопку
CATEGORIES = {
    "Моды (mods)": ("mods", "mods"),
}

API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def resolve_public_key(url_or_key):
    if not url_or_key:
        return ""
    return url_or_key.strip()

class UpdaterApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Minecraft Modpack Updater")
        self.geometry("600x700")
        self.resizable(False, False)

        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        self.config_path = os.path.join(self.base_path, "updater_config.json")

        (self.root_dir,
         self.public_url,
         self.nickname,
         self.selected_categories) = self.load_or_create_config()
        self.public_key = resolve_public_key(self.public_url)

        self.checkbox_vars = {}
        self.create_widgets()

    # ---------- Вспомогательные пути ----------
    def get_minecraft_dir(self):
        return os.path.join(self.root_dir, "Minecraft", "instances", "Sex3")

    def get_instance_parent_dir(self):
        return os.path.join(self.root_dir, "Minecraft")

    # ---------- работа с конфигурацией ----------
    def load_or_create_config(self):
        config = {}
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
            except Exception as e:
                messagebox.showwarning(
                    "Ошибка конфигурации",
                    f"Не удалось прочитать файл настроек:\n{e}\nБудут использованы значения по умолчанию.",
                )

        if "selected_categories" not in config:
            config["selected_categories"] = [local for local, _ in CATEGORIES.values()]

        if not all(k in config for k in ("root_dir", "public_url", "nickname")):
            config_dialog = self.request_config_dialog(
                config.get("root_dir", DEFAULT_ROOT_DIR),
                config.get("public_url", DEFAULT_PUBLIC_URL),
                config.get("nickname", DEFAULT_NICKNAME),
            )
            self.save_config(
                config_dialog["root_dir"],
                config_dialog["public_url"],
                config_dialog["nickname"],
                config["selected_categories"]
            )
            # Обновляем глобальные настройки из диалога
            global JVM_FLAGS, SERVER_ADDRESS
            JVM_FLAGS = config_dialog.get("jvm_flags", JVM_FLAGS)
            SERVER_ADDRESS = config_dialog.get("server", SERVER_ADDRESS)
            self._save_launcher_config(JVM_FLAGS, config_dialog["nickname"], SERVER_ADDRESS)
            return (config_dialog["root_dir"],
                    config_dialog["public_url"],
                    config_dialog["nickname"],
                    config["selected_categories"])

        return (config["root_dir"],
                config["public_url"],
                config["nickname"],
                config["selected_categories"])

    def _save_launcher_config(self, jvm_flags, nickname, server):
        """Сохраняет параметры запуска в launcher_config.json"""
        try:
            with open(LAUNCHER_CONFIG_PATH, "r", encoding="utf-8") as f:
                lc = json.load(f)
        except:
            lc = DEFAULT_LAUNCHER_CONFIG.copy()
        lc["jvm_flags"] = jvm_flags
        lc["default_nickname"] = nickname
        lc["server"] = server
        try:
            with open(LAUNCHER_CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(lc, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.log_error("Сохранение", f"Не удалось сохранить launcher_config.json: {e}")

    def save_config(self, root_dir, public_url, nickname, selected_categories=None):
        config = {
            "root_dir": root_dir,
            "public_url": public_url,
            "nickname": nickname,
            "selected_categories": selected_categories if selected_categories is not None else self.selected_categories
        }
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showwarning(
                "Ошибка сохранения",
                f"Не удалось записать файл настроек:\n{e}",
            )

    def request_config_dialog(self, current_root_dir, current_url, current_nick):
        dialog = tk.Toplevel(self)
        dialog.title("Настройки")
        dialog.geometry("650x500")
        dialog.resizable(False, False)
        dialog.grab_set()

        # Загружаем текущие значения из LAUNCHER_CONFIG
        current_jvm = LAUNCHER_CONFIG.get("jvm_flags", JVM_FLAGS)
        current_server = LAUNCHER_CONFIG.get("server", SERVER_ADDRESS)

        result = {
            "root_dir": current_root_dir,
            "public_url": current_url,
            "nickname": current_nick,
            "jvm_flags": current_jvm,
            "server": current_server,
        }

        row = 0
        # Поле выбора корневой папки
        tk.Label(dialog, text="Папка для установки Minecraft (внутри будет создана папка Minecraft):").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        dir_var = tk.StringVar(value=result["root_dir"])
        entry_dir = tk.Entry(dialog, textvariable=dir_var, width=55)
        entry_dir.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we")

        def browse_folder():
            path = filedialog.askdirectory(
                title="Выберите папку для Minecraft",
                initialdir=dir_var.get() if dir_var.get() else "",
            )
            if path:
                dir_var.set(path)

        btn_browse = tk.Button(dialog, text="Обзор...", command=browse_folder)
        btn_browse.grid(row=row, column=1, padx=(0, 10), pady=5)
        row += 1

        # Поле публичной ссылки
        tk.Label(dialog, text="Публичная ссылка Яндекс.Диска:").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        url_var = tk.StringVar(value=result["public_url"])
        entry_url = tk.Entry(dialog, textvariable=url_var, width=55)
        entry_url.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        # Поле никнейма
        tk.Label(dialog, text="Игровой никнейм:").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        nick_var = tk.StringVar(value=result["nickname"])
        entry_nick = tk.Entry(dialog, textvariable=nick_var, width=55)
        entry_nick.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        # Поле JVM-флагов
        tk.Label(dialog, text="JVM аргументы (флаги запуска):").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        jvm_var = tk.StringVar(value=result["jvm_flags"])
        entry_jvm = tk.Entry(dialog, textvariable=jvm_var, width=55)
        entry_jvm.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        # Поле сервера
        tk.Label(dialog, text="Сервер для автоматического подключения (IP:port, необязательно):").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        server_var = tk.StringVar(value=result["server"])
        entry_server = tk.Entry(dialog, textvariable=server_var, width=55)
        entry_server.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        # Кнопки
        def on_save():
            result["root_dir"] = dir_var.get().strip()
            result["public_url"] = url_var.get().strip()
            result["nickname"] = nick_var.get().strip()
            result["jvm_flags"] = jvm_var.get().strip()
            result["server"] = server_var.get().strip()
            dialog.destroy()

        def on_default():
            dir_var.set(DEFAULT_ROOT_DIR)
            url_var.set(DEFAULT_PUBLIC_URL)
            nick_var.set(DEFAULT_NICKNAME)
            jvm_var.set(DEFAULT_LAUNCHER_CONFIG["jvm_flags"])
            server_var.set("")

        frame_btns = tk.Frame(dialog)
        frame_btns.grid(row=row, column=0, columnspan=2, pady=15)
        tk.Button(frame_btns, text="По умолчанию", command=on_default, width=14).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Сохранить", command=on_save, bg="#4CAF50", fg="white", width=14).pack(side="left", padx=5)

        self.wait_window(dialog)
        return result

    # ---------- GUI ----------
    def create_widgets(self):
        lbl_title = tk.Label(
            self, text="Синхронизация сборки Minecraft", font=("Arial", 14, "bold")
        )
        lbl_title.pack(pady=10)

        frame_checks = tk.LabelFrame(
            self, text=" Выберите компоненты для установки ", padx=15, pady=10
        )
        frame_checks.pack(fill="x", padx=20, pady=5)

        for ui_name, (local_path, _) in CATEGORIES.items():
            var = tk.BooleanVar(value=local_path in self.selected_categories)
            self.checkbox_vars[local_path] = var
            var.trace('w', lambda *args, lp=local_path: self._on_checkbox_change(lp))
            chk = tk.Checkbutton(frame_checks, text=ui_name, variable=var, font=("Arial", 10))
            chk.pack(anchor="w", pady=2)

        self.progress = ttk.Progressbar(
            self, orient="horizontal", length=450, mode="determinate"
        )
        self.progress.pack(pady=10)

        # Верхняя строка кнопок
        frame_top = tk.Frame(self)
        frame_top.pack(pady=5)
        self.btn_launch = tk.Button(
            frame_top,
            text="Запустить Minecraft",
            command=self.launch_minecraft,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=5,
        )
        self.btn_launch.pack(side="left", padx=10)
        self.btn_sync = tk.Button(
            frame_top,
            text="Обновить моды",
            command=self.start_sync_thread,
            bg="#2196F3",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_sync.pack(side="left", padx=10)

        # Нижняя строка кнопок
        frame_bottom = tk.Frame(self)
        frame_bottom.pack(pady=5)
        self.btn_copy = tk.Button(
            frame_bottom,
            text="Скопировать логи",
            command=self.copy_logs_to_clipboard,
            bg="#607D8B",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_copy.pack(side="left", padx=10)
        self.btn_diag = tk.Button(
            frame_bottom,
            text="Диагностика облака",
            command=self.start_debug_thread,
            bg="#9E9E9E",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_diag.pack(side="left", padx=10)
        self.btn_config_install = tk.Button(
            frame_bottom,
            text="Установить конфиг",
            command=self.choose_config_file,
            bg="#FF5722",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_config_install.pack(side="left", padx=10)
        self.btn_settings = tk.Button(
            frame_bottom,
            text="Настройки",
            command=self.open_settings,
            bg="#FF9800",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_settings.pack(side="left", padx=10)

        self.txt_log = tk.Text(
            self, height=10, width=75, font=("Consolas", 9), bg="#1e1e1e", fg="#ffffff"
        )
        self.txt_log.pack(pady=10, padx=20)
        self.log_message("[СИСТЕМА] Инициализация завершена. Готов к работе.")
        self.log_message(f"[СИСТЕМА] Используется публичный ключ: {self.public_key}")

    def _on_checkbox_change(self, local_path):
        if self.checkbox_vars[local_path].get():
            if local_path not in self.selected_categories:
                self.selected_categories.append(local_path)
        else:
            if local_path in self.selected_categories:
                self.selected_categories.remove(local_path)
        self.save_config(self.root_dir, self.public_url, self.nickname, self.selected_categories)

    def open_settings(self):
        new_config = self.request_config_dialog(
            self.root_dir, self.public_url, self.nickname
        )
        if new_config:
            # Обновляем локальные переменные
            self.root_dir = new_config["root_dir"]
            self.public_url = new_config["public_url"]
            self.nickname = new_config["nickname"]
            self.public_key = resolve_public_key(self.public_url)
            # Обновляем глобальные JVM_FLAGS и SERVER_ADDRESS
            global JVM_FLAGS, SERVER_ADDRESS
            JVM_FLAGS = new_config["jvm_flags"]
            SERVER_ADDRESS = new_config["server"]
            # Сохраняем в launcher_config.json
            self._save_launcher_config(JVM_FLAGS, self.nickname, SERVER_ADDRESS)
            # Сохраняем настройки updater_config.json
            self.save_config(self.root_dir, self.public_url, self.nickname, self.selected_categories)
            self.log_message("[СИСТЕМА] Настройки обновлены.")
            messagebox.showinfo(
                "Настройки",
                "Настройки сохранены. Новые параметры будут использованы при следующем запуске.",
            )

    def log_message(self, message):
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)

    def log_error(self, ctx, err_text):
        self.log_message(f"❌ [{ctx.upper()}] {err_text}")

    def copy_logs_to_clipboard(self):
        logs_text = self.txt_log.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(logs_text)
        messagebox.showinfo("Буфер обмена", "Логи успешно скопированы!")

    def update_gui_progress(self, percent):
        self.progress["value"] = percent

    # ---------- Проверка и установка инстанса ----------
    def is_instance_installed(self):
        minecraft_dir = self.get_minecraft_dir()
        return os.path.isdir(minecraft_dir) and os.path.isfile(os.path.join(minecraft_dir, "instance.json"))

    def launch_minecraft(self):
        self.btn_launch.config(state=tk.DISABLED)

        if self.is_instance_installed():
            threading.Thread(target=self._launch_minecraft_thread, daemon=True).start()
        else:
            answer = messagebox.askyesno(
                "Minecraft не обнаружен",
                "Выбранная папка не содержит установленного Minecraft.\n\n"
                "Установить Minecraft сейчас?",
            )
            if answer:
                threading.Thread(target=self._install_and_launch, daemon=True).start()
            else:
                self.btn_launch.config(state=tk.NORMAL)
                self.open_settings()

    def _install_and_launch(self):
        if not self._install_instance():
            self.after(0, lambda: self.btn_launch.config(state=tk.NORMAL))
            return
        all_local = [local for local, _ in CATEGORIES.values()]
        success, _, _ = self.sync_process(all_local, silent=True)
        if not success:
            self.after(0, lambda: messagebox.showwarning("Ошибка", "Синхронизация модов завершилась с ошибками.\nПроверьте логи."))
        self._launch_game()

    def _install_instance(self):
        parent_dir = self.get_instance_parent_dir()
        os.makedirs(parent_dir, exist_ok=True)

        cmd = os.path.join(self.base_path, "cmd-launcher.exe")
        if not os.path.isfile(cmd):
            self.log_error("Установка", "cmd-launcher.exe не найден рядом с программой.")
            return False

        args = [
            cmd, "inst", "create",
            "--dir", parent_dir,
            "-v", MC_VERSION,
            "-l", LOADER,
            "--loader-version", LOADER_VERSION,
            "--verbosity", "info",
            "Sex3"
        ]
        self.log_message(f"[CMD] {' '.join(args)}")
        try:
            result = subprocess.run(args, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                output = result.stdout + result.stderr
                if "already exists" in output:
                    self.log_message("[УСТАНОВКА] Инстанс уже существует (по данным cmd-launcher). Продолжаем.")
                    return True
                error_msg = f"Ошибка cmd-launcher (код {result.returncode})\n"
                if result.stdout:
                    error_msg += f"STDOUT:\n{result.stdout}\n"
                if result.stderr:
                    error_msg += f"STDERR:\n{result.stderr}\n"
                self.log_error("Установка", error_msg)
                return False

            self.log_message("[УСТАНОВКА] Инстанс успешно создан.")
            return True
        except Exception as e:
            self.log_error("Установка", f"Исключение: {e}")
            return False

    def _launch_minecraft_thread(self):
        selected_local = [local for local, var in self.checkbox_vars.items() if var.get()]
        if not selected_local:
            self.after(0, self._launch_game)
            self.after(0, lambda: self.btn_launch.config(state=tk.NORMAL))
            return
        success, _, _ = self.sync_process(selected_local, silent=True)
        if not success:
            self.after(0, lambda: messagebox.showwarning("Ошибка", "Синхронизация модов завершилась с ошибками.\nПроверьте логи."))
        self._launch_game()
        self.after(0, lambda: self.btn_launch.config(state=tk.NORMAL))

    def _launch_game(self):
        nick = self.nickname.strip()
        if not nick:
            messagebox.showwarning("Ошибка", "Не указан игровой никнейм в настройках.")
            return

        cmd = os.path.join(self.base_path, "cmd-launcher.exe")
        if not os.path.isfile(cmd):
            self.log_error("Запуск", "cmd-launcher.exe не найден.")
            return

        parent_dir = self.get_instance_parent_dir()
        args = [
            cmd, "start", "Sex3",
            "--username", nick,
            "--dir", parent_dir,
            f"--jvm-args={JVM_FLAGS}",
        ]
        server = SERVER_ADDRESS
        if server:
            args.extend(["--server", server])

        self.log_message(f"[ЗАПУСК] {' '.join(args)}")
        try:
            subprocess.Popen(args, cwd=parent_dir, close_fds=True)
        except Exception as e:
            self.log_error("Запуск", f"Не удалось запустить игру: {e}")
            messagebox.showerror("Ошибка", "Не удалось запустить Minecraft. Проверьте логи.")

    # ---------- СИНХРОНИЗАЦИЯ МОДОВ ----------
    def start_sync_thread(self):
        selected_local = [local for local, var in self.checkbox_vars.items() if var.get()]
        if not selected_local:
            messagebox.showwarning("Внимание", "Выберите хотя бы один компонент для скачивания!")
            return

        self.btn_sync.config(state=tk.DISABLED)
        self.progress["value"] = 0
        threading.Thread(
            target=self._sync_thread_worker, args=(selected_local,), daemon=True
        ).start()

    def _sync_thread_worker(self, selected_local):
        try:
            self.sync_process(selected_local, silent=False)
        finally:
            self.after(0, lambda: self.btn_sync.config(state=tk.NORMAL))
            self.save_config(self.root_dir, self.public_url, self.nickname, self.selected_categories)

    def sync_process(self, selected_local_paths, silent=False):
        """
        Синхронизация модов: пофайловое сравнение, удаление лишних, загрузка недостающих.
        """
        minecraft_dir = self.get_minecraft_dir()
        self.after(0, self.log_message, f"[СТАРТ] Назначена папка сборки: {minecraft_dir}")

        if not os.path.exists(minecraft_dir):
            try:
                os.makedirs(minecraft_dir, exist_ok=True)
                self.after(0, self.log_message, "[ДИСК] Создана корневая папка сборки.")
            except Exception as e:
                self.after(0, self.log_error, "Диск", f"Не удалось создать папку {minecraft_dir}: {e}")
                return False, 0, 0

        has_errors = False
        deleted = 0
        downloaded = 0

        for local_path in selected_local_paths:
            if local_path == "mods":
                self.after(0, self.log_message, f"\n--- ОБРАБОТКА МОДОВ (пофайловая) ---")
                cloud_folder = "mods"
                cloud_files, success = self.get_yandex_folder_structure(self.public_key, cloud_folder)
                if not success:
                    self.after(0, self.log_error, "Синхронизация", f"Пропуск категории 'mods' из-за ошибки доступа к облаку.")
                    has_errors = True
                    continue

                cloud_data = {}
                for cloud_rel_path, (download_url, cloud_size) in cloud_files.items():
                    if cloud_rel_path.startswith(cloud_folder + "/"):
                        local_rel = local_path + cloud_rel_path[len(cloud_folder):]
                    else:
                        local_rel = local_path + "/" + cloud_rel_path.split("/", 1)[-1]
                    cloud_data[local_rel] = (download_url, cloud_size)

                local_files = self.get_local_files(minecraft_dir, local_path)

                to_delete = [rel for rel in local_files if rel not in cloud_data]
                to_download = [(rel, url) for rel, (url, size) in cloud_data.items()
                               if rel not in local_files or local_files[rel] != size]

                self.after(0, self.log_message, f"[СРАВНЕНИЕ] К удалению: {len(to_delete)}, к загрузке: {len(to_download)}")

                for rel_path in to_delete:
                    full_path = os.path.join(minecraft_dir, rel_path.replace("/", os.sep))
                    self.after(0, self.log_message, f"🗑️ Удаление: {rel_path}")
                    try:
                        if os.path.isfile(full_path):
                            os.remove(full_path)
                            deleted += 1
                            category_base = os.path.join(minecraft_dir, local_path)
                            parent = os.path.dirname(full_path)
                            while parent != category_base and os.path.exists(parent) and not os.listdir(parent):
                                os.rmdir(parent)
                                parent = os.path.dirname(parent)
                    except Exception as e:
                        self.after(0, self.log_error, "Удаление", f"Не удалось удалить {rel_path}: {e}")
                        has_errors = True

                for rel_path, url in to_download:
                    full_path = os.path.join(minecraft_dir, rel_path.replace("/", os.sep))
                    self.after(0, self.log_message, f"📥 Установка: {rel_path}")
                    if self.download_file(url, full_path):
                        downloaded += 1
                    else:
                        self.after(0, self.log_error, "Синхронизация", f"Не удалось установить: {rel_path}")
                        has_errors = True

                category_path = os.path.join(minecraft_dir, local_path)
                self._remove_empty_dirs(category_path)

            else:
                self.after(0, self.log_message, f"[ПРЕДУПРЕЖДЕНИЕ] Неизвестная категория '{local_path}' пропущена.")

        if has_errors:
            self.after(0, self.log_message, f"\n⚠️ [ЗАВЕРШЕНО С ОШИБКАМИ] Удалено: {deleted}, загружено: {downloaded}.")
            if not silent:
                self.after(0, lambda: messagebox.showwarning("Предупреждение", "Синхронизация модов завершена с ошибками."))
            return False, downloaded, deleted
        else:
            self.after(0, self.log_message, f"\n✨ [УСПЕХ] Удалено: {deleted}, загружено: {downloaded}.")
            if not silent:
                self.after(0, lambda: messagebox.showinfo("Готово", "Моды успешно синхронизированы!"))
            return True, downloaded, deleted

    def _remove_empty_dirs(self, path):
        if not os.path.isdir(path):
            return
        for root, dirs, _ in os.walk(path, topdown=False):
            for d in dirs:
                full = os.path.join(root, d)
                try:
                    if os.path.isdir(full) and not os.listdir(full):
                        os.rmdir(full)
                        self.after(0, self.log_message, f"[ОЧИСТКА] Удалена пустая папка: {full}")
                except OSError:
                    pass

    # ---------- УСТАНОВКА КОНФИГА (отдельная кнопка) ----------
    def choose_config_file(self):
        """Открывает диалог выбора файла из корня облака и устанавливает его как конфиг."""
        items, ok = self.list_public_folder(self.public_key, None)
        if not ok:
            messagebox.showerror("Ошибка", "Не удалось получить список файлов в корне облака.")
            return
        files = [it for it in items if it.get("type") == "file"]
        if not files:
            messagebox.showinfo("Нет файлов", "В корне облака нет файлов.")
            return

        dialog = tk.Toplevel(self)
        dialog.title("Выберите файл конфигурации")
        dialog.geometry("400x300")
        dialog.grab_set()

        tk.Label(dialog, text="Доступные файлы в корне облака:").pack(pady=5)
        listbox = tk.Listbox(dialog)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for f in files:
            listbox.insert(tk.END, f.get("name"))

        def on_ok():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                selected = files[index]
                dialog.destroy()
                self.install_config_file(selected)
            else:
                messagebox.showwarning("Внимание", "Выберите файл.")

        def on_cancel():
            dialog.destroy()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=5)
        tk.Button(frame_btns, text="Установить", command=on_ok, bg="#4CAF50", fg="white", width=12).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=on_cancel, width=12).pack(side="left", padx=5)

    def install_config_file(self, file_info):
        """Скачивает выбранный файл и (если это zip) распаковывает в папку config."""
        name = file_info.get("name")
        download_url = file_info.get("file")
        if not download_url:
            messagebox.showerror("Ошибка", "Не удалось получить ссылку на файл.")
            return

        minecraft_dir = self.get_minecraft_dir()
        if not os.path.exists(minecraft_dir):
            messagebox.showerror("Ошибка", "Папка инстанса не найдена. Сначала установите Minecraft.")
            return

        temp_path = os.path.join(minecraft_dir, f"temp_{name}")
        self.log_message(f"📥 Скачивание {name}...")
        if not self.download_file(download_url, temp_path):
            messagebox.showerror("Ошибка", f"Не удалось скачать {name}.")
            return

        if name.lower().endswith(".zip"):
            config_path = os.path.join(minecraft_dir, "config")
            if os.path.exists(config_path):
                try:
                    shutil.rmtree(config_path)
                    self.log_message("[ОЧИСТКА] Удалена старая папка config.")
                except Exception as e:
                    self.log_error("Очистка", f"Не удалось удалить папку config: {e}")
                    os.remove(temp_path)
                    messagebox.showerror("Ошибка", "Не удалось удалить старую папку config.")
                    return
            os.makedirs(config_path, exist_ok=True)

            try:
                with zipfile.ZipFile(temp_path, 'r') as zf:
                    zf.extractall(config_path)
                self.log_message(f"[РАСПАКОВКА] {name} распакован в {config_path}")
                messagebox.showinfo("Готово", f"Конфигурация установлена из {name}.")
            except Exception as e:
                self.log_error("Распаковка", f"Ошибка при распаковке: {e}")
                messagebox.showerror("Ошибка", f"Не удалось распаковать {name}.")
            finally:
                os.remove(temp_path)
        else:
            dest = os.path.join(minecraft_dir, name)
            try:
                shutil.move(temp_path, dest)
                self.log_message(f"[УСТАНОВЛЕНО] {name} сохранён в {dest}")
                messagebox.showinfo("Готово", f"Файл {name} сохранён в папку инстанса.")
            except Exception as e:
                self.log_error("Сохранение", f"Ошибка при сохранении: {e}")
                messagebox.showerror("Ошибка", f"Не удалось сохранить {name}.")

    # ---------- Диагностика облака ----------
    def start_debug_thread(self):
        threading.Thread(target=self.debug_cloud, daemon=True).start()

    def debug_cloud(self):
        self.after(0, self.log_message, "\n[ДИАГНОСТИКА] Чтение корня публичной папки...")
        items, ok = self.list_public_folder(self.public_key, None)
        if not ok:
            return
        if not items:
            self.after(0, self.log_message, "[ДИАГНОСТИКА] Корень публичной папки пуст.")
            return
        self.after(0, self.log_message, f"[ДИАГНОСТИКА] В корне облака найдено элементов: {len(items)}")
        for item in items:
            kind = "папка" if item.get("type") == "dir" else "файл"
            self.after(0, self.log_message, f"  - {item.get('name')} ({kind})")

    # ---------- работа с API Яндекс.Диска ----------
    def list_public_folder(self, public_key, api_path):
        all_items = []
        offset = 0
        limit = 100
        while True:
            params = {"public_key": public_key, "limit": limit, "offset": offset}
            if api_path:
                params["path"] = api_path
            self.after(0, self.log_message, f"[СЕТЬ] Запрос API: {API_BASE_URL} с параметрами {params}")
            try:
                response = requests.get(API_BASE_URL, params=params, headers=HEADERS, timeout=15)
            except requests.exceptions.RequestException as e:
                self.after(0, self.log_error, "Сеть", f"Ошибка запроса к API: {e}")
                return [], False
            if response.status_code == 404:
                self.after(0, self.log_error, "Сеть", f"Ресурс '{api_path or 'корень'}' не найден (HTTP 404).")
                return [], False
            if response.status_code != 200:
                self.after(0, self.log_error, "Сеть", f"Сервер API ответил HTTP {response.status_code}: {response.text[:200]}")
                return [], False
            try:
                data = response.json()
            except Exception as e:
                self.after(0, self.log_error, "Сеть", f"Ошибка разбора JSON: {e}")
                return [], False
            embedded = data.get("_embedded", {})
            items = embedded.get("items", [])
            all_items.extend(items)
            total = embedded.get("total")
            offset += limit
            if not items or total is None or offset >= total:
                break
        return all_items, True

    def collect_files_recursive(self, public_key, api_path, rel_prefix, files_dict):
        items, ok = self.list_public_folder(public_key, api_path)
        if not ok:
            return False
        for item in items:
            name = item.get("name")
            if not name:
                continue
            rel_path = f"{rel_prefix}/{name}"
            if item.get("type") == "dir":
                if not self.collect_files_recursive(public_key, item.get("path"), rel_path, files_dict):
                    return False
            elif item.get("type") == "file":
                download_url = item.get("file")
                size = item.get("size", 0)
                if download_url:
                    files_dict[rel_path] = (download_url, size)
        return True

    def get_yandex_folder_structure(self, public_key, folder_name):
        root_items, ok = self.list_public_folder(public_key, None)
        if not ok:
            return {}, False
        target = next((it for it in root_items if it.get("type") == "dir" and it.get("name") == folder_name), None)
        if target is None:
            self.after(0, self.log_error, "Облако", f"Папка '{folder_name}' не найдена в корне публичной ссылки.")
            return {}, False
        files_dict = {}
        ok = self.collect_files_recursive(public_key, target.get("path"), folder_name, files_dict)
        if not ok:
            return {}, False
        self.after(0, self.log_message, f"[ОБЛАКО] Прочитано файлов в папке '{folder_name}': {len(files_dict)}")
        return files_dict, True

    def get_local_files(self, base_dir, folder_name):
        local_dict = {}
        target_path = os.path.join(base_dir, folder_name)
        if not os.path.exists(target_path):
            self.after(0, self.log_message, f"[ДИСК] Локальная папка не существует: {target_path} (будет создана)")
            return local_dict
        for root, dirs, files in os.walk(target_path):
            for file in files:
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, base_dir).replace("\\", "/")
                local_dict[rel_path] = os.path.getsize(full_path)
        return local_dict

    def download_file(self, download_url, local_path):
        try:
            os.makedirs(os.path.dirname(local_path), exist_ok=True)
            response = requests.get(download_url, headers=HEADERS, stream=True, timeout=30)
            if response.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            else:
                self.after(0, self.log_error, "Скачивание", f"Ошибка HTTP {response.status_code} для файла {os.path.basename(local_path)}")
                return False
        except Exception as e:
            self.after(0, self.log_error, "Скачивание", f"Сбой при сохранении файла {os.path.basename(local_path)}: {e}")
            return False

if __name__ == "__main__":
    import sys

    if "--headless" in sys.argv:
        print("[INFO] Headless mode started")
        app = UpdaterApp()
        app.withdraw()

        def immediate_after(ms, func, *args):
            func(*args)
        app.after = immediate_after
        app.update_gui_progress = lambda p: None

        def log_headless(msg):
            print(msg)
        app.log_message = log_headless
        app.log_error = lambda ctx, msg: print(f"ERROR [{ctx}] {msg}")

        tk.messagebox.showinfo = lambda title, msg: print(f"INFO {title}: {msg}")
        tk.messagebox.showerror = lambda title, msg: print(f"ERROR {title}: {msg}")
        tk.messagebox.showwarning = lambda title, msg: print(f"WARNING {title}: {msg}")
        tk.messagebox.askyesno = lambda title, msg: False

        if not app.is_instance_installed():
            if not app._install_instance():
                print("FATAL: Cannot install Minecraft instance.")
                sys.exit(1)

        all_local = [local for local, _ in CATEGORIES.values()]
        success, _, _ = app.sync_process(all_local, silent=True)
        if not success:
            print("WARNING: Sync had errors, but launching anyway.")

        app._launch_game()
        sys.exit(0)
    else:
        app = UpdaterApp()
        app.mainloop()