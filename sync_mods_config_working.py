import os
import requests
from urllib.parse import urlencode

# ================= КОНФИГУРАЦИЯ =================
PUBLIC_URL = "https://disk.yandex.ru/d/tenAj8XlAQEPXA"

MINECRAFT_DIR = os.path.join(
    os.environ.get("APPDATA", ""),
    ".minecraft",
    "versions",
    "Sex3"
)
# ================================================

API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_yandex_folder_structure(public_key, remote_folder_path):
    """
    public_key: полный URL или идентификатор (у нас — полный URL)
    remote_folder_path: путь относительно корня публичной папки, начинающийся с '/' (например, '/mods')
    Возвращает (словарь_файлов, флаг_успеха)
    """
    files_dict = {}
    params = {
        'public_key': public_key,
        'path': remote_folder_path,
        'limit': 1000
    }
    final_url = f"{API_BASE_URL}?{urlencode(params)}"
    print(f"[API] Запрос: {final_url}")

    try:
        response = requests.get(final_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"❌ Ошибка HTTP {response.status_code}: {response.text[:200]}")
            return {}, False

        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            print("❌ Сервер вернул не JSON, возможно, требуется капча или авторизация.")
            return {}, False

        data = response.json()
        items = data.get('_embedded', {}).get('items', [])
        if not items:
            print(f"[ОБЛАКО] Папка '{remote_folder_path}' пуста.")

        for item in items:
            name = item['name']
            # относительный путь для локального сохранения (без начального слеша)
            if remote_folder_path == '/':
                relative_path = name
            else:
                relative_path = f"{remote_folder_path.lstrip('/')}/{name}"

            if item['type'] == 'dir':
                # рекурсивно заходим в подпапку
                sub_path = f"{remote_folder_path.rstrip('/')}/{name}"
                sub_files, sub_success = get_yandex_folder_structure(public_key, sub_path)
                if not sub_success:
                    return {}, False
                files_dict.update(sub_files)
            elif item['type'] == 'file':
                files_dict[relative_path] = (item.get('file'), item.get('size', 0))

        return files_dict, True

    except Exception as e:
        print(f"❌ Ошибка сети: {e}")
        return {}, False

def debug_cloud():
    """Показывает содержимое корня публичной папки (path='/' или без path)."""
    print("\n===== ДИАГНОСТИКА ОБЛАКА =====")
    # Можно вообще не передавать path, чтобы получить корень
    params = {'public_key': PUBLIC_URL, 'limit': 1000}
    final_url = f"{API_BASE_URL}?{urlencode(params)}"
    print(f"Диагностический URL: {final_url}")

    try:
        resp = requests.get(final_url, headers=HEADERS, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            items = data.get('_embedded', {}).get('items', [])
            if not items:
                print("Папка пуста.")
            else:
                print(f"Найдено элементов: {len(items)}")
                for item in items:
                    itype = item.get('type', '?')
                    name = item.get('name', '?')
                    print(f"  [{itype}] {name}")
        else:
            print(f"Ошибка HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        print(f"Ошибка при диагностике: {e}")
    print("===============================\n")

def get_local_files(base_dir, folder_name):
    local_dict = {}
    target_path = os.path.join(base_dir, folder_name)
    if not os.path.exists(target_path):
        return local_dict
    for root, dirs, files in os.walk(target_path):
        for file in files:
            full_path = os.path.join(root, file)
            rel_path = os.path.relpath(full_path, base_dir).replace('\\', '/')
            local_dict[rel_path] = os.path.getsize(full_path)
    return local_dict

def download_file(download_url, local_path):
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        response = requests.get(download_url, headers=HEADERS, stream=True, timeout=30)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"Ошибка скачивания {local_path}: {e}")
    return False

def sync_category(folder_path):
    """
    folder_path должен начинаться с '/', например '/mods' или '/config'.
    Это путь в облаке от корня публичной папки.
    """
    print(f"\n[ СИНХРОНИЗАЦИЯ: {folder_path} ]")
    cloud_files, success = get_yandex_folder_structure(PUBLIC_URL, folder_path)
    if not success:
        print(f"⚠️ Пропуск категории '{folder_path}' из-за ошибки доступа.")
        return

    # Локальная папка: убираем начальный слеш
    local_folder = folder_path.lstrip('/')
    local_files = get_local_files(MINECRAFT_DIR, local_folder)

    # Удаление лишних файлов
    deleted = 0
    for local_rel_path in local_files:
        if local_rel_path not in cloud_files:
            full_local_path = os.path.join(MINECRAFT_DIR, local_rel_path.replace('/', os.sep))
            try:
                os.remove(full_local_path)
                print(f"🗑️ Удалён: {local_rel_path}")
                deleted += 1
            except Exception as e:
                print(f"❌ Не удалось удалить {local_rel_path}: {e}")

    # Скачивание/обновление файлов
    downloaded = 0
    for cloud_rel_path, (download_url, cloud_size) in cloud_files.items():
        full_local_path = os.path.join(MINECRAFT_DIR, cloud_rel_path.replace('/', os.sep))
        need_download = False
        if cloud_rel_path not in local_files:
            need_download = True
        elif local_files[cloud_rel_path] != cloud_size:
            print(f"🔄 Изменился размер: {cloud_rel_path}")
            need_download = True

        if need_download:
            print(f"📥 Скачивание: {cloud_rel_path}...")
            if download_file(download_url, full_local_path):
                downloaded += 1
            else:
                print(f"❌ Не удалось скачать: {cloud_rel_path}")

    print(f"Итог по {folder_path}: скачано/обновлено {downloaded}, удалено {deleted}")

def main():
    print("Проверка папки сборки...")
    if not os.path.exists(MINECRAFT_DIR):
        os.makedirs(MINECRAFT_DIR, exist_ok=True)

    # Диагностика корня (без path)
    debug_cloud()

    print("Начало синхронизации...")
    # ВАЖНО: пути должны начинаться с '/'
    sync_category("/mods")
    sync_category("/config")
    print("\n✅ Синхронизация завершена.")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Критическая ошибка: {e}")
    input("\nНажмите Enter для выхода...")