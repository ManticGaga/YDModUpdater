import json
import os
import shutil
import threading
import subprocess
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import zipfile
import re
import tempfile

import requests

# Попытка импорта psutil для информации о памяти
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("[WARN] psutil not installed. Memory info will be unavailable.")

# ================= ЕДИНЫЙ КОНФИГ (config.json) =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.path.dirname(sys.executable)
CONFIG_PATH = os.path.join(BASE_DIR, "config.json")

DEFAULT_CONFIG = {
    "minecraft_version": "1.21.1",
    "loader": "neoforge",
    "loader_version": "21.1.228",
    "jvm_flags": (
        "-Xms128M -Xmx8755M -XX:+UseG1GC -XX:G1HeapRegionSize=16M "
        "-XX:G1ReservePercent=20 -XX:MaxGCPauseMillis=50 "
        "-XX:+UnlockExperimentalVMOptions -XX:+DisableExplicitGC "
        "-XX:+PerfDisableSharedMem -Dusing.aikars.flags=https://emc.gs "
        "-Daikars.new.flags=true -Duser.timezone=Europe/Moscow -Dfile.encoding=UTF-8"
    ),
    "public_url": "https://disk.yandex.ru/d/tenAj8XlAQEPXA",
    "nickname": "ManticGaga",
    "server": "",
    "instance_name": "Sex3"   # имя папки инстанса внутри Minecraft/instances/
}

def load_config():
    if not os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showwarning("Ошибка", f"Не удалось создать {CONFIG_PATH}:\n{e}")
            return DEFAULT_CONFIG.copy()
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        # Добавляем отсутствующие ключи
        for key, value in DEFAULT_CONFIG.items():
            if key not in config:
                config[key] = value
        return config
    except Exception as e:
        messagebox.showwarning("Ошибка", f"Не удалось загрузить {CONFIG_PATH}:\n{e}\nИспользуются значения по умолчанию.")
        return DEFAULT_CONFIG.copy()

def save_config(config):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, ensure_ascii=False, indent=2)
    except Exception as e:
        messagebox.showwarning("Ошибка сохранения", f"Не удалось записать {CONFIG_PATH}:\n{e}")

CONFIG = load_config()
MC_VERSION = CONFIG["minecraft_version"]
LOADER = CONFIG["loader"]
LOADER_VERSION = CONFIG["loader_version"]
JVM_FLAGS = CONFIG["jvm_flags"]
PUBLIC_URL = CONFIG["public_url"]
NICKNAME = CONFIG["nickname"]
SERVER = CONFIG.get("server", "")

# ================================================================================

CATEGORIES = {
    "Моды (mods)": ("mods", "mods"),
}

API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

GITHUB_OWNER = "ваш_ник"
GITHUB_REPO = "название_репозитория"

def resolve_public_key(url_or_key):
    if not url_or_key:
        return ""
    return url_or_key.strip()

class UpdaterApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Minecraft Modpack Updater")
        self.geometry("850x700")
        self.minsize(800, 600)

        if getattr(sys, 'frozen', False):
            self.base_path = os.path.dirname(sys.executable)
        else:
            self.base_path = os.path.dirname(os.path.abspath(__file__))

        self.config = load_config()
        # Корневая папка Minecraft (где лежат папки instances, libraries, versions)
        self.minecraft_root = os.path.join(self.base_path, "Minecraft")
        # Имя инстанса
        self.instance_name = self.config.get("instance_name", "Sex3")
        # Полный путь к папке инстанса
        self.instance_dir = os.path.join(self.minecraft_root, "instances", self.instance_name)
        self.public_url = self.config.get("public_url", PUBLIC_URL)
        self.nickname = self.config.get("nickname", NICKNAME)
        self.public_key = resolve_public_key(self.public_url)

        self.create_widgets()

    # ---------- Вспомогательные методы ----------
    def get_instance_dir(self):
        return self.instance_dir

    def get_instance_parent_dir(self):
        # Родительская папка инстанса = корень Minecraft
        return self.minecraft_root

    def get_instance_name(self):
        return self.instance_name

    # ---------- Сохранение конфига ----------
    def save_config(self):
        self.config["public_url"] = self.public_url
        self.config["nickname"] = self.nickname
        self.config["instance_name"] = self.instance_name
        global JVM_FLAGS, SERVER
        self.config["jvm_flags"] = JVM_FLAGS
        self.config["server"] = SERVER
        save_config(self.config)

    # ---------- GUI ----------
    def create_widgets(self):
        main_frame = tk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        left_frame = tk.Frame(main_frame, width=300)
        left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=False, padx=(0, 10))
        left_frame.pack_propagate(False)

        lbl_title = tk.Label(left_frame, text="Управление сборкой", font=("Arial", 14, "bold"))
        lbl_title.pack(pady=(0, 10))

        btn_frame = tk.Frame(left_frame)
        btn_frame.pack(fill=tk.X, pady=5)

        self.btn_launch = tk.Button(
            btn_frame,
            text="Запустить Minecraft",
            command=self.launch_minecraft,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=5,
        )
        self.btn_launch.pack(fill=tk.X, pady=2)

        self.btn_sync = tk.Button(
            btn_frame,
            text="Обновить моды",
            command=self.start_sync_thread,
            bg="#2196F3",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_sync.pack(fill=tk.X, pady=2)

        self.btn_additional = tk.Button(
            btn_frame,
            text="Установить доп. файлы",
            command=self.choose_additional_item,
            bg="#FF5722",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_additional.pack(fill=tk.X, pady=2)

        self.btn_settings = tk.Button(
            btn_frame,
            text="Настройки",
            command=self.open_settings,
            bg="#FF9800",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_settings.pack(fill=tk.X, pady=2)

        self.btn_update_launcher = tk.Button(
            btn_frame,
            text="Обновить лаунчер",
            command=self.check_for_updates,
            bg="#9C27B0",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_update_launcher.pack(fill=tk.X, pady=2)

        self.progress = ttk.Progressbar(left_frame, orient="horizontal", length=200, mode="determinate")
        self.progress.pack(fill=tk.X, pady=10)

        jvm_frame = tk.LabelFrame(left_frame, text="Настройки JVM", padx=5, pady=5)
        jvm_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.mem_label = tk.Label(jvm_frame, text="", font=("Arial", 9), anchor="w", justify=tk.LEFT)
        self.mem_label.pack(fill=tk.X, pady=2)

        xms_frame = tk.Frame(jvm_frame)
        xms_frame.pack(fill=tk.X, pady=2)
        tk.Label(xms_frame, text="Min RAM (Xms):", font=("Arial", 9), width=14, anchor="w").pack(side=tk.LEFT)
        self.xms_var = tk.StringVar()
        self.xms_entry = tk.Entry(xms_frame, textvariable=self.xms_var, width=8)
        self.xms_entry.pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(xms_frame, text="MB", font=("Arial", 9)).pack(side=tk.LEFT)

        xmx_frame = tk.Frame(jvm_frame)
        xmx_frame.pack(fill=tk.X, pady=2)
        tk.Label(xmx_frame, text="Max RAM (Xmx):", font=("Arial", 9), width=14, anchor="w").pack(side=tk.LEFT)
        self.xmx_var = tk.StringVar()
        self.xmx_entry = tk.Entry(xmx_frame, textvariable=self.xmx_var, width=8)
        self.xmx_entry.pack(side=tk.LEFT, padx=(0, 5))
        tk.Label(xmx_frame, text="MB", font=("Arial", 9)).pack(side=tk.LEFT)

        tk.Label(jvm_frame, text="Дополнительные аргументы:", font=("Arial", 9), anchor="w").pack(fill=tk.X, pady=(5, 0))
        self.jvm_text_frame = tk.Frame(jvm_frame)
        self.jvm_text_frame.pack(fill=tk.BOTH, expand=True, pady=2)

        self.jvm_text = tk.Text(self.jvm_text_frame, height=4, font=("Consolas", 9), wrap=tk.WORD)
        self.jvm_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(self.jvm_text_frame, command=self.jvm_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.jvm_text.config(yscrollcommand=scrollbar.set)

        btn_jvm_frame = tk.Frame(jvm_frame)
        btn_jvm_frame.pack(pady=5)
        self.btn_apply_jvm = tk.Button(
            btn_jvm_frame,
            text="Применить JVM",
            command=self.apply_jvm_changes,
            bg="#8BC34A",
            fg="white",
            font=("Arial", 10),
            padx=10,
            pady=3,
        )
        self.btn_apply_jvm.pack(side=tk.LEFT, padx=5)

        self.btn_reset_jvm = tk.Button(
            btn_jvm_frame,
            text="Откатить",
            command=self.reset_jvm_to_default,
            bg="#FFC107",
            fg="black",
            font=("Arial", 10),
            padx=10,
            pady=3,
        )
        self.btn_reset_jvm.pack(side=tk.LEFT, padx=5)

        self.update_jvm_ui()

        right_frame = tk.Frame(main_frame)
        right_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        self.txt_log = tk.Text(
            right_frame, height=15, font=("Consolas", 9), bg="#1e1e1e", fg="#ffffff"
        )
        self.txt_log.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        bottom_btn_frame = tk.Frame(right_frame)
        bottom_btn_frame.pack(fill=tk.X, pady=5)

        center_frame = tk.Frame(bottom_btn_frame)
        center_frame.pack(anchor=tk.CENTER)

        self.btn_copy = tk.Button(
            center_frame,
            text="Скопировать логи",
            command=self.copy_logs_to_clipboard,
            bg="#607D8B",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_copy.pack(side=tk.LEFT, padx=5)

        self.btn_diag = tk.Button(
            center_frame,
            text="Диагностика облака",
            command=self.start_debug_thread,
            bg="#9E9E9E",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_diag.pack(side=tk.LEFT, padx=5)

        self.log_message("[СИСТЕМА] Инициализация завершена. Готов к работе.")
        self.log_message(f"[СИСТЕМА] Используется публичный ключ: {self.public_key}")
        inst = self.get_instance_dir()
        self.log_message(f"[СИСТЕМА] Папка инстанса: {inst}")
        self.log_message(f"[СИСТЕМА] JVM флаги: {JVM_FLAGS}")

    def update_jvm_ui(self):
        global JVM_FLAGS
        xms_match = re.search(r'-Xms(\d+)[mM]?', JVM_FLAGS)
        xmx_match = re.search(r'-Xmx(\d+)[mM]?', JVM_FLAGS)
        if xms_match:
            self.xms_var.set(xms_match.group(1))
        else:
            self.xms_var.set("")
        if xmx_match:
            self.xmx_var.set(xmx_match.group(1))
        else:
            self.xmx_var.set("")

        rest = re.sub(r'-Xms\S+\s*', '', JVM_FLAGS)
        rest = re.sub(r'-Xmx\S+\s*', '', rest)
        rest = rest.strip()
        self.jvm_text.delete("1.0", tk.END)
        self.jvm_text.insert("1.0", rest)

        self.update_memory_info()

    def update_memory_info(self):
        if HAS_PSUTIL:
            mem = psutil.virtual_memory()
            total_gb = mem.total / (1024**3)
            free_gb = mem.available / (1024**3)
            used_percent = mem.percent
            self.mem_label.config(
                text=f"Общ.: {total_gb:.1f} ГБ  |  Своб.: {free_gb:.1f} ГБ  |  Исп.: {used_percent}%"
            )
        else:
            self.mem_label.config(text="Информация о памяти недоступна (установите psutil)")

    def apply_jvm_changes(self):
        global JVM_FLAGS
        xms = self.xms_var.get().strip()
        xmx = self.xmx_var.get().strip()
        rest = self.jvm_text.get("1.0", tk.END).strip()

        if not xms.isdigit() or not xmx.isdigit():
            messagebox.showerror("Ошибка", "Значения Xms и Xmx должны быть целыми числами (МБ).")
            return

        new_flags = f"-Xms{xms}M -Xmx{xmx}M"
        if rest:
            new_flags += " " + rest

        JVM_FLAGS = new_flags
        self.config["jvm_flags"] = JVM_FLAGS
        self.save_config()
        self.update_jvm_ui()
        self.log_message("[СИСТЕМА] JVM-флаги обновлены.")
        messagebox.showinfo("Готово", "JVM-аргументы успешно сохранены.")

    def reset_jvm_to_default(self):
        global JVM_FLAGS
        default_flags = DEFAULT_CONFIG["jvm_flags"]
        JVM_FLAGS = default_flags
        self.config["jvm_flags"] = JVM_FLAGS
        self.save_config()
        self.update_jvm_ui()
        self.log_message("[СИСТЕМА] JVM-флаги сброшены к значениям по умолчанию.")
        messagebox.showinfo("Готово", "JVM-аргументы сброшены до стандартных.")

    # ---------- ОБНОВЛЕНИЕ ЛАУНЧЕРА ----------
    def check_for_updates(self):
        if getattr(sys, 'frozen', False):
            threading.Thread(target=self._update_launcher_thread, daemon=True).start()
        else:
            messagebox.showinfo("Информация", "Обновление доступно только для собранного .exe файла.")

    def _update_launcher_thread(self):
        self.btn_update_launcher.config(state=tk.DISABLED)
        self.log_message("[ОБНОВЛЕНИЕ] Проверка обновлений...")
        try:
            url = f"https://api.github.com/repos/{GITHUB_OWNER}/{GITHUB_REPO}/releases/latest"
            response = requests.get(url, timeout=10)
            if response.status_code != 200:
                self.log_error("Обновление", f"Не удалось получить информацию о релизе (HTTP {response.status_code})")
                messagebox.showerror("Ошибка", "Не удалось проверить обновления.")
                self.btn_update_launcher.config(state=tk.NORMAL)
                return

            data = response.json()
            assets = data.get("assets", [])
            exe_asset = None
            for asset in assets:
                if asset["name"].endswith(".exe"):
                    exe_asset = asset
                    break
            if not exe_asset:
                self.log_error("Обновление", "В последнем релизе нет .exe файла.")
                messagebox.showerror("Ошибка", "В релизе нет исполняемого файла.")
                self.btn_update_launcher.config(state=tk.NORMAL)
                return

            download_url = exe_asset["browser_download_url"]
            current_exe = sys.executable
            temp_dir = tempfile.gettempdir()
            new_exe_path = os.path.join(temp_dir, "launcher_new.exe")
            self.log_message(f"[ОБНОВЛЕНИЕ] Скачивание {exe_asset['name']}...")
            if not self.download_file(download_url, new_exe_path):
                self.log_error("Обновление", "Не удалось скачать новый файл.")
                messagebox.showerror("Ошибка", "Ошибка загрузки обновления.")
                self.btn_update_launcher.config(state=tk.NORMAL)
                return

            try:
                backup_exe = current_exe + ".old"
                if os.path.exists(backup_exe):
                    os.remove(backup_exe)
                os.rename(current_exe, backup_exe)
                shutil.move(new_exe_path, current_exe)
                self.log_message("[ОБНОВЛЕНИЕ] Успешно обновлено. Перезапуск...")
                messagebox.showinfo("Обновление", "Лаунчер обновлён! Перезапуск...")
                subprocess.Popen([current_exe] + sys.argv[1:])
                sys.exit(0)
            except Exception as e:
                self.log_error("Обновление", f"Ошибка замены файла: {e}")
                messagebox.showerror("Ошибка", f"Не удалось заменить файл: {e}")
                if os.path.exists(backup_exe):
                    shutil.move(backup_exe, current_exe)
                self.btn_update_launcher.config(state=tk.NORMAL)

        except Exception as e:
            self.log_error("Обновление", f"Исключение: {e}")
            messagebox.showerror("Ошибка", f"Ошибка при обновлении: {e}")
            self.btn_update_launcher.config(state=tk.NORMAL)

    # ---------- ДИАЛОГ НАСТРОЕК (с выбором имени инстанса) ----------
    def open_settings(self):
        global JVM_FLAGS, SERVER
        dialog = tk.Toplevel(self)
        dialog.title("Настройки")
        dialog.geometry("650x450")
        dialog.resizable(False, False)
        dialog.grab_set()

        current_url = self.public_url
        current_nick = self.nickname
        current_jvm = JVM_FLAGS
        current_server = SERVER
        current_instance_name = self.instance_name

        result = {
            "public_url": current_url,
            "nickname": current_nick,
            "jvm_flags": current_jvm,
            "server": current_server,
            "instance_name": current_instance_name,
        }

        row = 0
        # Публичная ссылка
        tk.Label(dialog, text="Публичная ссылка Яндекс.Диска:").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        url_var = tk.StringVar(value=result["public_url"])
        entry_url = tk.Entry(dialog, textvariable=url_var, width=55)
        entry_url.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        # Никнейм
        tk.Label(dialog, text="Игровой никнейм:").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        nick_var = tk.StringVar(value=result["nickname"])
        entry_nick = tk.Entry(dialog, textvariable=nick_var, width=55)
        entry_nick.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        # Имя инстанса
        tk.Label(dialog, text="Имя папки инстанса (внутри Minecraft/instances/):").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        inst_name_var = tk.StringVar(value=result["instance_name"])
        entry_inst_name = tk.Entry(dialog, textvariable=inst_name_var, width=55)
        entry_inst_name.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        # JVM аргументы
        tk.Label(dialog, text="JVM аргументы (флаги запуска):").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        jvm_var = tk.StringVar(value=result["jvm_flags"])
        entry_jvm = tk.Entry(dialog, textvariable=jvm_var, width=55)
        entry_jvm.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        # Сервер
        tk.Label(dialog, text="Сервер для автоматического подключения (IP:port, необязательно):").grid(
            row=row, column=0, sticky="w", padx=10, pady=(15, 0), columnspan=2
        )
        row += 1
        server_var = tk.StringVar(value=result["server"])
        entry_server = tk.Entry(dialog, textvariable=server_var, width=55)
        entry_server.grid(row=row, column=0, padx=(10, 5), pady=5, sticky="we", columnspan=2)
        row += 1

        def on_save():
            new_name = inst_name_var.get().strip()
            if not new_name:
                messagebox.showwarning("Ошибка", "Имя инстанса не может быть пустым.")
                return
            result["public_url"] = url_var.get().strip()
            result["nickname"] = nick_var.get().strip()
            result["jvm_flags"] = jvm_var.get().strip()
            result["server"] = server_var.get().strip()
            result["instance_name"] = new_name
            dialog.destroy()

        def on_default():
            url_var.set(DEFAULT_CONFIG["public_url"])
            nick_var.set(DEFAULT_CONFIG["nickname"])
            jvm_var.set(DEFAULT_CONFIG["jvm_flags"])
            server_var.set("")
            inst_name_var.set("Sex3")

        frame_btns = tk.Frame(dialog)
        frame_btns.grid(row=row, column=0, columnspan=2, pady=15)
        tk.Button(frame_btns, text="По умолчанию", command=on_default, width=14).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Сохранить", command=on_save, bg="#4CAF50", fg="white", width=14).pack(side="left", padx=5)

        self.wait_window(dialog)

        # Применяем изменения
        self.public_url = result["public_url"]
        self.nickname = result["nickname"]
        JVM_FLAGS = result["jvm_flags"]
        SERVER = result["server"]
        self.instance_name = result["instance_name"]
        # Пересчитываем путь к инстансу
        self.instance_dir = os.path.join(self.minecraft_root, "instances", self.instance_name)
        self.public_key = resolve_public_key(self.public_url)
        self.save_config()
        self.update_jvm_ui()
        self.log_message("[СИСТЕМА] Настройки обновлены.")
        self.log_message(f"[СИСТЕМА] Новое имя инстанса: {self.instance_name}")
        self.log_message(f"[СИСТЕМА] Новый путь: {self.instance_dir}")
        messagebox.showinfo("Настройки", "Настройки сохранены. Инстанс будет использоваться при следующем запуске.")

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
        inst = self.get_instance_dir()
        return os.path.isdir(inst) and os.path.isfile(os.path.join(inst, "instance.json"))

    def launch_minecraft(self):
        self.btn_launch.config(state=tk.DISABLED)
        threading.Thread(target=self._launch_thread, daemon=True).start()

    def _launch_thread(self):
        if not self.is_instance_installed():
            self.after(0, self.log_message, "[ЗАПУСК] Инстанс не найден, устанавливаю...")
            if not self._install_instance():
                self.after(0, self.btn_launch.config, state=tk.NORMAL)
                return
            success, _, _ = self.sync_process(silent=True)
            if not success:
                self.after(0, lambda: messagebox.showwarning("Ошибка", "Синхронизация модов завершилась с ошибками.\nПроверьте логи."))
        self._launch_game()
        self.after(0, self.btn_launch.config, state=tk.NORMAL)

    def _install_instance(self):
        parent_dir = self.get_instance_parent_dir()
        instance_name = self.get_instance_name()
        if not parent_dir or not instance_name:
            self.log_error("Установка", "Неверный путь к инстансу.")
            return False

        os.makedirs(parent_dir, exist_ok=True)
        os.makedirs(os.path.join(parent_dir, "instances", instance_name), exist_ok=True)

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
            instance_name
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
        instance_name = self.get_instance_name()
        if not parent_dir or not instance_name:
            messagebox.showerror("Ошибка", "Неверный путь к инстансу.")
            return

        args = [
            cmd, "start", instance_name,
            "--username", nick,
            "--dir", parent_dir,
            f"--jvm-args={JVM_FLAGS}",
        ]
        if SERVER:
            args.extend(["--server", SERVER])

        self.log_message(f"[ЗАПУСК] {' '.join(args)}")
        try:
            subprocess.Popen(args, cwd=parent_dir, close_fds=True)
        except Exception as e:
            self.log_error("Запуск", f"Не удалось запустить игру: {e}")
            messagebox.showerror("Ошибка", "Не удалось запустить Minecraft. Проверьте логи.")

    # ---------- СИНХРОНИЗАЦИЯ МОДОВ (с удалением) ----------
    def start_sync_thread(self):
        self.btn_sync.config(state=tk.DISABLED)
        self.progress["value"] = 0
        threading.Thread(
            target=self._sync_thread_worker, daemon=True
        ).start()

    def _sync_thread_worker(self):
        try:
            self.sync_process(silent=False)
        finally:
            self.after(0, lambda: self.btn_sync.config(state=tk.NORMAL))
            self.save_config()

    def sync_process(self, silent=False):
        instance_dir = self.get_instance_dir()
        if not instance_dir:
            self.log_error("Синхронизация", "Папка инстанса не задана.")
            return False, 0, 0

        self.after(0, self.log_message, f"[СТАРТ] Папка инстанса: {instance_dir}")

        if not os.path.exists(instance_dir):
            try:
                os.makedirs(instance_dir, exist_ok=True)
                self.after(0, self.log_message, "[ДИСК] Создана папка инстанса.")
            except Exception as e:
                self.after(0, self.log_error, "Диск", f"Не удалось создать папку {instance_dir}: {e}")
                return False, 0, 0

        has_errors = False
        deleted = 0
        downloaded = 0
        local_path = "mods"

        self.after(0, self.log_message, f"\n--- ОБРАБОТКА МОДОВ (пофайловая с удалением) ---")
        cloud_folder = "mods"
        cloud_files, success = self.get_yandex_folder_structure(self.public_key, cloud_folder)
        if not success:
            self.after(0, self.log_error, "Синхронизация", f"Пропуск категории 'mods' из-за ошибки доступа к облаку.")
            has_errors = True
        else:
            cloud_data = {}
            for cloud_rel_path, (download_url, cloud_size) in cloud_files.items():
                if cloud_rel_path.startswith(cloud_folder + "/"):
                    local_rel = local_path + cloud_rel_path[len(cloud_folder):]
                else:
                    local_rel = local_path + "/" + cloud_rel_path.split("/", 1)[-1]
                cloud_data[local_rel] = (download_url, cloud_size)

            local_files = self.get_local_files(instance_dir, local_path)

            to_delete = [rel for rel in local_files if rel not in cloud_data]
            to_download = [(rel, url) for rel, (url, size) in cloud_data.items()
                           if rel not in local_files or local_files[rel] != size]

            self.after(0, self.log_message, f"[СРАВНЕНИЕ] К удалению: {len(to_delete)}, к загрузке: {len(to_download)}")

            for rel_path in to_delete:
                full_path = os.path.join(instance_dir, rel_path.replace("/", os.sep))
                self.after(0, self.log_message, f"🗑️ Удаление: {rel_path}")
                try:
                    if os.path.isfile(full_path):
                        os.remove(full_path)
                        deleted += 1
                        category_base = os.path.join(instance_dir, local_path)
                        parent = os.path.dirname(full_path)
                        while parent != category_base and os.path.exists(parent) and not os.listdir(parent):
                            os.rmdir(parent)
                            parent = os.path.dirname(parent)
                except Exception as e:
                    self.after(0, self.log_error, "Удаление", f"Не удалось удалить {rel_path}: {e}")
                    has_errors = True

            for rel_path, url in to_download:
                full_path = os.path.join(instance_dir, rel_path.replace("/", os.sep))
                self.after(0, self.log_message, f"📥 Установка: {rel_path}")
                if self.download_file(url, full_path):
                    downloaded += 1
                else:
                    self.after(0, self.log_error, "Синхронизация", f"Не удалось установить: {rel_path}")
                    has_errors = True

            category_path = os.path.join(instance_dir, local_path)
            self._remove_empty_dirs(category_path)

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

    # ---------- СИНХРОНИЗАЦИЯ ПАПКИ БЕЗ УДАЛЕНИЯ ----------
    def sync_folder_no_delete(self, cloud_folder, local_path):
        instance_dir = self.get_instance_dir()
        if not instance_dir:
            self.log_error("Синхронизация", "Папка инстанса не задана.")
            return False, 0

        self.log_message(f"[СИНХРОНИЗАЦИЯ] Папка {cloud_folder} -> {local_path} (без удаления)")
        cloud_files, success = self.get_yandex_folder_structure(self.public_key, cloud_folder)
        if not success:
            self.log_error("Синхронизация", f"Не удалось получить список файлов в папке '{cloud_folder}'.")
            return False, 0

        if not cloud_files:
            self.log_message(f"[СИНХРОНИЗАЦИЯ] В облачной папке '{cloud_folder}' нет файлов.")
            return True, 0

        downloaded = 0
        has_errors = False

        local_files = self.get_local_files(instance_dir, local_path)

        for cloud_rel_path, (download_url, cloud_size) in cloud_files.items():
            if cloud_rel_path.startswith(cloud_folder + "/"):
                local_rel = local_path + cloud_rel_path[len(cloud_folder):]
            else:
                local_rel = local_path + "/" + cloud_rel_path.split("/", 1)[-1]

            full_local_path = os.path.join(instance_dir, local_rel.replace("/", os.sep))
            need_download = False
            if local_rel not in local_files:
                need_download = True
            elif local_files[local_rel] != cloud_size:
                need_download = True
                self.log_message(f"[ОБНОВЛЕНИЕ] {local_rel} (размер изменился)")

            if need_download:
                self.log_message(f"📥 Установка: {local_rel}")
                if self.download_file(download_url, full_local_path):
                    downloaded += 1
                else:
                    self.log_error("Синхронизация", f"Не удалось установить: {local_rel}")
                    has_errors = True

        if has_errors:
            self.log_message(f"[ЗАВЕРШЕНО С ОШИБКАМИ] Загружено: {downloaded}.")
            return False, downloaded
        else:
            self.log_message(f"[УСПЕХ] Загружено: {downloaded}.")
            return True, downloaded

    # ---------- УСТАНОВКА ДОП. ФАЙЛОВ ----------
    def choose_additional_item(self):
        items, ok = self.list_public_folder(self.public_key, None)
        if not ok:
            messagebox.showerror("Ошибка", "Не удалось получить список элементов в корне облака.")
            return
        if not items:
            messagebox.showinfo("Нет элементов", "В корне облака ничего нет.")
            return

        dirs = [it for it in items if it.get("type") == "dir"]
        files = [it for it in items if it.get("type") == "file"]
        items_sorted = dirs + files

        dialog = tk.Toplevel(self)
        dialog.title("Выберите элемент для установки")
        dialog.geometry("450x400")
        dialog.grab_set()

        tk.Label(dialog, text="Выберите папку (синхронизация без удаления) или файл:").pack(pady=5)
        listbox = tk.Listbox(dialog)
        listbox.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        for item in items_sorted:
            kind = "📁" if item.get("type") == "dir" else "📄"
            listbox.insert(tk.END, f"{kind} {item.get('name')}")

        def on_ok():
            selection = listbox.curselection()
            if selection:
                index = selection[0]
                selected = items_sorted[index]
                dialog.destroy()
                if selected.get("type") == "dir":
                    folder_name = selected.get("name")
                    local_folder = folder_name
                    threading.Thread(target=self._install_folder_thread, args=(folder_name, local_folder), daemon=True).start()
                else:
                    self.install_additional_file(selected)
            else:
                messagebox.showwarning("Внимание", "Выберите элемент.")

        def on_cancel():
            dialog.destroy()

        frame_btns = tk.Frame(dialog)
        frame_btns.pack(pady=5)
        tk.Button(frame_btns, text="Установить", command=on_ok, bg="#4CAF50", fg="white", width=12).pack(side="left", padx=5)
        tk.Button(frame_btns, text="Отмена", command=on_cancel, width=12).pack(side="left", padx=5)

    def _install_folder_thread(self, cloud_folder, local_folder):
        self.btn_additional.config(state=tk.DISABLED)
        self.progress["value"] = 0
        try:
            success, count = self.sync_folder_no_delete(cloud_folder, local_folder)
            if success:
                messagebox.showinfo("Готово", f"Папка '{cloud_folder}' успешно синхронизирована (загружено {count} файлов).")
            else:
                messagebox.showwarning("Предупреждение", f"Синхронизация '{cloud_folder}' завершена с ошибками.")
        except Exception as e:
            self.log_error("Ошибка", f"Исключение: {e}")
            messagebox.showerror("Ошибка", f"Ошибка синхронизации: {e}")
        finally:
            self.btn_additional.config(state=tk.NORMAL)

    def install_additional_file(self, file_info):
        name = file_info.get("name")
        download_url = file_info.get("file")
        if not download_url:
            messagebox.showerror("Ошибка", "Не удалось получить ссылку на файл.")
            return

        instance_dir = self.get_instance_dir()
        if not instance_dir or not os.path.exists(instance_dir):
            messagebox.showerror("Ошибка", "Папка инстанса не найдена. Сначала установите Minecraft.")
            return

        temp_path = os.path.join(instance_dir, f"temp_{name}")
        self.log_message(f"📥 Скачивание {name}...")
        if not self.download_file(download_url, temp_path):
            messagebox.showerror("Ошибка", f"Не удалось скачать {name}.")
            return

        if name.lower() == "config.zip":
            target_dir = os.path.join(instance_dir, "config")
            self.log_message(f"[УСТАНОВКА] Файл {name} будет установлен как конфигурация в {target_dir}")
            if os.path.exists(target_dir):
                try:
                    shutil.rmtree(target_dir)
                    self.log_message("[ОЧИСТКА] Удалена старая папка config.")
                except Exception as e:
                    self.log_error("Очистка", f"Не удалось удалить папку config: {e}")
                    os.remove(temp_path)
                    messagebox.showerror("Ошибка", "Не удалось удалить старую папку config.")
                    return
            os.makedirs(target_dir, exist_ok=True)
            try:
                with zipfile.ZipFile(temp_path, 'r') as zf:
                    zf.extractall(target_dir)
                self.log_message(f"[РАСПАКОВКА] {name} распакован в {target_dir}")
                messagebox.showinfo("Готово", f"Конфигурация установлена из {name}.")
            except Exception as e:
                self.log_error("Распаковка", f"Ошибка при распаковке: {e}")
                messagebox.showerror("Ошибка", f"Не удалось распаковать {name}.")
            finally:
                os.remove(temp_path)
        else:
            additional_dir = os.path.join(instance_dir, "Доп Установки")
            os.makedirs(additional_dir, exist_ok=True)
            if name.lower().endswith(".zip"):
                try:
                    with zipfile.ZipFile(temp_path, 'r') as zf:
                        zf.extractall(additional_dir)
                    self.log_message(f"[РАСПАКОВКА] {name} распакован в {additional_dir}")
                    messagebox.showinfo("Готово", f"Файл {name} распакован в папку 'Доп Установки'.")
                except Exception as e:
                    self.log_error("Распаковка", f"Ошибка при распаковке: {e}")
                    messagebox.showerror("Ошибка", f"Не удалось распаковать {name}.")
                finally:
                    os.remove(temp_path)
            else:
                dest = os.path.join(additional_dir, name)
                try:
                    shutil.move(temp_path, dest)
                    self.log_message(f"[УСТАНОВЛЕНО] {name} сохранён в {dest}")
                    messagebox.showinfo("Готово", f"Файл {name} сохранён в папку 'Доп Установки'.")
                except Exception as e:
                    self.log_error("Сохранение", f"Ошибка при сохранении: {e}")
                    messagebox.showerror("Ошибка", f"Не удалось сохранить {name}.")

    # ---------- ДИАГНОСТИКА ОБЛАКА ----------
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

    # ---------- РАБОТА С API ----------
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

        if not app.get_instance_dir():
            print("FATAL: No instance directory set. Please run GUI to configure.")
            sys.exit(1)

        if not app.is_instance_installed():
            if not app._install_instance():
                print("FATAL: Cannot install Minecraft instance.")
                sys.exit(1)

        success, _, _ = app.sync_process(silent=True)
        if not success:
            print("WARNING: Sync had errors, but launching anyway.")

        app._launch_game()
        sys.exit(0)
    else:
        app = UpdaterApp()
        app.mainloop()