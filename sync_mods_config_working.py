import os
import requests
from urllib.parse import urlencode

# ================= КОНФИГУРАЦИЯ =================
# Ваша проверенная публичная ссылка
PUBLIC_URL = "https://disk.yandex.ru/d/tenAj8XlAQEPXA"

# Точный путь к сборке игрока
MINECRAFT_DIR = os.path.join(
    os.environ.get("APPDATA", ""), 
    ".minecraft", 
    "versions", 
    "Sex3"
)
# ================================================

API_BASE_URL = "https://cloud-api.yandex.net/v1/disk/public/resources"

# Маскируемся под обычный браузер, чтобы Яндекс не блокировал запросы
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_yandex_folder_structure(public_key, remote_folder_path):
    """Рекурсивно получает структуру файлов из папки Яндекс.Диска.
    Возвращает (словарь_файлов, флаг_успеха)
    """
    files_dict = {}
    params = {
        'public_key': public_key.strip(),
        'path': remote_folder_path,
        'limit': 1000
    }
    final_url = f"{API_BASE_URL}?{urlencode(params)}"
    
    try:
        response = requests.get(final_url, headers=HEADERS, timeout=15)
        
        if response.status_code != 200:
            print(f"❌ Яндекс.Диск вернул статус-код: {response.status_code}")
            return {}, False
            
        content_type = response.headers.get('Content-Type', '')
        if 'application/json' not in content_type:
            print("❌ Сбой: Сервер прислал веб-страницу (HTML) вместо данных JSON.")
            return {}, False
        
        data = response.json()
        items = data.get('_embedded', {}).get('items', [])
        
        for item in items:
            clean_remote_path = remote_folder_path.strip('/')
            relative_path = f"{clean_remote_path}/{item['name']}" if clean_remote_path else item['name']
            
            if item['type'] == 'dir':
                # Рекурсивный обход подпапок
                sub_files, sub_success = get_yandex_folder_structure(public_key, relative_path)
                if not sub_success:
                    return {}, False
                files_dict.update(sub_files)
            elif item['type'] == 'file':
                files_dict[relative_path] = (item.get('file'), item.get('size', 0))
                
        return files_dict, True
        
    except Exception as e:
        print(f"❌ Ошибка сети при связи с Яндекс.Диском ({remote_folder_path}): {e}")
        return {}, False

def get_local_files(base_dir, folder_name):
    """Собирает список локальных файлов в указанной папке."""
    local_dict = {}
    target_path = os.path.join(base_dir, folder_name)
    if not os.path.exists(target_path):
        return local_dict
        
    for root, dirs, files in os.walk(target_path):
        for file in files:
            full_path = os.path.join(root, file)
            # Приводим к единому формату путей с прямыми слэшами
            rel_path = os.path.relpath(full_path, base_dir).replace('\\', '/')
            local_dict[rel_path] = os.path.getsize(full_path)
            
    return local_dict

def download_file(download_url, local_path):
    """Скачивает файл и заменяет старый."""
    os.makedirs(os.path.dirname(local_path), exist_ok=True)
    try:
        response = requests.get(download_url, headers=HEADERS, stream=True, timeout=30)
        if response.status_code == 200:
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            return True
    except Exception as e:
        print(f"Ошибка при скачивании файла {local_path}: {e}")
    return False

def sync_category(category_name):
    """Синхронизирует категорию с полной защитой локальных файлов игроков."""
    print(f"\n[ СИНХРОНИЗАЦИЯ ПАПКИ: {category_name} ]")
    print(f"Получение списка файлов из облака...")
    
    # Исправлено: теперь корректно принимаем кортеж из двух элементов
    cloud_files, success = get_yandex_folder_structure(PUBLIC_URL, category_name)
    
    if not success:
        print(f"⚠️ Синхронизация папки '{category_name}' ОТМЕНЕНА. Ошибка связи. Локальные файлы НЕ изменены.")
        return
        
    local_files = get_local_files(MINECRAFT_DIR, category_name)
    
    # 1. Удаление лишних файлов (только если успешно прочитали облако)
    deleted_count = 0
    for local_rel_path in local_files:
        if local_rel_path not in cloud_files:
            full_local_path = os.path.join(MINECRAFT_DIR, local_rel_path.replace('/', os.sep))
            try:
                os.remove(full_local_path)
                print(f"🗑️ Удален лишний/старый файл: {local_rel_path}")
                deleted_count += 1
            except Exception as e:
                print(f"❌ Не удалось удалить {local_rel_path}: {e}")
                
    # 2. Скачивание новых и обновление изменившихся по размеру файлов
    downloaded_count = 0
    for cloud_rel_path, (download_url, cloud_size) in cloud_files.items():
        full_local_path = os.path.join(MINECRAFT_DIR, cloud_rel_path.replace('/', os.sep))
        
        need_download = False
        if cloud_rel_path not in local_files:
            need_download = True
        elif local_files[cloud_rel_path] != cloud_size:
            print(f"🔄 Изменился размер в облаке: {cloud_rel_path}")
            need_download = True
            
        if need_download:
            print(f"📥 Скачивание: {cloud_rel_path}...")
            if download_file(download_url, full_local_path):
                downloaded_count += 1
            else:
                print(f"❌ Ошибка скачивания: {cloud_rel_path}")
                
    print(f"Итог по {category_name}: скачано/обновлено: {downloaded_count}, удалено: {deleted_count}.")

def main():
    print("Проверка папки назначения...")
    if not os.path.exists(MINECRAFT_DIR):
        print(f"Папка сборки не найдена по пути: {MINECRAFT_DIR}")
        print("Создаем структуру папок автоматически...")
        os.makedirs(MINECRAFT_DIR, exist_ok=True)

    print("Начало синхронизации модов и конфигурации сборки...")
    
    sync_category("/mods")
    sync_category("config")

    print("\n✅ Синхронизация успешно завершена!")

if __name__ == "__main__":
    try:
        main()
    except Exception as general_error:
        print(f"\nКритическая ошибка работы апдейтера: {general_error}")
    input("\nНажмите Enter для выхода...")
