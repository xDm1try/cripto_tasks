#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

_demo_pause() {
  [[ -z "${LAB_DEMO_PAUSE:-"10"}" ]] || sleep 3
}

echo ""
echo "============================================================"
echo "  Лабораторная работа 2"
echo "  Тема: энтропия и частоты байтов"
echo "============================================================"
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 0"
echo "  Подготовка тестовых файлов"
echo "------------------------------------------------------------"
echo "  Генерируем набор файлов для дальнейших экспериментов."
echo ""
echo '$ python3 entropy_lab.py demo -n 8000 --seed 42'
python3 entropy_lab.py demo -n 8000 --seed 42
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 1"
echo "  Просмотр доступных команд"
echo "------------------------------------------------------------"
echo "  Выводим справку по программе и доступным режимам работы."
echo ""
echo '$ python3 entropy_lab.py --help'
python3 entropy_lab.py --help
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 2"
echo "  Частоты символов"
echo "------------------------------------------------------------"
echo "  Рассматриваем пример для текстового файла."
echo "  Программа показывает наиболее часто встречающиеся байты."
echo ""
echo '$ python3 entropy_lab.py freq samples/sample_text.txt --top 8'
python3 entropy_lab.py freq samples/sample_text.txt --top 8
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 3"
echo "  Энтропия файла из одного символа"
echo "------------------------------------------------------------"
echo "  В таком файле почти нет неопределённости,"
echo "  поэтому значение энтропии должно быть близко к нулю."
echo ""
echo '$ python3 entropy_lab.py entropy samples/sample_const.bin --top 4'
python3 entropy_lab.py entropy samples/sample_const.bin --top 4
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 4"
echo "  Случайная последовательность из 0 и 1"
echo "------------------------------------------------------------"
echo "  Для равновероятных 0 и 1 ожидаем энтропию около 1 бита."
echo ""
echo '$ python3 entropy_lab.py entropy samples/sample_coin.txt --top 4'
python3 entropy_lab.py entropy samples/sample_coin.txt --top 4
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 5"
echo "  Случайные байты от 0 до 255"
echo "------------------------------------------------------------"
echo "  При почти равномерном распределении по всем байтам"
echo "  энтропия должна быть близка к максимуму — 8 битам."
echo ""
echo '$ python3 entropy_lab.py entropy samples/sample_uniform255.bin --top 8'
python3 entropy_lab.py entropy samples/sample_uniform255.bin --top 8
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 6"
echo "  Два символа с равными вероятностями"
echo "------------------------------------------------------------"
echo "  Если два символа встречаются примерно одинаково часто,"
echo "  ожидаем энтропию около 1 бита."
echo ""
echo '$ python3 entropy_lab.py entropy samples/sample_two_equal.bin --top 4'
python3 entropy_lab.py entropy samples/sample_two_equal.bin --top 4
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 7"
echo "  Повторяющийся текст"
echo "------------------------------------------------------------"
echo "  В повторяющемся тексте распределение байтов неравномерное,"
echo "  поэтому энтропия ниже максимально возможной."
echo ""
echo '$ python3 entropy_lab.py entropy samples/sample_text.txt --top 8'
python3 entropy_lab.py entropy samples/sample_text.txt --top 8
echo ""
_demo_pause

echo "------------------------------------------------------------"
echo "  Шаг 8"
echo "  Проверка программы тестами"
echo "------------------------------------------------------------"
echo "  Запускаем автоматические тесты для проверки корректности работы."
echo ""
echo '$ python3 -m pytest test_entropy_lab.py -v --tb=short'
python3 -m pytest test_entropy_lab.py -v --tb=short

echo ""
echo "============================================================"
echo "  Демонстрация завершена"
echo "============================================================"