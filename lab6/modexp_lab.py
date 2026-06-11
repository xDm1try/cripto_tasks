from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

import click

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


def hamming_weight(x: int) -> int:
    """Число единичных бит в двоичной записи x (x >= 0)."""
    if x < 0:
        raise ValueError(f"x должно быть >= 0, получено {x}")
    w = 0
    n = x
    while n > 0:
        w += n & 1
        n >>= 1
    return w


def bit_length(x: int) -> int:
    """Длина двоичной записи x; для x=0 возвращает 1."""
    if x < 0:
        raise ValueError(f"x должно быть >= 0, получено {x}")
    if x == 0:
        return 1
    n, k = x, 0
    while n > 0:
        k += 1
        n >>= 1
    return k


def _validate_modexp_args(a: int, x: int, p: int) -> None:
    if p < 1:
        raise ValueError(f"модуль p должен быть >= 1, получено {p}")
    if x < 0:
        raise ValueError(f"показатель x должен быть >= 0, получено {x}")
    if a < 0:
        raise ValueError(f"основание a должно быть >= 0, получено {a}")


def naive_modexp(a: int, x: int, p: int) -> tuple[int, int]:
    """Медленное a^x mod p циклом из x умножений. Возвращает (результат, число умножений)."""
    _validate_modexp_args(a, x, p)
    if p == 1:
        return 0, 0
    result = 1 % p
    mults = 0
    base = a % p
    for _ in range(x):
        result = (result * base) % p
        mults += 1
    return result, mults


@dataclass
class TraceStep:
    """Колонка таблицы трассировки для бита i показателя x."""

    i: int
    power_of_two: int
    a_pow_raw: int
    a_pow_mod: int
    bit: int
    mul_raw: int | None
    mul_mod: int | None
    is_init: bool


def fast_modexp_traced(a: int, x: int, p: int) -> tuple[int, int, list[TraceStep]]:
    """
    a^x mod p методом «квадратирование и умножение» (биты x от младшего к старшему).

    Возвращает (результат, число умножений, шаги трассировки).
    """
    _validate_modexp_args(a, x, p)
    if p == 1:
        return 0, 0, []
    if x == 0:
        return 1 % p, 0, []

    n_bits = bit_length(x)
    bits = [(x >> i) & 1 for i in range(n_bits)]

    mults = 0
    result: int | None = None
    a_pow_mod = a % p
    trace: list[TraceStep] = []

    for i, bit in enumerate(bits):
        if i == 0:
            raw = a
        else:
            raw = a_pow_mod * a_pow_mod
            mults += 1
            a_pow_mod = raw % p

        mul_raw: int | None = None
        mul_mod: int | None = None
        is_init = False
        if bit == 1:
            if result is None:
                result = a_pow_mod
                is_init = True
            else:
                mul_raw = result * a_pow_mod
                mults += 1
                result = mul_raw % p
                mul_mod = result

        trace.append(
            TraceStep(
                i=i,
                power_of_two=1 << i,
                a_pow_raw=raw,
                a_pow_mod=a_pow_mod,
                bit=bit,
                mul_raw=mul_raw,
                mul_mod=mul_mod,
                is_init=is_init,
            )
        )

    assert result is not None
    logger.debug("fast_modexp(%s,%s,%s)=%s mults=%s", a, x, p, result, mults)
    return result, mults, trace


def fast_modexp(a: int, x: int, p: int) -> tuple[int, int]:
    """Быстрое a^x mod p без трассировки. Возвращает (результат, число умножений)."""
    res, mults, _ = fast_modexp_traced(a, x, p)
    return res, mults


def format_trace_table(a: int, x: int, p: int, trace: list[TraceStep]) -> str:
    """Таблица трассировки в духе примера из lec6.pdf."""
    if not trace:
        return "(трассировка пуста: x = 0 или p = 1)"

    cells: dict[str, list[str]] = {
        "i": [str(s.i) for s in trace],
        "2^i": [str(s.power_of_two) for s in trace],
        f"a^(2^i)  (a={a})": [str(s.a_pow_raw) for s in trace],
        f"a^(2^i) mod {p}": [str(s.a_pow_mod) for s in trace],
        "бит x_i": [str(s.bit) for s in trace],
        "r * a^(2^i)": [
            "init" if s.is_init else ("-" if s.mul_raw is None else str(s.mul_raw))
            for s in trace
        ],
        f"r mod {p}": [
            "-" if (s.bit == 0) else str(s.a_pow_mod if s.is_init else s.mul_mod)
            for s in trace
        ],
    }

    label_w = max(len(label) for label in cells)
    col_w = max(max(len(v) for v in values) for values in cells.values())
    col_w = max(col_w, 3)

    lines: list[str] = []
    sep = "+" + "-" * (label_w + 2) + ("+" + "-" * (col_w + 2)) * len(trace) + "+"
    lines.append(sep)
    for label, values in cells.items():
        row = f"| {label:<{label_w}} |" + "".join(f" {v:>{col_w}} |" for v in values)
        lines.append(row)
        lines.append(sep)
    return "\n".join(lines)


