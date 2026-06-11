from __future__ import annotations

import logging
import math
import random
import sys
from collections import Counter
from pathlib import Path

import click

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


def byte_frequencies(data: bytes) -> Counter[int]:
    return Counter(data)


def frequencies_from_file(path: Path) -> Counter[int]:
    raw = path.read_bytes()
    logger.debug("read %s bytes from %s", len(raw), path)
    return byte_frequencies(raw)


def entropy_from_frequencies(counts: Counter[int]) -> float:
    """
    Энтропия Шеннона в битах на символ: H = -sum_i p_i log2(p_i).

    Пустой вход: 0.0 (неопределённость отсутствует).
    """
    total = sum(counts.values())
    if total == 0:
        return 0.0
    h = 0.0
    for c in counts.values():
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log2(p)
    return h


def theoretical_max_entropy(alphabet_size: int) -> float:
    if alphabet_size <= 1:
        return 0.0
    return math.log2(alphabet_size)


def write_sample(path: Path, data: bytes) -> None:
    path.write_bytes(data)
    logger.debug("wrote %s bytes -> %s", len(data), path)


def generate_constant_byte(length: int, b: int = ord("A")) -> bytes:
    return bytes([b & 0xFF]) * length


def generate_coin_ascii(length: int, rng: random.Random) -> bytes:
    """Случайные символы '0' и '1' (алфавит из 2 символов)."""
    return bytes(rng.choice((ord("0"), ord("1"))) for _ in range(length))


def generate_uniform_bytes(length: int, rng: random.Random) -> bytes:
    """Случайные байты 0…255 (равномерно)."""
    return bytes(rng.randint(0, 255) for _ in range(length))


def generate_two_symbols_equal_freq(length: int, rng: random.Random) -> bytes:
    a, b = ord("x"), ord("y")
    half = length // 2
    rest = length - half
    left = bytes([a]) * half + bytes([b]) * rest
    seq = bytearray(left)
    rng.shuffle(seq)
    return bytes(seq)


class SampleGenerator:
    """Набор тестовых файлов для сравнения энтропий."""

    def __init__(self, out_dir: Path, rng: random.Random | None = None) -> None:
        self._out = out_dir
        self._rng = rng or random.Random()

    def write_all(self, size: int) -> list[tuple[str, Path, Counter[int], float]]:
        self._out.mkdir(parents=True, exist_ok=True)
        rows: list[tuple[str, Path, Counter[int], float]] = []

        def add(label: str, rel: str, data: bytes) -> None:
            p = self._out / rel
            write_sample(p, data)
            cnt = byte_frequencies(data)
            h = entropy_from_frequencies(cnt)
            rows.append((label, p, cnt, h))

        add("Один повторяющийся символ", "sample_const.bin", generate_constant_byte(size))
        add("Случайные '0'/'1'", "sample_coin.txt", generate_coin_ascii(size, self._rng))
        add("Случайные байты 0…255", "sample_uniform255.bin", generate_uniform_bytes(size, self._rng))
        add("Ровно два символа, 50/50", "sample_two_equal.bin", generate_two_symbols_equal_freq(size, self._rng))
        # Дополнительно: ASCII-печатные, смешанный текст
        text = ("Hello entropy " * (max(1, size // 15)))[:size].encode("utf-8", errors="ignore")
        if len(text) < size:
            text += b" " * (size - len(text))
        add("Повторяющийся текст (узкий алфавит)", "sample_text.txt", text[:size])

        return rows


def print_frequency_report(counts: Counter[int], limit: int = 32) -> None:
    """Печать частот (первые limit по убыванию частоты)."""
    total = sum(counts.values())
    click.echo(f"Всего символов (байтов): {total}")
    if total == 0:
        click.echo("(пустой файл)")
        return
    items = counts.most_common(limit)
    click.echo(f"Топ-{len(items)} по частоте (байт как число / как символ если printable):")
    for b, n in items:
        ch = chr(b) if 32 <= b < 127 else "."
        click.echo(f"  {b:3d} 0x{b:02x} '{ch}'  ->  {n}  ({100.0 * n / total:.4f}%)")


def print_entropy_row(label: str, h: float, counts: Counter[int]) -> None:
    m = len(counts)
    h_max = theoretical_max_entropy(m)
    click.echo(f"{label}")
    click.echo(f"  |алфавит| = {m},  H = {h:.6f} бит/символ,  log2(m) = {h_max:.6f}")


# --- CLI --------------------------------------------------------------------


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, help="Логи уровня DEBUG.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """Частоты символов и энтропия файла (байтовая модель)."""
    configure_logging(verbose)
    ctx.ensure_object(dict)
    logger.debug("CLI инициализирован")


@cli.command("freq")
@click.argument("path", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--top", type=int, default=32, show_default=True, help="Сколько частот показать.")
def cmd_freq(path: Path, top: int) -> None:
    """Задача 1: частоты байтов в файле."""
    counts = frequencies_from_file(path)
    click.echo(f"Файл: {path.resolve()}")
    print_frequency_report(counts, limit=top)


@cli.command("entropy")
@click.argument("path", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.option("--top", type=int, default=16, show_default=True)
def cmd_entropy(path: Path, top: int) -> None:
    """Задача 2: энтропия по вычисленным частотам."""
    counts = frequencies_from_file(path)
    h = entropy_from_frequencies(counts)
    click.echo(f"Файл: {path.resolve()}")
    print_frequency_report(counts, limit=top)
    m = len(counts)
    click.echo(f"\nЭнтропия H = {h:.8f} бит/символ")
    click.echo(f"Размер алфавита (уникальных байтов): m = {m}")
    click.echo(f"log2(m) при равномерном распределении: {theoretical_max_entropy(m):.8f}")


@cli.command("demo")
@click.option("-n", "--size", type=int, default=200_000, show_default=True, help="Длина каждого образца в байтах.")
@click.option("--seed", type=int, default=42, show_default=True, help="Seed ГПСЧ для воспроизводимости.")
def cmd_demo(size: int, seed: int) -> None:
    """Задача 3: сгенерировать образцы и сопоставить энтропии."""
    out_dir = Path("samples")
    rng = random.Random(seed)
    gen = SampleGenerator(out_dir, rng=rng)
    rows = gen.write_all(size)

    bar = "=" * 62
    click.echo(f"\n{bar}\nСгенерированные файлы (n = {size}, seed = {seed})\n{bar}\n")
    for label, p, _cnt, _h in rows:
        click.echo(f"{label}")
        click.echo(f"  файл: {p.resolve()}\n")

    click.echo(bar)
    click.echo(
        "Ожидание: для почти одного символа H → 0; "
        "для равномерных случайных 0/1 H → 1 = log2(2); "
        "для равномерных байтов 0…255 H → 8 = log2(256).\n"
        f"(При конечной выборке значения слегка отклоняются от предела.)\n{bar}\n"
    )


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        logger.warning("Прервано пользователем")
        sys.exit(130)


if __name__ == "__main__":
    main()
