from __future__ import annotations

import hashlib
import logging
import secrets
import sys
from pathlib import Path
from typing import Iterator

import click
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms

logger = logging.getLogger(__name__)


def configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(levelname)s %(name)s: %(message)s",
        force=True,
    )


class LinearCongruentialGenerator:
    """Линейный конгруэнтный генератор."""

    _A = 1664525
    _C = 1013904223
    _M = 2**32

    def __init__(self, seed: int) -> None:
        self._state = seed % self._M
        logger.debug("LCG seed=%s", self._state)

    def next_u32(self) -> int:
        self._state = (self._A * self._state + self._C) % self._M
        return self._state

    def bytes_stream(self) -> Iterator[int]:
        while True:
            yield self.next_u32() & 0xFF


class KeyFileGenerator:
    @staticmethod
    def write_lcg(path: Path, nbytes: int, seed: int) -> None:
        lcg = LinearCongruentialGenerator(seed)
        gen = lcg.bytes_stream()
        buf = bytearray(next(gen) for _ in range(nbytes))
        path.write_bytes(buf)
        logger.debug("LCG: записано %s байт в %s", nbytes, path)

    @staticmethod
    def write_secrets(path: Path, nbytes: int) -> None:
        path.write_bytes(secrets.token_bytes(nbytes))
        logger.debug("secrets: записано %s байт в %s", nbytes, path)


class VernamCipher:

    @staticmethod
    def xor_files(plaintext_path: Path, key_path: Path, output_path: Path) -> None:
        plain = plaintext_path.read_bytes()
        key = key_path.read_bytes()
        if len(key) < len(plain):
            raise ValueError(
                f"Ключ короче открытого текста: key={len(key)} < plain={len(plain)}"
            )
        out = bytes(p ^ k for p, k in zip(plain, key))
        output_path.write_bytes(out)
        logger.debug("Vernam: plain=%s key_used=%s out=%s", len(plain), len(plain), len(out))

    @staticmethod
    def encrypt_file(plaintext_path: Path, key_path: Path, ciphertext_path: Path) -> None:
        VernamCipher.xor_files(plaintext_path, key_path, ciphertext_path)

    @staticmethod
    def decrypt_file(ciphertext_path: Path, key_path: Path, plaintext_path: Path) -> None:
        VernamCipher.xor_files(ciphertext_path, key_path, plaintext_path)


def chacha20_key_from_keyfile_material(material: bytes) -> bytes:
    if not material:
        raise ValueError("Файл ключа для ChaCha20 не может быть пустым")
    return hashlib.sha256(material).digest()


class ChaCha20FileCipher:
    NONCE_LEN = 16

    def __init__(self, key32: bytes) -> None:
        if len(key32) != 32:
            raise ValueError("Внутренний ключ ChaCha20 должен быть ровно 32 байта")
        self._key = key32
        logger.debug("ChaCha20: ключ готов (32 байта)")

    @classmethod
    def from_key_file(cls, key_file: Path) -> ChaCha20FileCipher:
        return cls(chacha20_key_from_keyfile_material(key_file.read_bytes()))

    def encrypt_file(self, input_path: Path, output_path: Path, chunk: int = 64 * 1024) -> None:
        nonce = secrets.token_bytes(self.NONCE_LEN)
        algorithm = algorithms.ChaCha20(self._key, nonce)
        encryptor = Cipher(algorithm, mode=None).encryptor()
        with input_path.open("rb") as fin, output_path.open("wb") as fout:
            fout.write(nonce)
            while True:
                block = fin.read(chunk)
                if not block:
                    break
                fout.write(encryptor.update(block))
            fout.write(encryptor.finalize())

    def decrypt_file(self, input_path: Path, output_path: Path, chunk: int = 64 * 1024) -> None:
        with input_path.open("rb") as fin, output_path.open("wb") as fout:
            nonce = fin.read(self.NONCE_LEN)
            if len(nonce) != self.NONCE_LEN:
                raise ValueError("Некорректный файл: нет 16-байтового nonce в начале")
            algorithm = algorithms.ChaCha20(self._key, nonce)
            decryptor = Cipher(algorithm, mode=None).decryptor()
            while True:
                block = fin.read(chunk)
                if not block:
                    break
                fout.write(decryptor.update(block))
            fout.write(decryptor.finalize())