def explain_powers_of_two(x: int) -> str:
    """Разложение x по степеням двойки: 701 -> '512 + 128 + 32 + 16 + 8 + 4 + 1'."""
    if x == 0:
        return "0"
    parts = [str(1 << i) for i in range(bit_length(x)) if (x >> i) & 1]
    parts.reverse()
    return " + ".join(parts)


# --- CLI --------------------------------------------------------------------


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, help="Логи уровня DEBUG.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Быстрое возведение в степень по модулю с трассировкой и счётчиком умножений."""
    configure_logging(verbose)
    ctx.ensure_object(dict)
    logger.debug("CLI инициализирован")


@cli.command("compute")
@click.argument("a", type=int)
@click.argument("x", type=int)
@click.argument("p", type=int)
def cmd_compute(a: int, x: int, p: int) -> None:
    """Посчитать a^x mod p и вывести результат и счётчик умножений."""
    res, mults = fast_modexp(a, x, p)
    click.echo(f"{a}^{x} mod {p} = {res}")
    click.echo(f"Фактически выполнено умножений: {mults}")
    click.echo(f"Длина показателя в битах: {bit_length(x)}, вес Хэмминга: {hamming_weight(x)}")


@cli.command("trace")
@click.argument("a", type=int)
@click.argument("x", type=int)
@click.argument("p", type=int)
def cmd_trace(a: int, x: int, p: int) -> None:
    """Подробная трассировка вычисления a^x mod p (таблица как в lec6.pdf)."""
    res, mults, trace = fast_modexp_traced(a, x, p)
    click.echo(f"Y = {a}^{x} mod {p}")
    click.echo(f"{x} = {explain_powers_of_two(x)}")
    click.echo(f"Длина показателя: {bit_length(x)} бит, вес Хэмминга: {hamming_weight(x)}")
    click.echo("")
    click.echo(format_trace_table(a, x, p, trace))
    click.echo("")
    click.echo(f"Результат: Y = {res}")
    click.echo(f"Фактически выполнено умножений: {mults}")
    n = bit_length(x)
    h = hamming_weight(x)
    click.echo(
        f"Теоретическая оценка для этого x: (n-1) + (HW-1) = ({n}-1) + ({h}-1) = {(n - 1) + (h - 1)}"
    )


@cli.command("compare")
@click.argument("a", type=int)
@click.argument("x", type=int)
@click.argument("p", type=int)
def cmd_compare(a: int, x: int, p: int) -> None:
    """Сравнить быстрый и медленный алгоритмы (медленный пропускается при больших x)."""
    fast_res, fast_mults = fast_modexp(a, x, p)
    click.echo(f"Быстрый:   {a}^{x} mod {p} = {fast_res}, умножений = {fast_mults}")
    if x <= 200_000:
        naive_res, naive_mults = naive_modexp(a, x, p)
        click.echo(f"Медленный: {a}^{x} mod {p} = {naive_res}, умножений = {naive_mults}")
        click.echo(f"Совпадают: {fast_res == naive_res}")
    else:
        click.echo("Медленный пропущен (x слишком большой).")
    builtin = pow(a, x, p)
    click.echo(f"Проверка через builtin pow: {builtin}  ->  совпадает: {fast_res == builtin}")


