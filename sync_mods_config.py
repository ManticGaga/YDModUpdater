import json
import os
import threading
import sys
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

import requests

# ================= ЗНАЧЕНИЯ ПО УМОЛЧАНИЮ =================
DEFAULT_MINECRAFT_DIR = os.path.join(
    os.environ.get("APPDATA", ""), ".minecraft", "versions", "Sex3"
)
DEFAULT_PUBLIC_URL = "https://disk.yandex.ru/d/tenAj8XlAQEPXA"
# =========================================================

# Ключ: имя на диске (без лишних слэшей).
# Работаем только с папкой mods — папку config трогать не нужно.
CATEGORIES = {"Моды (mods)": "mods"}

API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def resolve_public_key(url_or_key):
    """Готовит значение параметра public_key для API Яндекс.Диска.

    Для современных коротких ссылок вида https://disk.yandex.ru/d/xxxxx
    API принимает только ПОЛНУЮ ссылку в качестве public_key.
    """
    if not url_or_key:
        return ""
    return url_or_key.strip()


class UpdaterApp(tk.Tk):

    def __init__(self):
        super().__init__()
        self.title("Minecraft Modpack Updater")
        self.geometry("600x550")
        self.resizable(False, False)

        # ---------- ОПРЕДЕЛЯЕМ ПУТЬ К ПАПКЕ С ПРОГРАММОЙ ----------
        if getattr(sys, 'frozen', False):
            # Запущено из PyInstaller exe
            base_path = os.path.dirname(sys.executable)
        else:
            # Обычный Python-скрипт
            base_path = os.path.dirname(os.path.abspath(__file__))

        self.config_path = os.path.join(base_path, "updater_config.json")

        # Загружаем или запрашиваем настройки
        self.minecraft_dir, self.public_url = self.load_or_create_config()
        self.public_key = resolve_public_key(self.public_url)

        self.checkbox_vars = {}
        self.create_widgets()

    # ---------- работа с конфигурацией ----------
    def load_or_create_config(self):
        """Загружает конфиг из JSON или запускает диалог первого запуска."""
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

        # Если конфиг пуст или отсутствуют ключи, показываем диалог
        if not config or "minecraft_dir" not in config or "public_url" not in config:
            config = self.request_config_dialog(
                config.get("minecraft_dir", DEFAULT_MINECRAFT_DIR),
                config.get("public_url", DEFAULT_PUBLIC_URL),
            )
            # Сохраняем, даже если пользователь ничего не менял (чтобы файл появился)
            self.save_config(config["minecraft_dir"], config["public_url"])

        return config.get("minecraft_dir", DEFAULT_MINECRAFT_DIR), config.get(
            "public_url", DEFAULT_PUBLIC_URL
        )

    def save_config(self, minecraft_dir, public_url):
        """Записывает настройки в JSON."""
        config = {"minecraft_dir": minecraft_dir, "public_url": public_url}
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            messagebox.showwarning(
                "Ошибка сохранения",
                f"Не удалось записать файл настроек:\n{e}",
            )

    def request_config_dialog(self, current_dir, current_url):
        """Показывает диалог настройки пути и ссылки, возвращает словарь с ключами."""
        dialog = tk.Toplevel(self)
        dialog.title("Настройки обновления")
        dialog.geometry("550x220")
        dialog.resizable(False, False)
        dialog.grab_set()  # модальное окно

        result = {"minecraft_dir": current_dir, "public_url": current_url}

        # ----- Поле выбора папки -----
        tk.Label(dialog, text="Папка Minecraft (со сборкой):").grid(
            row=0, column=0, sticky="w", padx=10, pady=(15, 0)
        )
        dir_var = tk.StringVar(value=result["minecraft_dir"])
        entry_dir = tk.Entry(dialog, textvariable=dir_var, width=50)
        entry_dir.grid(row=1, column=0, padx=(10, 5), pady=5, sticky="we")

        def browse_folder():
            path = filedialog.askdirectory(
                title="Выберите папку сборки Minecraft",
                initialdir=os.path.dirname(dir_var.get()) if dir_var.get() else "",
            )
            if path:
                dir_var.set(path)

        btn_browse = tk.Button(dialog, text="Обзор...", command=browse_folder)
        btn_browse.grid(row=1, column=1, padx=(0, 10), pady=5)

        # ----- Поле для публичной ссылки -----
        tk.Label(dialog, text="Публичная ссылка Яндекс.Диска:").grid(
            row=2, column=0, sticky="w", padx=10, pady=(15, 0)
        )
        url_var = tk.StringVar(value=result["public_url"])
        entry_url = tk.Entry(dialog, textvariable=url_var, width=50)
        entry_url.grid(row=3, column=0, padx=(10, 5), pady=5, sticky="we")

        # ----- Кнопки -----
        def on_save():
            result["minecraft_dir"] = dir_var.get().strip()
            result["public_url"] = url_var.get().strip()
            dialog.destroy()

        def on_default():
            dir_var.set(DEFAULT_MINECRAFT_DIR)
            url_var.set(DEFAULT_PUBLIC_URL)

        frame_buttons = tk.Frame(dialog)
        frame_buttons.grid(row=4, column=0, columnspan=2, pady=15)
        tk.Button(
            frame_buttons,
            text="По умолчанию",
            command=on_default,
            width=14,
        ).pack(side="left", padx=5)
        tk.Button(
            frame_buttons,
            text="Сохранить",
            command=on_save,
            bg="#4CAF50",
            fg="white",
            width=14,
        ).pack(side="left", padx=5)

        # Ждём закрытия диалога
        self.wait_window(dialog)
        return result

    # ---------- GUI основного окна ----------
    def create_widgets(self):
        lbl_title = tk.Label(
            self, text="Синхронизация сборки Minecraft", font=("Arial", 14, "bold")
        )
        lbl_title.pack(pady=10)

        frame_checks = tk.LabelFrame(
            self, text=" Выберите компоненты для установки ", padx=15, pady=10
        )
        frame_checks.pack(fill="x", padx=20, pady=5)

        for name, path in CATEGORIES.items():
            var = tk.BooleanVar(value=True)
            self.checkbox_vars[path] = var
            chk = tk.Checkbutton(
                frame_checks, text=name, variable=var, font=("Arial", 10)
            )
            chk.pack(anchor="w", pady=2)

        self.progress = ttk.Progressbar(
            self, orient="horizontal", length=450, mode="determinate"
        )
        self.progress.pack(pady=15)

        frame_buttons = tk.Frame(self)
        frame_buttons.pack(pady=5)

        self.btn_start = tk.Button(
            frame_buttons,
            text="Начать обновление",
            command=self.start_sync_thread,
            bg="#4CAF50",
            fg="white",
            font=("Arial", 11, "bold"),
            padx=10,
            pady=5,
        )
        self.btn_start.pack(side="left", padx=10)

        self.btn_copy = tk.Button(
            frame_buttons,
            text="Скопировать логи",
            command=self.copy_logs_to_clipboard,
            bg="#2196F3",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_copy.pack(side="left", padx=10)

        self.btn_diag = tk.Button(
            frame_buttons,
            text="Диагностика облака",
            command=self.start_debug_thread,
            bg="#9E9E9E",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_diag.pack(side="left", padx=10)

        self.btn_config = tk.Button(
            frame_buttons,
            text="Настройки",
            command=self.open_settings,
            bg="#FF9800",
            fg="white",
            font=("Arial", 11),
            padx=10,
            pady=5,
        )
        self.btn_config.pack(side="left", padx=10)

        self.txt_log = tk.Text(
            self, height=10, width=75, font=("Consolas", 9), bg="#1e1e1e", fg="#ffffff"
        )
        self.txt_log.pack(pady=10, padx=20)
        self.log_message("[СИСТЕМА] Инициализация завершена. Готов к работе.")
        self.log_message(f"[СИСТЕМА] Используется публичный ключ: {self.public_key}")

    def open_settings(self):
        """Повторно открывает диалог настроек и применяет изменения."""
        new_config = self.request_config_dialog(
            self.minecraft_dir, self.public_url
        )
        if new_config:
            self.minecraft_dir = new_config["minecraft_dir"]
            self.public_url = new_config["public_url"]
            self.public_key = resolve_public_key(self.public_url)
            self.save_config(self.minecraft_dir, self.public_url)
            self.log_message("[СИСТЕМА] Настройки обновлены.")
            messagebox.showinfo(
                "Настройки",
                "Настройки сохранены. Новый путь и ссылка будут использованы при следующем обновлении.",
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

    def sync_completed(self, downloaded, deleted):
        self.log_message(
            f"\n✨ [УСПЕХ] Скачано файлов: {downloaded}, удалено устаревших: {deleted}."
        )
        self.btn_start.config(state=tk.NORMAL)
        messagebox.showinfo("Готово", "Синхронизация успешно завершена!")

    def start_sync_thread(self):
        selected_paths = [
            path for path, var in self.checkbox_vars.items() if var.get()
        ]
        if not selected_paths:
            messagebox.showwarning("Внимание", "Выберите компоненты для скачивания!")
            return

        self.btn_start.config(state=tk.DISABLED)
        self.progress["value"] = 0
        threading.Thread(
            target=self.sync_process, args=(selected_paths,), daemon=True
        ).start()

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
        self.after(
            0, self.log_message, f"[ДИАГНОСТИКА] В корне облака найдено элементов: {len(items)}"
        )
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

            self.after(
                0,
                self.log_message,
                f"[СЕТЬ] Запрос API: {API_BASE_URL} с параметрами {params}",
            )

            try:
                response = requests.get(
                    API_BASE_URL, params=params, headers=HEADERS, timeout=15
                )
            except requests.exceptions.RequestException as e:
                self.after(0, self.log_error, "Сеть", f"Ошибка запроса к API: {e}")
                return [], False

            if response.status_code == 404:
                self.after(
                    0,
                    self.log_error,
                    "Сеть",
                    f"Ресурс '{api_path or 'корень'}' не найден (HTTP 404).",
                )
                return [], False
            if response.status_code != 200:
                self.after(
                    0,
                    self.log_error,
                    "Сеть",
                    f"Сервер API ответил HTTP {response.status_code}: {response.text[:200]}",
                )
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
                if not self.collect_files_recursive(
                    public_key, item.get("path"), rel_path, files_dict
                ):
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

        target = next(
            (
                it
                for it in root_items
                if it.get("type") == "dir" and it.get("name") == folder_name
            ),
            None,
        )
        if target is None:
            self.after(
                0,
                self.log_error,
                "Облако",
                f"Папка '{folder_name}' не найдена в корне публичной ссылки. "
                "Проверьте имя (кнопка 'Диагностика облака').",
            )
            return {}, False

        files_dict = {}
        ok = self.collect_files_recursive(
            public_key, target.get("path"), folder_name, files_dict
        )
        if not ok:
            return {}, False

        self.after(
            0,
            self.log_message,
            f"[ОБЛАКО] Прочитано файлов в папке '{folder_name}': {len(files_dict)}",
        )
        return files_dict, True

    def get_local_files(self, base_dir, folder_name):
        local_dict = {}
        target_path = os.path.join(base_dir, folder_name)
        if not os.path.exists(target_path):
            self.after(
                0,
                self.log_message,
                f"[ДИСК] Локальная папка не существует: {target_path} (будет создана)",
            )
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
            response = requests.get(
                download_url, headers=HEADERS, stream=True, timeout=30
            )
            if response.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                return True
            else:
                self.after(
                    0,
                    self.log_error,
                    "Скачивание",
                    f"Ошибка HTTP {response.status_code} для файла {os.path.basename(local_path)}",
                )
                return False
        except Exception as e:
            self.after(
                0,
                self.log_error,
                "Скачивание",
                f"Сбой при сохранении файла {os.path.basename(local_path)}: {e}",
            )
            return False

    # ---------- основной процесс синхронизации ----------
    def sync_process(self, selected_paths):
        self.after(
            0, self.log_message, f"[СТАРТ] Назначена папка сборки: {self.minecraft_dir}"
        )

        if not os.path.exists(self.minecraft_dir):
            try:
                os.makedirs(self.minecraft_dir, exist_ok=True)
                self.after(0, self.log_message, "[ДИСК] Создана корневая папка сборки.")
            except Exception as e:
                self.after(
                    0,
                    self.log_error,
                    "Диск",
                    f"Не удалось создать корневую папку {self.minecraft_dir}: {e}",
                )
                self.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
                return

        total_actions = []
        has_errors = False

        self.after(0, self.log_message, "\n--- ЭТАП 1: Получение структуры файлов ---")

        for path in selected_paths:
            cloud_files, success = self.get_yandex_folder_structure(
                self.public_key, path
            )
            if not success:
                self.after(
                    0,
                    self.log_error,
                    "Синхронизация",
                    f"Пропуск категории '{path}' из-за ошибки доступа к облаку.",
                )
                has_errors = True
                continue

            local_files = self.get_local_files(self.minecraft_dir, path)

            for local_rel_path in local_files:
                if local_rel_path not in cloud_files:
                    total_actions.append(("delete", local_rel_path, None))

            for cloud_rel_path, (download_url, cloud_size) in cloud_files.items():
                if cloud_rel_path not in local_files:
                    total_actions.append(("download", cloud_rel_path, download_url))
                elif local_files[cloud_rel_path] != cloud_size:
                    self.after(
                        0,
                        self.log_message,
                        f"[ОБНОВЛЕНИЕ] Изменился размер файла: {cloud_rel_path}",
                    )
                    total_actions.append(("download", cloud_rel_path, download_url))

        if has_errors and not total_actions:
            self.after(
                0,
                self.log_message,
                "\n⚠️ [ЗАВЕРШЕНО С ОШИБКАМИ] Не удалось получить данные из облака.",
            )
            self.after(0, self.debug_cloud)
            self.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Ошибка синхронизации",
                    "Не удалось прочитать список файлов на Яндекс.Диске.\n"
                    "Проверьте лог диагностики: возможно, имена папок 'mods'/'config' "
                    "на диске отличаются от ожидаемых.",
                ),
            )
            return

        total_tasks = len(total_actions)
        if total_tasks == 0:
            self.after(
                0,
                self.log_message,
                "\n✨ [РЕЗУЛЬТАТ] Все локальные файлы полностью соответствуют облаку!",
            )
            self.after(0, self.update_gui_progress, 100)
            self.after(
                0,
                lambda: [
                    self.btn_start.config(state=tk.NORMAL),
                    messagebox.showinfo(
                        "Готово", "У вас установлена актуальная версия сборки!"
                    ),
                ],
            )
            return

        self.after(
            0,
            self.log_message,
            f"\n--- ЭТАП 2: Выполнение изменений (Всего задач: {total_tasks}) ---",
        )

        completed_tasks = 0
        downloaded = 0
        deleted = 0

        for action_type, rel_path, url in total_actions:
            full_local_path = os.path.join(
                self.minecraft_dir, rel_path.replace("/", os.sep)
            )

            if action_type == "delete":
                try:
                    os.remove(full_local_path)
                    self.after(0, self.log_message, f"🗑 Удален лишний файл: {rel_path}")
                    deleted += 1
                except Exception as e:
                    self.after(
                        0,
                        self.log_error,
                        "Диск",
                        f"Не удалось удалить файл {rel_path}: {e}",
                    )
                    has_errors = True
            elif action_type == "download":
                self.after(0, self.log_message, f"📥 Установка: {rel_path}")
                if self.download_file(url, full_local_path):
                    downloaded += 1
                else:
                    self.after(
                        0,
                        self.log_error,
                        "Синхронизация",
                        f"Не удалось установить: {rel_path}",
                    )
                    has_errors = True

            completed_tasks += 1
            percent = int((completed_tasks / total_tasks) * 100)
            self.after(0, self.update_gui_progress, percent)

        if has_errors:
            self.after(
                0,
                self.log_message,
                f"\n⚠️ [ЗАВЕРШЕНО С ОШИБКАМИ] Успешно обработано файлов: {downloaded + deleted} из {total_tasks}.",
            )
            self.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
            self.after(
                0,
                lambda: messagebox.showwarning(
                    "Предупреждение",
                    "Обновление завершено, но некоторые файлы не удалось обработать.",
                ),
            )
        else:
            self.after(0, self.sync_completed, downloaded, deleted)


if __name__ == "__main__":
    app = UpdaterApp()
    app.mainloop()