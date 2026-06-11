#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

_demo_pause() {
  [[ -z "${LAB_DEMO_PAUSE:-"10"}" ]] || sleep 3
}

echo ""
echo "============================================================"
echo "  Лабораторная работа 5"
echo "  Тема: SHA-256 и парадокс дней рождения"
echo "============================================================"
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Справка по программе"
echo "------------------------------------------------------------"
echo "  Сначала посмотрим доступные команды CLI."
echo ""
echo '$ python3 hash_lab.py -v --help'
python3 hash_lab.py -v --help
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Задача 1"
echo "  Полный хеш SHA-256"
echo "------------------------------------------------------------"
echo "  Вычисляем полный SHA-256 для двух разных строк."
echo "  Результат выводится в шестнадцатеричном виде."
echo ""
echo '$ python3 hash_lab.py hash-hex "lab5"'
python3 hash_lab.py hash-hex "lab5"
echo ""
echo '$ python3 hash_lab.py hash-hex "Hash functions lab5 demo text."'
python3 hash_lab.py hash-hex "Hash functions lab5 demo text."
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Задача 2"
echo "  Усечённый хеш"
echo "------------------------------------------------------------"
echo "  Берём не весь SHA-256, а только первые заданные биты."
echo "  В примере используется усечение до 32 бит."
echo ""
echo '$ python3 hash_lab.py truncate "collision" --bits 32'
python3 hash_lab.py truncate "collision" --bits 32
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Задача 3"
echo "  Парадокс дней рождения для усечённого хеша"
echo "------------------------------------------------------------"
echo "  Для bits=20 коллизия обычно находится значительно раньше,"
echo "  чем при полном переборе всех 2^20 возможных значений."
echo ""
echo '$ python3 hash_lab.py birthday-search --bits 20'
python3 hash_lab.py birthday-search --bits 20
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Встроенная демонстрация"
echo "------------------------------------------------------------"
echo "  Запускаем demo-режим с подробными пояснениями."
echo ""
echo '$ python3 hash_lab.py demo'
python3 hash_lab.py demo
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Проверка программы тестами"
echo "------------------------------------------------------------"
echo "  Запускаем автоматические тесты для проверки корректности работы."
echo ""
echo '$ python3 -m pytest test_hash_lab.py -v --tb=short'
python3 -m pytest test_hash_lab.py -v --tb=short

echo ""
_demo_pause
echo "============================================================"
echo "  Демонстрация завершена"
echo "============================================================"