class SubmissionDemo:
    def run(self, work: Path) -> None:
        work.mkdir(parents=True, exist_ok=True)
        plain_path = work / "demo_plain.txt"
        key_path = work / "demo_key.bin"
        cipher_path = work / "demo_vernam.bin"
        recovered_path = work / "demo_recovered.txt"
        chacha_out = work / "demo_chacha.bin"
        chacha_back = work / "demo_chacha_plain.txt"

        plain = b"Vernam one-time pad and ChaCha20 (cryptography) demo.\n"
        plain_path.write_bytes(plain)

        bar = "=" * 58
        print(f"\n{bar}\n1. Файл ключа (secrets, длина = открытый текст)\n{bar}")
        KeyFileGenerator.write_secrets(key_path, len(plain))
        print(f"Открытый текст: {plain_path} ({len(plain)} байт)")
        print(f"Ключ:           {key_path} ({key_path.stat().st_size} байт)")

        print(f"\n{bar}\n2. Шифр Вернама (XOR) и расшифрование\n{bar}")
        VernamCipher.encrypt_file(plain_path, key_path, cipher_path)
        VernamCipher.decrypt_file(cipher_path, key_path, recovered_path)
        ok = recovered_path.read_bytes() == plain
        print(f"Шифртекст:      {cipher_path}")
        print(f"Расшифровка:  {recovered_path} (совпадает с открытым: {ok})")

        print(f"\n{bar}\n3. ChaCha20 (пакет cryptography), ключ = SHA-256(файл ключа)\n{bar}")
        ChaCha20FileCipher.from_key_file(key_path).encrypt_file(plain_path, chacha_out)
        ChaCha20FileCipher.from_key_file(key_path).decrypt_file(chacha_out, chacha_back)
        ok2 = chacha_back.read_bytes() == plain
        print(f"ChaCha20 out: {chacha_out}\nChaCha20 plain: {chacha_back} (round-trip: {ok2})")


def prepare_samples(samples_dir: Path, method: str = "secrets", seed: int | None = None) -> tuple[Path, Path]:
    samples_dir.mkdir(parents=True, exist_ok=True)
    plain_path = samples_dir / "plain.txt"
    key_path = samples_dir / "key.bin"

    plain = b"Stream ciphers lab3 demo text.\n"
    plain_path.write_bytes(plain)

    m = method.lower()
    if m == "secrets":
        KeyFileGenerator.write_secrets(key_path, len(plain))
    else:
        if seed is None:
            raise click.UsageError("Для --method lcg укажите --seed")
        KeyFileGenerator.write_lcg(key_path, len(plain), seed)
    return plain_path, key_path


# --- CLI --------------------------------------------------------------------

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, help="Логи уровня DEBUG.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    configure_logging(verbose)
    ctx.ensure_object(dict)
    logger.debug("CLI инициализирован")


@cli.command("gen-key")
@click.argument("output", type=click.Path(path_type=Path))
@click.option(
    "-n",
    "--bytes",
    "nbytes",
    type=int,
    required=True,
    help="Сколько случайных байт записать.",
)
@click.option(
    "--method",
    type=click.Choice(["lcg", "secrets"], case_sensitive=False),
    default="secrets",
    show_default=True,
    help="lcg — линейный конгруэнтный генератор; secrets — встроенный CSPRNG.",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Начальное значение для ЛКГ (обязательно осмысленно для lcg).",
)
def cmd_gen_key(output: Path, nbytes: int, method: str, seed: int | None) -> None:
    """Сгенерировать файл ключа из случайных байт."""
    if nbytes <= 0:
        raise click.BadParameter("nbytes должен быть > 0")
    output.parent.mkdir(parents=True, exist_ok=True)
    m = method.lower()
    if m == "secrets":
        KeyFileGenerator.write_secrets(output, nbytes)
    else:
        if seed is None:
            raise click.UsageError("Для --method lcg укажите --seed")
        KeyFileGenerator.write_lcg(output, nbytes, seed)
    click.echo(f"Записано {nbytes} байт в {output}")


