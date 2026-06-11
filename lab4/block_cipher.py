from __future__ import annotations

import logging
import secrets
import struct
import sys
from pathlib import Path

import click

logger = logging.getLogger(__name__)

_BLOCK_SIZE = 8
_KEY_SIZE = 16
_DELTA = 0x9E3779B9
_DEFAULT_ROUNDS = 64


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


class XTEABlockCipher:
    """XTEA (eXtended TEA): блок 64 бита, ключ 128 бит, итеративное смешивание (Feistel-подобно)."""

    def __init__(self, key: bytes, rounds: int = _DEFAULT_ROUNDS) -> None:
        if len(key) != _KEY_SIZE:
            raise ValueError(f"Ключ XTEA должен быть ровно {_KEY_SIZE} байт, получено {len(key)}")
        if rounds <= 0:
            raise ValueError("Число раундов должно быть > 0")
        self._key = struct.unpack("<4I", key)
        self._rounds = rounds
        logger.debug("XTEA: rounds=%s", rounds)

    def encrypt_block(self, block: bytes) -> bytes:
        if len(block) != _BLOCK_SIZE:
            raise ValueError(f"Блок должен быть {_BLOCK_SIZE} байт")
        v0, v1 = struct.unpack("<II", block)
        key = self._key
        s = 0
        for _ in range(self._rounds):
            v0 = (v0 + ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key[s & 3]))) & 0xFFFFFFFF
            s = (s + _DELTA) & 0xFFFFFFFF
            v1 = (v1 + ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key[(s >> 11) & 3]))) & 0xFFFFFFFF
        return struct.pack("<II", v0, v1)

    def decrypt_block(self, block: bytes) -> bytes:
        if len(block) != _BLOCK_SIZE:
            raise ValueError(f"Блок должен быть {_BLOCK_SIZE} байт")
        v0, v1 = struct.unpack("<II", block)
        key = self._key
        s = (_DELTA * self._rounds) & 0xFFFFFFFF
        for _ in range(self._rounds):
            v1 = (v1 - ((((v0 << 4) ^ (v0 >> 5)) + v0) ^ (s + key[(s >> 11) & 3]))) & 0xFFFFFFFF
            s = (s - _DELTA) & 0xFFFFFFFF
            v0 = (v0 - ((((v1 << 4) ^ (v1 >> 5)) + v1) ^ (s + key[s & 3]))) & 0xFFFFFFFF
        return struct.pack("<II", v0, v1)


def _pkcs7_pad(data: bytes, block_size: int = _BLOCK_SIZE) -> bytes:
    n = block_size - (len(data) % block_size)
    return data + bytes([n]) * n


def _pkcs7_unpad(data: bytes, block_size: int = _BLOCK_SIZE) -> bytes:
    if not data or len(data) % block_size != 0:
        raise ValueError("Некорректная длина данных для снятия PKCS#7")
    n = data[-1]
    if n < 1 or n > block_size or data[-n:] != bytes([n]) * n:
        raise ValueError("Некорректное заполнение PKCS#7 (ключ или файл повреждены)")
    return data[:-n]


def _xor_block(a: bytes, b: bytes) -> bytes:
    return bytes(x ^ y for x, y in zip(a, b))


class CBCFileCipher:
    """CBC + PKCS#7: в начале файла — IV (один блок)."""

    def __init__(self, block_cipher: XTEABlockCipher) -> None:
        self._cipher = block_cipher

    def encrypt_bytes(self, plaintext: bytes, iv: bytes | None = None) -> bytes:
        if iv is None:
            iv = secrets.token_bytes(_BLOCK_SIZE)
        if len(iv) != _BLOCK_SIZE:
            raise ValueError("IV должен быть длиной один блок (8 байт)")
        body = _pkcs7_pad(plaintext)
        out = bytearray(iv)
        prev = iv
        for i in range(0, len(body), _BLOCK_SIZE):
            blk = body[i : i + _BLOCK_SIZE]
            x = _xor_block(blk, prev)
            c = self._cipher.encrypt_block(x)
            out.extend(c)
            prev = c
        logger.debug("CBC encrypt: plain=%s out=%s", len(plaintext), len(out))
        return bytes(out)

    def decrypt_bytes(self, blob: bytes) -> bytes:
        if len(blob) < _BLOCK_SIZE * 2 or len(blob) % _BLOCK_SIZE != 0:
            raise ValueError("Файл слишком короткий или длина не кратна блоку")
        iv = blob[:_BLOCK_SIZE]
        ct = blob[_BLOCK_SIZE:]
        prev = iv
        plain = bytearray()
        for i in range(0, len(ct), _BLOCK_SIZE):
            c = ct[i : i + _BLOCK_SIZE]
            p = _xor_block(self._cipher.decrypt_block(c), prev)
            plain.extend(p)
            prev = c
        result = _pkcs7_unpad(bytes(plain))
        logger.debug("CBC decrypt: blob=%s plain=%s", len(blob), len(result))
        return result

    def encrypt_file(self, input_path: Path, output_path: Path) -> None:
        data = input_path.read_bytes()
        output_path.write_bytes(self.encrypt_bytes(data))

    def decrypt_file(self, input_path: Path, output_path: Path) -> None:
        blob = input_path.read_bytes()
        output_path.write_bytes(self.decrypt_bytes(blob))


def prepare_samples(samples_dir: Path) -> tuple[Path, Path]:
    """Создать samples/plain.txt и samples/key.bin (ключ 16 байт для XTEA)."""
    samples_dir.mkdir(parents=True, exist_ok=True)
    plain_path = samples_dir / "plain.txt"
    key_path = samples_dir / "key.bin"
    plain_path.write_text("Hello, XTEA + CBC file encryption demo.\n", encoding="utf-8")
    key_path.write_bytes(bytes(range(_KEY_SIZE)))
    return plain_path, key_path


