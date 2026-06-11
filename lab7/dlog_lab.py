from __future__ import annotations

import logging
import math
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


def _validate(a: int, y: int, p: int, n: int | None) -> None:
    if p < 2:
        raise ValueError(f"модуль p должен быть >= 2, получено {p}")
    if a < 1:
        raise ValueError(f"основание a должно быть >= 1, получено {a}")
    if y < 0:
        raise ValueError(f"y должно быть >= 0, получено {y}")
    if n is not None and n < 0:
        raise ValueError(f"граница n должна быть >= 0, получено {n}")


def isqrt_ceil(n: int) -> int:
    """ceil(sqrt(n)) для n >= 0."""
    if n <= 0:
        return 0
    s = math.isqrt(n)
    return s if s * s == n else s + 1


def brute_force_log(
    a: int, y: int, p: int, n: int | None = None
) -> tuple[int | None, int, list[tuple[int, int]]]:
    """Дискретный логарифм перебором: ищем x в [0..n]: a^x ≡ y (mod p).

    Возвращает (x | None, число умножений, [(x_i, a^x_i mod p), ...]).
    """
    _validate(a, y, p, n)
    if n is None:
        n = p - 1
    a %= p
    y %= p

    val = 1 % p
    pairs: list[tuple[int, int]] = [(0, val)]
    if val == y:
        return 0, 0, pairs

    mults = 0
    for x in range(1, n + 1):
        val = (val * a) % p
        mults += 1
        pairs.append((x, val))
        if val == y:
            return x, mults, pairs
    return None, mults, pairs


@dataclass
class BSGSTrace:
    m: int
    k: int
    n: int
    baby: list[tuple[int, int]]
    am: int
    giant: list[tuple[int, int, int | None]]
    found: tuple[int, int, int] | None


