#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

_demo_pause() {
  [[ -z "${LAB_DEMO_PAUSE:-"10"}" ]] || sleep 3
}

echo ""
echo "============================================================"
echo "  Лабораторная работа 3"
echo "  Тема: потоковые шифры"
echo "============================================================"
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Справка по программе"
echo "------------------------------------------------------------"
echo "  Сначала посмотрим доступные команды CLI."
echo ""
echo '$ python3 stream_ciphers.py -v --help'
python3 stream_ciphers.py -v --help
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Подготовка примеров"
echo "------------------------------------------------------------"
echo "  Создаём каталог samples и необходимые тестовые файлы"
echo "  через основной Python-код программы."
echo ""
echo '$ python3 stream_ciphers.py prepare-samples --dir samples --method secrets'
python3 stream_ciphers.py prepare-samples --dir samples --method secrets
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Задача 1"
echo "  Генерация файла ключа с помощью ГПСЧ"
echo "------------------------------------------------------------"
echo "  Ключ был создан на предыдущем шаге"
echo "  и сохранён в файле samples/key.bin."
echo ""
echo '$ ls -lh samples/plain.txt samples/key.bin'
ls -lh samples/plain.txt samples/key.bin
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Задача 2"
echo "  Шифр Вернама на основе операции XOR"
echo "------------------------------------------------------------"
echo "  Выполняем шифрование файла, затем расшифровываем его обратно."
echo "  После этого сравниваем исходный и восстановленный файлы."
echo ""
echo '$ python3 stream_ciphers.py vernam-encrypt samples/plain.txt samples/key.bin samples/vernam.bin'
python3 stream_ciphers.py vernam-encrypt samples/plain.txt samples/key.bin samples/vernam.bin
echo ""
echo '$ python3 stream_ciphers.py vernam-decrypt samples/vernam.bin samples/key.bin samples/recovered.txt'
python3 stream_ciphers.py vernam-decrypt samples/vernam.bin samples/key.bin samples/recovered.txt
echo ""
echo '$ cmp -s samples/plain.txt samples/recovered.txt && echo "Совпадает: true"'
cmp -s samples/plain.txt samples/recovered.txt && echo "Совпадает: true"
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Задача 3"
echo "  Готовый потоковый шифр ChaCha20"
echo "------------------------------------------------------------"
echo "  Используем ChaCha20 для шифрования и обратного расшифрования."
echo "  Затем проверяем, что исходный файл успешно восстановлен."
echo ""
echo '$ python3 stream_ciphers.py chacha-encrypt samples/plain.txt samples/key.bin samples/chacha.bin'
python3 stream_ciphers.py chacha-encrypt samples/plain.txt samples/key.bin samples/chacha.bin
echo ""
echo '$ python3 stream_ciphers.py chacha-decrypt samples/chacha.bin samples/key.bin samples/chacha_plain.txt'
python3 stream_ciphers.py chacha-decrypt samples/chacha.bin samples/key.bin samples/chacha_plain.txt
echo ""
echo '$ cmp -s samples/plain.txt samples/chacha_plain.txt && echo "Round-trip: true"'
cmp -s samples/plain.txt samples/chacha_plain.txt && echo "Round-trip: true"
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Проверка программы тестами"
echo "------------------------------------------------------------"
echo "  Запускаем автоматические тесты для проверки корректности работы."
echo ""
echo '$ python3 -m pytest test_stream_ciphers.py -v --tb=short'
python3 -m pytest test_stream_ciphers.py -v --tb=short

echo ""
_demo_pause
echo "============================================================"
echo "  Демонстрация завершена"
echo "============================================================"