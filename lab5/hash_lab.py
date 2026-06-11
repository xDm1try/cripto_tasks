from __future__ import annotations

import hashlib
import logging
import math
import sys
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


def sha256_digest(data: bytes) -> bytes:
    """Полный дайджест SHA-256 (криптографическая хеш-функция из стандартной библиотеки)."""
    return hashlib.sha256(data).digest()


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def truncated_hash_bits(data: bytes, n_bits: int) -> int:
    """
    Первые n_bits бит дайджеста SHA-256 как целое (старшие биты идут первыми).

    1 <= n_bits <= 256.
    """
    if not (1 <= n_bits <= 256):
        raise ValueError(f"n_bits должен быть от 1 до 256, получено {n_bits}")
    h = int.from_bytes(sha256_digest(data), "big")
    return h >> (256 - n_bits)


def expected_birthday_trials(n_bits: int) -> float:
    """Ожидаемое число случайных значений до первой коллизии в пространстве размера 2^n: ~ √(π·2^n / 2)."""
    if n_bits <= 0:
        return 0.0
    m = 2.0**n_bits
    return math.sqrt(math.pi * m / 2.0)


def _message_counter_utf8(i: int) -> bytes:
    return str(i).encode("utf-8")


def find_truncated_collision(
    n_bits: int,
    max_trials: int = 5_000_000,
    message_fn=_message_counter_utf8,
) -> tuple[bytes, bytes, int, int]:
    """
    Ищет два различных сообщения с одинаковыми первыми n_bits битами SHA-256.

    Возвращает (msg_a, msg_b, общее_число_проверенных_сообщений, усечённое_значение).
    """
    if not (1 <= n_bits <= 256):
        raise ValueError(f"n_bits вне диапазона 1…256: {n_bits}")
    seen: dict[int, bytes] = {}
    for i in range(max_trials):
        msg = message_fn(i)
        t = truncated_hash_bits(msg, n_bits)
        prev = seen.get(t)
        if prev is not None and prev != msg:
            logger.debug("коллизия на шаге i=%s prefix=%s", i, t)
            return prev, msg, i + 1, t
        seen[t] = msg
    raise RuntimeError(
        f"Коллизия за {max_trials} попыток не найдена (n_bits={n_bits}); увеличьте max_trials или уменьшите n_bits."
    )


def verify_truncated_collision(msg_a: bytes, msg_b: bytes, n_bits: int) -> bool:
    if msg_a == msg_b:
        return False
    return truncated_hash_bits(msg_a, n_bits) == truncated_hash_bits(msg_b, n_bits)


# --- CLI --------------------------------------------------------------------


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, help="Логи уровня DEBUG.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """SHA-256 (hashlib) и парадокс дней рождения на усечённом хеше."""
    configure_logging(verbose)
    ctx.ensure_object(dict)
    logger.debug("CLI инициализирован")


@cli.command("hash-hex")
@click.argument("text", required=False, default="")
@click.option(
    "--file",
    "path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Хешировать содержимое файла вместо строки text.",
)
def cmd_hash_hex(text: str, path: Path | None) -> None:
    """Полный SHA-256 в hex (строка UTF-8 или файл)."""
    data = path.read_bytes() if path is not None else text.encode("utf-8")
    click.echo(sha256_hex(data))


@cli.command("truncate")
@click.argument("text")
@click.option("--bits", type=int, required=True, help="Сколько старших бит дайджеста показать (1…256).")
def cmd_truncate(text: str, bits: int) -> None:
    """Первые --bits бит хеша как целое и в hex (минимальная ширина ceil(bits/4) nibbles)."""
    t = truncated_hash_bits(text.encode("utf-8"), bits)
    width = (bits + 3) // 4
    click.echo(f"truncated ({bits} бит, int): {t}")
    click.echo(f"truncated ({bits} бит, hex): {t:0{width}x}")


@cli.command("birthday-search")
@click.option("--bits", type=int, required=True, help="Длина усечённого префикса в битах (для демо обычно 12…22).")
@click.option("--max-trials", type=int, default=2_000_000, show_default=True)
def cmd_birthday_search(bits: int, max_trials: int) -> None:
    """Найти коллизию среди сообщений 0, 1, 2, … (строки в UTF-8)."""
    exp = expected_birthday_trials(bits)
    buckets = 2**bits
    click.echo(f"n_bits={bits}")
    click.echo(f"Размер пространства префиксов: 2^{bits} = {buckets}")
    click.echo(f"Ожидаемый порядок до первой коллизии: около sqrt(2^{bits}) ~= {exp:.1f} сообщений")
    click.echo("Идея: это как дни рождения - людей намного меньше 365, но совпадение дня уже вероятно.")
    a, b, n, val = find_truncated_collision(bits, max_trials=max_trials)
    click.echo(f"Найдено за n={n} сообщений.")
    click.echo(f"Сообщение A (repr): {a!r}")
    click.echo(f"Сообщение B (repr): {b!r}")
    click.echo(f"Общий префикс ({bits} бит, int): {val}")
    click.echo(f"SHA256(A) hex: {sha256_hex(a)}")
    click.echo(f"SHA256(B) hex: {sha256_hex(b)}")


@cli.command("demo")
def cmd_demo() -> None:
    """Короткий сценарий: хеш, усечение, поиск коллизии на малых n_bits."""
    bar = "=" * 58
    s = b"birthday"
    click.echo(f"\n{bar}\n1. SHA-256 (полный hex)\n{bar}")
    click.echo(f"SHA256({s!r}) =\n{sha256_hex(s)}")

    nb = 18
    click.echo(f"\n{bar}\n2. Первые {nb} бит как целое\n{bar}")
    tv = truncated_hash_bits(s, nb)
    click.echo(f"truncated_{nb}_bits = {tv} (hex width {(nb + 3) // 4}: {tv:0{(nb + 3) // 4}x})")

    click.echo(f"\n{bar}\n3. Коллизия усечённого хеша ({nb} бит)\n{bar}")
    exp = expected_birthday_trials(nb)
    click.echo(f"Префиксов всего: 2^{nb} = {2**nb}")
    click.echo(f"По парадоксу дней рождения коллизия обычно появляется уже примерно через ~{exp:.0f} попыток.")
    click.echo("Причина: число пар растет как n^2/2, поэтому совпадение возникает сильно раньше, чем перебор всего пространства.")
    a, b, n, val = find_truncated_collision(nb, max_trials=500_000)
    click.echo(f"Получено за {n} сообщений; префикс (int) = {val}")
    click.echo(f"A = {a!r}\nB = {b!r}")
    click.echo(f"Проверка: совпадают первые {nb} бит: {verify_truncated_collision(a, b, nb)}")


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        logger.warning("Прервано пользователем")
        sys.exit(130)


if __name__ == "__main__":
    main()
