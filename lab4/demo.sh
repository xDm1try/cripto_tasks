#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

_demo_pause() {
  [[ -z "${LAB_DEMO_PAUSE:-"10"}" ]] || sleep 3
}

echo ""
echo "============================================================"
echo "  Лабораторная работа 4"
echo "  Тема: XTEA и режим CBC"
echo "============================================================"
echo ""

echo "------------------------------------------------------------"
echo "  Справка по программе"
echo "------------------------------------------------------------"
echo "  Сначала посмотрим доступные команды CLI."
echo ""
echo '$ python3 block_cipher.py -v --help'
python3 block_cipher.py -v --help
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Подготовка примеров"
echo "------------------------------------------------------------"
echo "  Создаём каталог samples и необходимые файлы"
echo "  для демонстрации работы блочного шифра."
echo ""
echo '$ python3 block_cipher.py prepare-samples --dir samples'
python3 block_cipher.py prepare-samples --dir samples
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Задача 1"
echo "  Итеративный блочный шифр XTEA"
echo "------------------------------------------------------------"
echo "  Запускаем встроенную демонстрацию:"
echo "  шифрование одного блока и шифрование файла в режиме CBC."
echo ""
echo '$ python3 block_cipher.py demo --dir samples'
python3 block_cipher.py demo --dir samples
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Задача 2"
echo "  Шифрование и расшифрование файла XTEA-CBC"
echo "------------------------------------------------------------"
echo "  Шифруем исходный файл с использованием ключа,"
echo "  затем расшифровываем его обратно."
echo "  После этого сравниваем исходный и восстановленный файлы."
echo ""
echo '$ python3 block_cipher.py encrypt samples/plain.txt samples/cipher.bin --key-file samples/key.bin'
python3 block_cipher.py encrypt samples/plain.txt samples/cipher.bin --key-file samples/key.bin
echo ""
echo '$ python3 block_cipher.py decrypt samples/cipher.bin samples/restored.txt --key-file samples/key.bin'
python3 block_cipher.py decrypt samples/cipher.bin samples/restored.txt --key-file samples/key.bin
echo ""
echo '$ cmp -s samples/plain.txt samples/restored.txt && echo "Совпадает: true"'
cmp -s samples/plain.txt samples/restored.txt && echo "Совпадает: true"
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Проверка программы тестами"
echo "------------------------------------------------------------"
echo "  Запускаем автоматические тесты для проверки корректности работы."
echo ""
echo '$ python3 -m pytest test_block_cipher.py -v --tb=short'
python3 -m pytest test_block_cipher.py -v --tb=short

echo ""
_demo_pause
echo "============================================================"
echo "  Демонстрация завершена"
echo "============================================================"