def load_key_16(path_or_hex: Path | None, key_hex: str | None) -> bytes:
    """16 байт ключа: либо --key-file (ровно 16 байт), либо --key-hex (32 шестнадцатеричных символа)."""
    if key_hex is not None:
        h = key_hex.strip().lower().replace(" ", "")
        if len(h) != 32:
            raise click.BadParameter("--key-hex: нужно ровно 32 hex-символа (128 бит)")
        try:
            return bytes.fromhex(h)
        except ValueError as e:
            raise click.BadParameter(f"Некорректный hex: {e}") from e
    if path_or_hex is None:
        raise click.UsageError("Укажите --key-file или --key-hex")
    p = Path(path_or_hex)
    raw = p.read_bytes()
    if len(raw) != _KEY_SIZE:
        raise click.BadParameter(f"Файл ключа: ожидается {_KEY_SIZE} байт, получено {len(raw)}")
    return raw


# --- CLI --------------------------------------------------------------------

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, help="Логи уровня DEBUG.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """XTEA (блочный шифр) в режиме CBC: шифрование и расшифрование файлов."""
    configure_logging(verbose)
    ctx.ensure_object(dict)
    logger.debug("CLI инициализирован")


@cli.command("encrypt")
@click.argument("plaintext", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("ciphertext", type=click.Path(path_type=Path))
@click.option(
    "--key-file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help=f"Файл ключа, ровно {_KEY_SIZE} байт.",
)
@click.option("--key-hex", default=None, help="Ключ 128 бит в hex (32 символа).")
@click.option("--rounds", type=int, default=_DEFAULT_ROUNDS, show_default=True, help="Число раундов XTEA.")
def cmd_encrypt(
    plaintext: Path,
    ciphertext: Path,
    key_file: Path | None,
    key_hex: str | None,
    rounds: int,
) -> None:
    """Зашифровать файл (в начале шифртекста — IV, далее CBC + PKCS#7)."""
    key = load_key_16(key_file, key_hex)
    cipher = XTEABlockCipher(key, rounds=rounds)
    cbc = CBCFileCipher(cipher)
    ciphertext.parent.mkdir(parents=True, exist_ok=True)
    cbc.encrypt_file(plaintext, ciphertext)
    click.echo(f"Шифртекст: {ciphertext}")


@cli.command("decrypt")
@click.argument("ciphertext", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("plaintext", type=click.Path(path_type=Path))
@click.option(
    "--key-file",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help=f"Тот же файл ключа ({_KEY_SIZE} байт).",
)
@click.option("--key-hex", default=None, help="Тот же ключ в hex.")
@click.option("--rounds", type=int, default=_DEFAULT_ROUNDS, show_default=True)
def cmd_decrypt(
    ciphertext: Path,
    plaintext: Path,
    key_file: Path | None,
    key_hex: str | None,
    rounds: int,
) -> None:
    """Расшифровать файл."""
    key = load_key_16(key_file, key_hex)
    cipher = XTEABlockCipher(key, rounds=rounds)
    cbc = CBCFileCipher(cipher)
    plaintext.parent.mkdir(parents=True, exist_ok=True)
    cbc.decrypt_file(ciphertext, plaintext)
    click.echo(f"Открытый текст: {plaintext}")


@cli.command("prepare-samples")
@click.option(
    "--dir",
    "samples_dir",
    type=click.Path(path_type=Path),
    default="samples",
    show_default=True,
    help="Каталог с демонстрационными файлами.",
)
def cmd_prepare_samples(samples_dir: Path) -> None:
    """Подготовить samples/plain.txt и samples/key.bin для демо."""
    plain_path, key_path = prepare_samples(samples_dir)
    click.echo(f"Открытый текст: {plain_path}")
    click.echo(f"Ключ: {key_path} ({key_path.stat().st_size} байт)")


@cli.command("demo")
@click.option(
    "--dir",
    "work_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Каталог для демо-файлов (по умолчанию ./samples).",
)
def cmd_demo(work_dir: Path | None) -> None:
    """Краткий сценарий: один блок XTEA + файл CBC."""
    base = Path.cwd() / "samples" if work_dir is None else work_dir
    base.mkdir(parents=True, exist_ok=True)
    key = bytes(range(16))  # демо-ключ
    bar = "=" * 58
    xc = XTEABlockCipher(key)
    blk = b"abcdefgh"
    enc = xc.encrypt_block(blk)
    dec = xc.decrypt_block(enc)
    print(f"\n{bar}\n1. XTEA: один блок (8 байт)\n{bar}")
    print(f"Блок (plain):  {blk!r}")
    print(f"После encrypt: {enc.hex()}")
    print(f"После decrypt: {dec!r}")

    plain_path = base / "plain.txt"
    key_path = base / "key.bin"
    cipher_path = base / "cipher.bin"
    back_path = base / "restored.txt"
    prepare_samples(base)
    key = key_path.read_bytes()
    xc = XTEABlockCipher(key)
    CBCFileCipher(xc).encrypt_file(plain_path, cipher_path)
    CBCFileCipher(xc).decrypt_file(cipher_path, back_path)
    print(f"\n{bar}\n2. Файл через CBC\n{bar}")
    print(f"Записано: {plain_path}")
    print(f"Шифртекст: {cipher_path} ({cipher_path.stat().st_size} байт)")
    print(f"Восстановлено: {back_path.read_text(encoding='utf-8')!r}")


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        logger.warning("Прервано пользователем")
        sys.exit(130)


if __name__ == "__main__":
    main()