@cli.command("prepare-samples")
@click.option(
    "--dir",
    "samples_dir",
    type=click.Path(path_type=Path),
    default="samples",
    show_default=True,
    help="Каталог с демонстрационными файлами.",
)
@click.option(
    "--method",
    type=click.Choice(["lcg", "secrets"], case_sensitive=False),
    default="secrets",
    show_default=True,
    help="Метод генерации ключа.",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Seed для ЛКГ (используется только при --method lcg).",
)
def cmd_prepare_samples(samples_dir: Path, method: str, seed: int | None) -> None:
    """Подготовить samples/plain.txt и samples/key.bin для демо."""
    plain_path, key_path = prepare_samples(samples_dir, method=method, seed=seed)
    click.echo(f"Открытый текст: {plain_path} ({plain_path.stat().st_size} байт)")
    click.echo(f"Ключ: {key_path} ({key_path.stat().st_size} байт)")


@cli.command("vernam-encrypt")
@click.argument("plaintext", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("key", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("ciphertext", type=click.Path(path_type=Path))
def cmd_vernam_encrypt(plaintext: Path, key: Path, ciphertext: Path) -> None:
    """Зашифровать файл: XOR(открытый текст, ключ)."""
    ciphertext.parent.mkdir(parents=True, exist_ok=True)
    VernamCipher.encrypt_file(plaintext, key, ciphertext)
    click.echo(f"Шифртекст: {ciphertext}")


@cli.command("vernam-decrypt")
@click.argument("ciphertext", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("key", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("plaintext", type=click.Path(path_type=Path))
def cmd_vernam_decrypt(ciphertext: Path, key: Path, plaintext: Path) -> None:
    """Расшифровать файл: XOR(шифртекст, ключ)."""
    plaintext.parent.mkdir(parents=True, exist_ok=True)
    VernamCipher.decrypt_file(ciphertext, key, plaintext)
    click.echo(f"Открытый текст: {plaintext}")


@cli.command("chacha-encrypt")
@click.argument("input_file", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("key_file", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("output_file", type=click.Path(path_type=Path))
def cmd_chacha_encrypt(input_file: Path, key_file: Path, output_file: Path) -> None:
    """Зашифровать файл ChaCha20 (cryptography); в начале файла — 16 байт nonce."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ChaCha20FileCipher.from_key_file(key_file).encrypt_file(input_file, output_file)
    click.echo(f"ChaCha20: {output_file}")


@cli.command("chacha-decrypt")
@click.argument("input_file", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("key_file", type=click.Path(path_type=Path, exists=True, dir_okay=False))
@click.argument("output_file", type=click.Path(path_type=Path))
def cmd_chacha_decrypt(input_file: Path, key_file: Path, output_file: Path) -> None:
    """Расшифровать файл ChaCha20 (тот же key_file → тот же SHA-256 → 32 байта ключа)."""
    output_file.parent.mkdir(parents=True, exist_ok=True)
    ChaCha20FileCipher.from_key_file(key_file).decrypt_file(input_file, output_file)
    click.echo(f"ChaCha20 plain: {output_file}")


@cli.command("demo")
@click.option(
    "--dir",
    "work_dir",
    type=click.Path(path_type=Path),
    default=None,
    help="Каталог для демо-файлов (по умолчанию ./samples).",
)
def cmd_demo(work_dir: Path | None) -> None:
    """Краткий сценарий по пунктам задания."""
    base = Path.cwd() / "samples" if work_dir is None else work_dir
    SubmissionDemo().run(base)


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        logger.warning("Прервано пользователем")
        sys.exit(130)


if __name__ == "__main__":
    main()