@cli.command("hamming-demo")
@click.option("--a", "a", type=int, default=5, show_default=True, help="Основание a.")
@click.option("--p", "p", type=int, default=1_000_003, show_default=True, help="Модуль p.")
@click.option("--bits", type=int, default=32, show_default=True, help="Длина показателя x в битах.")
def cmd_hamming_demo(a: int, p: int, bits: int) -> None:
    """Несколько показателей x одинаковой длины с разным весом Хэмминга."""
    if bits < 1 or bits > 64:
        raise click.BadParameter("--bits ожидается в диапазоне 1..64")

    cases: list[tuple[str, int]] = [
        ("min HW (одна 1)", 1 << (bits - 1)),
        ("две 1", (1 << (bits - 1)) | 1),
        ("половина HW", int("10" * (bits // 2) + ("1" if bits % 2 else ""), 2)),
        ("max HW (все 1)", (1 << bits) - 1),
    ]
    click.echo(f"a = {a}, p = {p}, длина показателя = {bits} бит")
    click.echo("")
    header = f"{'случай':<22} | {'x':>20} | {'HW':>4} | {'умножений':>10} | {'результат':>14}"
    click.echo(header)
    click.echo("-" * len(header))
    for label, x in cases:
        res, mults = fast_modexp(a, x, p)
        builtin = pow(a, x, p)
        ok = "ok" if res == builtin else "FAIL"
        click.echo(
            f"{label:<22} | {x:>20} | {hamming_weight(x):>4} | {mults:>10} | {res:>14}  [{ok}]"
        )
    click.echo("")
    click.echo("Вывод: при одинаковой длине показателя число умножений = (n-1) + (HW-1).")


@cli.command("demo")
def cmd_demo() -> None:
    """Готовый сценарий для сдачи: примеры из лекции и проверка веса Хэмминга."""
    bar = "=" * 70

    click.echo(f"\n{bar}\n1. Пример из lec6.pdf: Y = 5^701 mod 11\n{bar}")
    a, x, p = 5, 701, 11
    res, mults, trace = fast_modexp_traced(a, x, p)
    click.echo(f"{x} = {explain_powers_of_two(x)}")
    click.echo(f"Длина показателя: {bit_length(x)} бит, вес Хэмминга: {hamming_weight(x)}")
    click.echo("")
    click.echo(format_trace_table(a, x, p, trace))
    click.echo("")
    click.echo(f"Результат:                       Y = {res}")
    click.echo(f"Фактически выполнено умножений:    {mults}")
    click.echo(f"Проверка через builtin pow(a,x,p): {pow(a, x, p)}  -> совпадает: {res == pow(a, x, p)}")
    click.echo("В лекции для этого примера тоже 15 умножений: 9 квадратирований + 6 «доумножений».")

    click.echo(f"\n{bar}\n2. Второй пример из лекции: Y = 3^800 mod 13\n{bar}")
    a, x, p = 3, 800, 13
    res, mults, trace = fast_modexp_traced(a, x, p)
    click.echo(f"{x} = {explain_powers_of_two(x)}")
    click.echo(f"Длина показателя: {bit_length(x)} бит, вес Хэмминга: {hamming_weight(x)}")
    click.echo("")
    click.echo(format_trace_table(a, x, p, trace))
    click.echo("")
    click.echo(f"Результат: Y = {res} (проверка: {pow(a, x, p)})")
    click.echo(f"Умножений: {mults}")

    click.echo(f"\n{bar}\n3. Сравнение быстрого и медленного на маленьком x\n{bar}")
    a, x, p = 7, 200, 1000
    fr, fm = fast_modexp(a, x, p)
    nr, nm = naive_modexp(a, x, p)
    click.echo(f"a={a}, x={x}, p={p}")
    click.echo(f"  быстрый:   {fr}  за {fm} умножений")
    click.echo(f"  медленный: {nr}  за {nm} умножений")
    click.echo(f"  совпадают: {fr == nr}; ускорение в {nm / max(fm, 1):.1f} раз по числу умножений")

    click.echo(f"\n{bar}\n4. Зависимость числа умножений от веса Хэмминга (32 бита)\n{bar}")
    a, p, bits = 5, 1_000_003, 32
    cases: list[tuple[str, int]] = [
        ("min HW = 1   ", 1 << (bits - 1)),
        ("HW = 2       ", (1 << (bits - 1)) | 1),
        ("HW ~ 16      ", int("10" * (bits // 2), 2)),
        ("max HW = 32  ", (1 << bits) - 1),
    ]
    click.echo(f"a={a}, p={p}, фиксируем длину показателя = {bits} бит")
    click.echo("")
    click.echo(f"{'случай':<14} | {'x':>11} | {'HW':>3} | {'умножений':>10}")
    click.echo("-" * 50)
    for label, x in cases:
        res, mults = fast_modexp(a, x, p)
        assert res == pow(a, x, p)
        click.echo(f"{label:<14} | {x:>11} | {hamming_weight(x):>3} | {mults:>10}")
    click.echo("")
    click.echo("Подтверждение формулы: умножений = (n-1) + (HW-1).")

    click.echo(f"\n{bar}\n5. Большое число (демонстрация эффективности)\n{bar}")
    a, x, p = 7, 2**512 - 1, (1 << 521) - 1
    res, mults = fast_modexp(a, x, p)
    click.echo(f"a={a}")
    click.echo(f"x = 2^512 - 1 (512 бит, HW = 512)")
    click.echo(f"p = 2^521 - 1 (простое Мерсенна M_521)")
    click.echo(f"Получили результат за {mults} умножений (медленный потребовал бы ~2^512).")
    click.echo(f"Проверка через builtin pow совпадает: {res == pow(a, x, p)}")


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        logger.warning("Прервано пользователем")
        sys.exit(130)


if __name__ == "__main__":
    main()
