@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

:: ================================================================
::  БАТ-ФАЙЛ ДЛЯ СБОРКИ .PY → .EXE (PyInstaller)
:: ================================================================
::  1. Укажите имя вашего основного скрипта (без .py):
set SCRIPT_NAME=YDPackLauncher

::  2. Выберите режим:
::     console  – показать консольное окно (для отладки)
::     windowed – скрыть консоль (для GUI-приложений)
set MODE=console

::  3. (Опционально) Путь к иконке .ico (если есть):
set ICON_PATH=YDPackLauncher.ico

::  4. Дополнительные флаги PyInstaller (можно менять):
set PYINSTALLER_FLAGS=--onefile --clean

:: ================================================================
::  Проверка наличия Python и pip
:: ================================================================
where python >nul 2>&1
if %errorlevel% neq 0 (
    echo [ОШИБКА] Python не найден в PATH. Установите Python и добавьте в переменные среды.
    pause
    exit /b 1
)

:: ================================================================
::  Установка PyInstaller (если отсутствует)
:: ================================================================
echo [ИНФО] Проверка установки PyInstaller...
python -c "import PyInstaller" >nul 2>&1
if %errorlevel% neq 0 (
    echo [ИНФО] PyInstaller не найден. Установка...
    pip install pyinstaller
    if %errorlevel% neq 0 (
        echo [ОШИБКА] Не удалось установить PyInstaller.
        pause
        exit /b 1
    )
)

:: ================================================================
::  Формирование команды сборки
:: ================================================================
set CMD=pyinstaller %PYINSTALLER_FLAGS%

if /i "%MODE%"=="windowed" (
    set CMD=%CMD% --noconsole
) else (
    set CMD=%CMD% --console
)

if not "%ICON_PATH%"=="" (
    set CMD=%CMD% --icon="%ICON_PATH%"
)

set CMD=%CMD% "%SCRIPT_NAME%.py"

:: ================================================================
::  Запуск сборки
:: ================================================================
echo [ИНФО] Выполняется: %CMD%
%CMD%

if %errorlevel% equ 0 (
    echo [УСПЕХ] Сборка завершена! Исполняемый файл находится в папке .\dist\%SCRIPT_NAME%.exe
) else (
    echo [ОШИБКА] Сборка завершилась с ошибками. Проверьте консоль выше.
)

pause