import os
import threading
import traceback
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.parse import urlencode
import requests

# ================= КОНФИГУРАЦИЯ =================
PUBLIC_URL = "https://disk.yandex.ru/d/tenAj8XlAQEPXA"

MINECRAFT_DIR = os.path.join(
    os.environ.get("APPDATA", ""), ".minecraft", "versions", "Sex3"
)

# Ключ: имя на диске (без лишних слэшей)
CATEGORIES = {"Моды (mods)": "mods", "Конфиги (config)": "config"}
# ================================================

API_BASE_URL = "https://yandex.net"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


class UpdaterApp(tk.Tk):

    def __init__(self):
        super().__init__()

        self.title("Minecraft Modpack Updater")
        self.geometry("600x480")  # Оптимальная высота под кнопки и консоль
        self.resizable(False, False)

        self.checkbox_vars = {}
        self.create_widgets()

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

        # Контейнер для кнопок, чтобы они стояли красиво в ряд
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

        # ВОЗВРАЩЕНА: Кнопка копирования логов
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

        self.txt_log = tk.Text(
            self, height=10, width=75, font=("Consolas", 9), bg="#1e1e1e", fg="#ffffff"
        )
        self.txt_log.pack(pady=10, padx=20)
        self.log_message("[СИСТЕМА] Инициализация завершена. Готов к работе.")

    def log_message(self, message):
        """Вывод логов в окно программы."""
        self.txt_log.insert(tk.END, message + "\n")
        self.txt_log.see(tk.END)

    def log_error(self, ctx, err_text):
        """Специальный вывод ошибок ярким маркером."""
        self.log_message(f"❌ [{ctx.upper()}] {err_text}")

    def copy_logs_to_clipboard(self):
        """Копирует весь текст из консоли в буфер обмена Windows/системы."""
        logs_text = self.txt_log.get("1.0", tk.END).strip()
        self.clipboard_clear()
        self.clipboard_append(logs_text)
        messagebox.showinfo("Буфер обмена", "Логи успешно скопированы!")

    def update_gui_progress(self, percent):
        self.progress["value"] = percent

    def sync_completed(self, downloaded, deleted):
        self.log_message(f"\n✨ [УСПЕХ] Скачано файлов: {downloaded}, удалено устаревших: {deleted}.")
        self.btn_start.config(state=tk.NORMAL)
        messagebox.showinfo("Готово", "Синхронизация успешно завершена!")

    def start_sync_thread(self):
        selected_paths = [
            path for path, var in self.checkbox_vars.items() if var.get()
        ]

        if not selected_paths:
            messagebox.showwarning(
                "Внимание", "Выберите компоненты для скачивания!"
            )
            return

        self.btn_start.config(state=tk.DISABLED)
        self.progress["value"] = 0

        threading.Thread(
            target=self.sync_process, args=(selected_paths,), daemon=True
        ).start()

    def get_yandex_folder_structure(self, public_key, remote_folder_path=""):
        """
        Получает структуру файлов из публичной папки Яндекс.Диска через официальное API.
        public_key — идентификатор папки (из ссылки).
        remote_folder_path — относительный путь внутри папки (например, "mods").
        """
        files_dict = {}
        api_url = "https://cloud-api.yandex.net/v1/disk/public/resources"

        params = {
            "public_key": public_key,
            "path": remote_folder_path.strip("/") if remote_folder_path else ""
        }
        # Убираем пустой path, если не задан
        if not params["path"]:
            del params["path"]

        self.after(
            0,
            self.log_message,
            f"[СЕТЬ] Запрос API: {api_url} с параметрами {params}"
        )

        try:
            response = requests.get(api_url, params=params, headers=HEADERS, timeout=15)
            if response.status_code != 200:
                self.after(
                    0,
                    self.log_error,
                    "Сеть",
                    f"Сервер API ответил HTTP {response.status_code}: {response.text[:200]}"
                )
                return {}, False

            data = response.json()
            # В ответе могут быть ключи _embedded.items или просто items
            items = data.get("_embedded", {}).get("items") or data.get("items")
            if not items:
                self.after(
                    0,
                    self.log_message,
                    f"[ОБЛАКО] В папке '{remote_folder_path or 'корень'}' нет элементов."
                )
                return files_dict, True

            for item in items:
                name = item.get("name")
                if not name:
                    continue

                # Формируем относительный путь
                if remote_folder_path:
                    rel_path = f"{remote_folder_path}/{name}"
                else:
                    rel_path = name

                if item.get("type") == "dir":
                    # Рекурсивно читаем подпапку
                    sub_files, sub_ok = self.get_yandex_folder_structure(
                        public_key, rel_path
                    )
                    if not sub_ok:
                        return {}, False
                    files_dict.update(sub_files)
                elif item.get("type") == "file":
                    # У файла есть поле 'file' — прямая ссылка на скачивание
                    download_url = item.get("file")
                    size = item.get("size", 0)
                    if download_url:
                        files_dict[rel_path] = (download_url, size)

            self.after(
                0,
                self.log_message,
                f"[ОБЛАКО] Прочитано файлов в '{remote_folder_path or 'корень'}': {len(files_dict)}"
            )
            return files_dict, True

        except requests.exceptions.RequestException as e:
            self.after(0, self.log_error, "Сеть", f"Ошибка запроса к API: {e}")
            return {}, False
        except Exception as e:
            self.after(0, self.log_error, "Сеть", f"Критическая ошибка при разборе JSON: {e}")
            return {}, False
            
    def get_local_files(self, base_dir, folder_name):
        """Собирает список локальных файлов в указанной папке."""
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
                rel_path = os.path.relpath(full_path, base_dir).replace(
                    "\\", "/"
                )
                local_dict[rel_path] = os.path.getsize(full_path)
        return local_dict

    def download_file(self, download_url, local_path):
        """Скачивает один файл и заменяет старый."""
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

    def sync_process(self, selected_paths):
        """Основной рабочий процесс синхронизации с пофайловой логикой и точным прогресс-баром."""
        self.after(
            0, self.log_message, f"[СТАРТ] Назначена папка сборки: {MINECRAFT_DIR}"
        )

        if not os.path.exists(MINECRAFT_DIR):
            try:
                os.makedirs(MINECRAFT_DIR, exist_ok=True)
                self.after(
                    0, self.log_message, "[ДИСК] Создана корневая папка сборки."
                )
            except Exception as e:
                self.after(
                    0,
                    self.log_error,
                    "Диск",
                    f"Не удалось создать корневую папку {MINECRAFT_DIR}: {e}",
                )
                self.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
                return

        total_actions = []
        has_errors = False  # Флаг обнаружения ошибок в процессе

        # Шаг 1: Сканирование облака и локального ПК
        self.after(
            0, self.log_message, "\n--- ЭТАП 1: Получение структуры файлов ---"
        )
        for path in selected_paths:
            cloud_files, success = self.get_yandex_folder_structure(
                PUBLIC_URL, path
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

            local_files = self.get_local_files(MINECRAFT_DIR, path)

            # Находим локальные файлы, которых больше нет в облаке (подлежат удалению)
            for local_rel_path in local_files:
                if local_rel_path not in cloud_files:
                    total_actions.append(("delete", local_rel_path, None))

            # Находим новые файлы или файлы с изменившимся размером (подлежат скачиванию)
            for cloud_rel_path, (download_url, cloud_size) in cloud_files.items():
                if cloud_rel_path not in local_files:
                    total_actions.append(
                        ("download", cloud_rel_path, download_url)
                    )
                elif local_files[cloud_rel_path] != cloud_size:
                    self.after(
                        0,
                        self.log_message,
                        f"[ОБНОВЛЕНИЕ] Изменился размер файла: {cloud_rel_path}",
                    )
                    total_actions.append(
                        ("download", cloud_rel_path, download_url)
                    )

        # Прерываем процесс, если облако вообще не ответило
        if has_errors and not total_actions:
            self.after(
                0,
                self.log_message,
                "\n⚠️ [ЗАВЕРШЕНО С ОШИБКАМИ] Не удалось получить данные из облака.",
            )
            self.after(0, lambda: self.btn_start.config(state=tk.NORMAL))
            self.after(
                0,
                lambda: messagebox.showerror(
                    "Ошибка синхронизации",
                    "Не удалось прочитать список файлов на Яндекс.Диске.",
                ),
            )
            return

        total_tasks = len(total_actions)

        # Если изменений нет
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

        # Шаг 2: Пофайловое выполнение изменений и обновление прогресс-бара
        for action_type, rel_path, url in total_actions:
            full_local_path = os.path.join(
                MINECRAFT_DIR, rel_path.replace("/", os.sep)
            )

            if action_type == "delete":
                try:
                    os.remove(full_local_path)
                    self.after(
                        0, self.log_message, f"🗑️ Удален лишний файл: {rel_path}"
                    )
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

            # Рассчитываем процент выполнения на основе завершенных файлов
            completed_tasks += 1
            percent = int((completed_tasks / total_tasks) * 100)
            self.after(0, self.update_gui_progress, percent)

        # Финальный отчет
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
