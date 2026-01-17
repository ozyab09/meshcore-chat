#!/usr/bin/env python3
"""
Скрипт для проверки установки и работоспособности meshchat
"""

import sys
import subprocess
import importlib.util

def check_python_version():
    """Проверяет версию Python"""
    print(f"Версия Python: {sys.version}")
    if sys.version_info < (3, 8):
        print("❌ Рекомендуется использовать Python 3.8 или выше")
        return False
    else:
        print("✅ Версия Python подходит")
        return True

def check_module_installed(module_name):
    """Проверяет, установлен ли модуль"""
    try:
        importlib.util.find_spec(module_name)
        print(f"✅ Модуль {module_name} установлен")
        return True
    except ImportError:
        print(f"❌ Модуль {module_name} не найден")
        return False

def check_executable_exists(cmd):
    """Проверяет, существует ли исполняемый файл"""
    try:
        result = subprocess.run([cmd, "--help"], capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print(f"✅ Команда {cmd} работает")
            return True
        else:
            print(f"❌ Команда {cmd} завершилась с ошибкой")
            return False
    except FileNotFoundError:
        print(f"❌ Команда {cmd} не найдена")
        return False
    except subprocess.TimeoutExpired:
        print(f"⚠️  Команда {cmd} превысила время ожидания")
        return False

def main():
    print("Проверка установки meshchat...")
    print("="*50)
    
    # Проверяем версию Python
    python_ok = check_python_version()
    print()
    
    # Проверяем зависимости
    modules_to_check = ["meshcore", "prompt_toolkit", "pycryptodome"]
    modules_ok = all(check_module_installed(module) for module in modules_to_check)
    print()
    
    # Проверяем, доступна ли команда meshchat
    cmd_ok = check_executable_exists("meshchat")
    print()
    
    # Результат
    print("="*50)
    if python_ok and modules_ok and cmd_ok:
        print("🎉 Все проверки пройдены! meshchat готов к использованию.")
        print("\nДля запуска используйте команду:")
        print("meshchat")
    else:
        print("❌ Обнаружены проблемы с установкой. Пожалуйста, проверьте инструкцию по установке в README.md")
        
        if not python_ok:
            print("- Необходима более новая версия Python")
        if not modules_ok:
            print("- Необходимо установить недостающие модули")
        if not cmd_ok:
            print("- Команда meshchat не найдена, возможно, пакет не установлен корректно")

if __name__ == "__main__":
    main()