def bsgs(
    a: int, y: int, p: int, n: int | None = None
) -> tuple[int | None, int, BSGSTrace]:
    """Метод Шэнкса (baby-step giant-step). m = ceil(sqrt(n)), k подобрано так, что m*k >= n.

    Уравнение a^(j*m - i) ≡ y (mod p) сводится к (a^m)^j ≡ y * a^i (mod p).
    Возвращает (x | None, число умножений, трассировка). По умолчанию n = p - 1.
    """
    _validate(a, y, p, n)
    if n is None:
        n = p - 1
    a %= p
    y %= p

    m = max(1, isqrt_ceil(n))
    k = max(1, (n + m - 1) // m)

    if y == 1 % p:
        return 0, 0, BSGSTrace(m=m, k=k, n=n, baby=[], am=0, giant=[], found=(0, 0, 0))

    mults = 0
    baby_table: dict[int, int] = {}
    baby: list[tuple[int, int]] = []
    r = y
    baby_table.setdefault(r, 0)
    baby.append((0, r))
    for i in range(1, m):
        r = (r * a) % p
        mults += 1
        baby_table.setdefault(r, i)
        baby.append((i, r))

    am = 1 % p
    for _ in range(m):
        am = (am * a) % p
        mults += 1

    giant: list[tuple[int, int, int | None]] = []
    found: tuple[int, int, int] | None = None
    l = 1 % p
    for j in range(1, k + 1):
        l = (l * am) % p
        mults += 1
        mi = baby_table.get(l)
        giant.append((j, l, mi))
        if mi is not None:
            found = (j * m - mi, j, mi)
            break

    trace = BSGSTrace(m=m, k=k, n=n, baby=baby, am=am, giant=giant, found=found)
    logger.debug("BSGS m=%s k=%s am=%s found=%s mults=%s", m, k, am, found, mults)
    return (found[0] if found else None), mults, trace


def _table(headers: list[str], rows: list[list[str]]) -> str:
    cols = list(zip(headers, *rows)) if rows else [(h,) for h in headers]
    widths = [max(len(str(c)) for c in col) for col in cols]
    sep = "+" + "+".join("-" * (w + 2) for w in widths) + "+"
    out = [sep, "| " + " | ".join(f"{h:>{w}}" for h, w in zip(headers, widths)) + " |", sep]
    for row in rows:
        out.append("| " + " | ".join(f"{v:>{w}}" for v, w in zip(row, widths)) + " |")
    if rows:
        out.append(sep)
    return "\n".join(out)


def _trim(rows: list[list[str]], max_rows: int) -> list[list[str]]:
    if len(rows) <= max_rows:
        return rows
    head = rows[: max_rows - 3]
    tail = rows[-3:]
    return head + [["..."] * len(rows[0])] + tail


def format_brute_trace(p: int, pairs: list[tuple[int, int]], max_rows: int = 30) -> str:
    rows = _trim([[str(x), str(v)] for x, v in pairs], max_rows)
    return _table(["x", f"a^x mod {p}"], rows)


def format_bsgs_trace(a: int, p: int, t: BSGSTrace, max_rows: int = 30) -> str:
    parts = [f"n = {t.n}, m = {t.m}, k = {t.k}  (m*k = {t.m * t.k} >= n)"]
    if t.found == (0, 0, 0) and not t.baby:
        parts.append("y ≡ 1 (mod p) -> x = 0 (без перебора)")
        return "\n".join(parts)

    parts.append("")
    parts.append(f"Шаг младенца: r_i = y * a^i mod p, i = 0..{t.m - 1}")
    parts.append(_table(["i", "r_i"], _trim([[str(i), str(r)] for i, r in t.baby], max_rows)))

    parts.append("")
    parts.append(f"a^m mod p = {a}^{t.m} mod {p} = {t.am}")

    parts.append("")
    parts.append(f"Шаг великана: l_j = (a^m)^j mod p, j = 1..{t.k}")
    grows = [[str(j), str(l), "-" if mi is None else f"i={mi}"] for j, l, mi in t.giant]
    parts.append(_table(["j", "l_j", "совпадение"], _trim(grows, max_rows)))

    if t.found is not None:
        x, j, i = t.found
        parts.append("")
        parts.append(f"Найдено: i = {i}, j = {j}  =>  x = j*m - i = {j}*{t.m} - {i} = {x}")
    return "\n".join(parts)


# --- CLI --------------------------------------------------------------------


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, help="Логи уровня DEBUG.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Дискретный логарифм: полный перебор и метод Шэнкса (BSGS)."""
    configure_logging(verbose)
    ctx.ensure_object(dict)
    logger.debug("CLI инициализирован")


@cli.command("brute")
@click.argument("a", type=int)
@click.argument("y", type=int)
@click.argument("p", type=int)
@click.option("--n", type=int, default=None, help="Верхняя граница для x. По умолчанию p-1.")
@click.option("--max-rows", type=int, default=30, show_default=True, help="Сколько строк трассировки печатать.")
def cmd_brute(a: int, y: int, p: int, n: int | None, max_rows: int) -> None:
    """Дискретный логарифм полным перебором."""
    x, mults, pairs = brute_force_log(a, y, p, n)
    bound = n if n is not None else p - 1
    click.echo(f"Полный перебор: ищем x: {a}^x ≡ {y} (mod {p}), n = {bound}")
    click.echo("")
    click.echo(format_brute_trace(p, pairs, max_rows=max_rows))
    click.echo("")
    if x is None:
        click.echo(f"x не найден на интервале [0..{bound}]")
    else:
        click.echo(f"Найдено: x = {x}")
        click.echo(f"Проверка: pow({a},{x},{p}) = {pow(a, x, p)}  -> совпадает: {pow(a, x, p) == y % p}")
    click.echo(f"Фактически выполнено умножений: {mults}")


@cli.command("bsgs")
@click.argument("a", type=int)
@click.argument("y", type=int)
@click.argument("p", type=int)
@click.option("--n", type=int, default=None, help="Верхняя граница для x. По умолчанию p-1.")
@click.option("--max-rows", type=int, default=30, show_default=True, help="Сколько строк таблиц печатать.")
def cmd_bsgs(a: int, y: int, p: int, n: int | None, max_rows: int) -> None:
    """Метод Шэнкса с подробной трассировкой."""
    x, mults, trace = bsgs(a, y, p, n)
    click.echo(f"BSGS: ищем x: {a}^x ≡ {y} (mod {p})")
    click.echo("")
    click.echo(format_bsgs_trace(a, p, trace, max_rows=max_rows))
    click.echo("")
    if x is None:
        click.echo("x не найден (y, по-видимому, не лежит в группе, порождённой a)")
    else:
        click.echo(f"Результат: x = {x}")
        click.echo(f"Проверка: pow({a},{x},{p}) = {pow(a, x, p)}  -> совпадает: {pow(a, x, p) == y % p}")
    click.echo(f"Фактически выполнено умножений: {mults}")


@cli.command("compare")
@click.argument("a", type=int)
@click.argument("y", type=int)
@click.argument("p", type=int)
@click.option("--n", type=int, default=None, help="Верхняя граница для x. По умолчанию p-1.")
@click.option("--max-brute", type=int, default=2_000_000, show_default=True, help="Не запускать перебор при n больше этого.")
def cmd_compare(a: int, y: int, p: int, n: int | None, max_brute: int) -> None:
    """Сравнить число умножений в полном переборе и BSGS."""
    bound = n if n is not None else p - 1
    click.echo(f"a = {a}, y = {y}, p = {p}, n = {bound}")
    click.echo("")
    sx, sm, st = bsgs(a, y, p, n)
    click.echo(f"BSGS:    x = {sx}, умножений = {sm}  (m = {st.m}, k = {st.k})")
    if bound <= max_brute:
        bx, bm, _ = brute_force_log(a, y, p, n)
        click.echo(f"Перебор: x = {bx}, умножений = {bm}")
        if bx is not None and sx is not None:
            click.echo(f"Совпадает y: {pow(a, sx, p) == pow(a, bx, p) == y % p}")
            click.echo(f"Ускорение по умножениям: ~{bm / max(sm, 1):.1f} раз")
    else:
        click.echo(f"Перебор пропущен (n = {bound} > {max_brute}).")
    click.echo(f"Теория: перебор ~ n, BSGS ~ 2*sqrt(n) = {2 * isqrt_ceil(bound)}")


@cli.command("demo")
def cmd_demo() -> None:
    """Готовый сценарий: малый пример с трассировкой и сравнение на большом p."""
    bar = "=" * 70

    click.echo(f"\n{bar}\n1. Малый пример: 2^x ≡ 22 (mod 29)\n{bar}")
    a, y, p = 2, 22, 29
    sx, sm, st = bsgs(a, y, p)
    click.echo("BSGS с подробной трассировкой:")
    click.echo("")
    click.echo(format_bsgs_trace(a, p, st))
    click.echo("")
    click.echo(f"x = {sx}, умножений = {sm}")
    bx, bm, bp = brute_force_log(a, y, p)
    click.echo("")
    click.echo("Полный перебор:")
    click.echo(format_brute_trace(p, bp))
    click.echo(f"x = {bx}, умножений = {bm}")
    click.echo(f"Проверка: оба метода дают a^x ≡ y: {pow(a, sx, p) == pow(a, bx, p) == y}")

    click.echo(f"\n{bar}\n2. Сравнение на большом p\n{bar}")
    p, a, secret = 100003, 2, 54321
    y = pow(a, secret, p)
    click.echo(f"a = {a}, p = {p}, секретный x = {secret}, y = {y}")
    bx, bm, _ = brute_force_log(a, y, p)
    sx, sm, st = bsgs(a, y, p)
    click.echo(f"Перебор: x = {bx}, умножений = {bm}")
    click.echo(f"BSGS:    x = {sx}, умножений = {sm}  (m = {st.m}, k = {st.k})")
    click.echo(f"Совпадает y: {pow(a, sx, p) == pow(a, bx, p) == y}")
    click.echo(f"Ускорение BSGS: ~{bm / max(sm, 1):.1f} раз")
    click.echo(f"Теория: 2*sqrt(n) ≈ {2 * isqrt_ceil(p - 1)}")

    click.echo(f"\n{bar}\n3. Зависимость от величины искомого x\n{bar}")
    p, a = 100003, 2
    click.echo(f"a = {a}, p = {p}, меняем x:")
    click.echo("")
    click.echo(f"{'x':>6} | {'перебор':>10} | {'BSGS':>6}")
    click.echo("-" * 32)
    for sx in (1, 100, 10_000, 50_000, 99_999):
        sy = pow(a, sx, p)
        _, bm, _ = brute_force_log(a, sy, p)
        _, sm, _ = bsgs(a, sy, p)
        click.echo(f"{sx:>6} | {bm:>10} | {sm:>6}")
    click.echo("")
    click.echo("Перебор зависит от x; у BSGS число умножений почти не зависит от x")
    click.echo("и определяется только размером p (порядка sqrt(p)).")


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        logger.warning("Прервано пользователем")
        sys.exit(130)


if __name__ == "__main__":
    main()
