from __future__ import annotations

import logging
import re
import string
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


class CaesarCipher:

    @staticmethod
    def alphabet_size() -> int:
        return len(string.ascii_lowercase)

    def encrypt(self, text: str, key: int) -> str:
        m = self.alphabet_size()
        key %= m
        logger.debug("encrypt key=%s text_len=%s", key, len(text))

        def shift(c: str) -> str:
            if "a" <= c <= "z":
                return chr(ord("a") + (ord(c) - ord("a") + key) % m)
            if "A" <= c <= "Z":
                return chr(ord("A") + (ord(c) - ord("A") + key) % m)
            return c

        return "".join(shift(c) for c in text)

    def decrypt(self, text: str, key: int) -> str:
        return self.encrypt(text, -key)

    def known_plaintext_key(self, plain: str, cipher: str) -> int | None:
        m = self.alphabet_size()
        keys = [
            (ord(cl) - ord(pl)) % m
            for pl, cl in zip(plain.lower(), cipher.lower())
            if pl.isalpha() and cl.isalpha()
        ]
        if not keys:
            logger.debug("KPA: нет пар букв")
            return None
        k = Counter(keys).most_common(1)[0][0]
        logger.debug("KPA: ключ=%s (пар букв: %s)", k, len(keys))
        return k

    def ciphertext_variants(self, ciphertext: str) -> list[tuple[int, str]]:
        n = self.alphabet_size()
        logger.debug("brute-force: %s ключей", n)
        return [(k, self.decrypt(ciphertext, k)) for k in range(n)]


class WordDictionary:
    """Словарь слов для эвристического подбора ключа."""

    _FALLBACK = frozenset(
        {
            "the", "and", "for", "are", "but", "not", "you", "all", "can", "was",
            "one", "our", "out", "day", "get", "has", "him", "his", "how", "man",
            "new", "now", "old", "see", "two", "way", "who", "hello", "world",
            "this", "that", "with", "from", "attack", "cipher", "plain", "text",
        }
    )

    def __init__(self, words: set[str]) -> None:
        self._words = words

    @property
    def words(self) -> set[str]:
        return self._words

    @classmethod
    def load(cls, path: Path | None = None) -> WordDictionary:
        default = Path(__file__).resolve().parent / "words.txt"
        p = Path(path) if path is not None else default
        if path is not None and not p.is_file():
            raise FileNotFoundError(p)
        if not p.is_file():
            logger.warning("Файл словаря не найден (%s), встроенный набор", p)
            return cls(set(cls._FALLBACK))
        raw: set[str] = set()
        for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
            w = line.strip().lower()
            if w.isalpha():
                raw.add(w)
        if not raw:
            logger.warning("Словарь пуст (%s), встроенный набор", p)
            return cls(set(cls._FALLBACK))
        logger.debug("Словарь: %s слов из %s", len(raw), p)
        return cls(raw)

    @staticmethod
    def _tokens(text: str) -> list[str]:
        return re.findall(r"[a-z]+", text.lower())

    def score(self, text: str) -> tuple[int, int]:
        t = self._tokens(text)
        if not t:
            return 0, 0
        hits = sum(1 for w in t if w in self._words)
        return hits, len(t)

    def best_key(self, ciphertext: str, cipher: CaesarCipher) -> tuple[int, str, float]:
        def metric(k: int) -> tuple[float, int]:
            plain = cipher.decrypt(ciphertext, k)
            h, tot = self.score(plain)
            return (h / tot if tot else 0.0, h)

        k = max(range(cipher.alphabet_size()), key=metric)
        plain = cipher.decrypt(ciphertext, k)
        h, tot = self.score(plain)
        ratio = h / tot if tot else 0.0
        logger.debug("Словарь: лучший ключ=%s, совпадений %s/%s", k, h, tot)
        return k, plain, ratio


class SubmissionDemo:

    def __init__(self, cipher: CaesarCipher, dictionary: WordDictionary) -> None:
        self._cipher = cipher
        self._dict = dictionary

    def run(self) -> None:
        logger.debug("Демо-сценарий для сдачи")
        plain = "Hello world attack cipher"
        key = 3
        bar = "=" * 58
        c = self._cipher
        d = self._dict
        cipher = c.encrypt(plain, key)

        print(f"\n{bar}\n1. Шифрование / расшифрование (ключ {key})\n{bar}")
        print(f"Открытый текст:  {plain}")
        print(f"Шифртекст:       {cipher}")
        print(f"Расшифрование:   {c.decrypt(cipher, key)}")

        print(f"\n{bar}\n2. Атака по известному открытому тексту\n{bar}")
        print(f"Открытый текст:  {plain}\nШифртекст:       {cipher}")
        print(f"Найденный ключ:  {c.known_plaintext_key(plain, cipher)}")

        print(f"\n{bar}\n3. Все варианты расшифрования\n{bar}\nШифртекст: {cipher}\n")
        for k, p in c.ciphertext_variants(cipher):
            print(f"  k={k:2d}  {p}")

        print(f"\n{bar}\n4. Подбор ключа по словарю\n{bar}\nШифртекст: {cipher}")
        k_dic, recovered, ratio = d.best_key(cipher, c)
        h, t = d.score(recovered)
        print(f"Выбранный ключ:  {k_dic}\nТекст:           {recovered}")
        print(f"Совпадений:      {h}/{t} ({ratio:.0%})")


# --- CLI --------------------------------------------------------------------

@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.option("-v", "--verbose", is_flag=True, help="Логи уровня DEBUG.")
@click.option(
    "--words",
    "words_path",
    type=click.Path(path_type=Path, exists=True, dir_okay=False),
    default=None,
    help="Файл словаря (иначе words.txt рядом со скриптом).",
)
@click.pass_context
def cli(ctx: click.Context, verbose: bool, words_path: Path | None) -> None:
    """Шифр Цезаря: шифрование, расшифрование, атаки."""
    configure_logging(verbose)
    ctx.obj = {
        "cipher": CaesarCipher(),
        "dictionary": WordDictionary.load(words_path),
    }
    logger.debug("CLI инициализирован")


@cli.command("encrypt")
@click.argument("text")
@click.option("-k", "--key", type=int, required=True, help="Ключ 0…25 (сводится по модулю).")
@click.pass_obj
def cmd_encrypt(obj: dict, text: str, key: int) -> None:
    """Зашифровать текст."""
    out = obj["cipher"].encrypt(text, key)
    logger.debug("encrypt готово")
    click.echo(out)


@cli.command("decrypt")
@click.argument("ciphertext")
@click.option("-k", "--key", type=int, required=True)
@click.pass_obj
def cmd_decrypt(obj: dict, ciphertext: str, key: int) -> None:
    """Расшифровать с известным ключом."""
    out = obj["cipher"].decrypt(ciphertext, key)
    logger.debug("decrypt готово")
    click.echo(out)


@cli.command("kpa")
@click.option("--plain", "plain_text", required=True, help="Открытый текст.")
@click.option("--cipher", "cipher_text", required=True, help="Шифртекст.")
@click.pass_obj
def cmd_kpa(obj: dict, plain_text: str, cipher_text: str) -> None:
    """Ключ по известному открытому тексту (known-plaintext)."""
    k = obj["cipher"].known_plaintext_key(plain_text, cipher_text)
    if k is None:
        click.echo("Ключ не найден (нет пар букв).", err=True)
        raise SystemExit(1)
    click.echo(k)


@cli.command("brute")
@click.argument("ciphertext")
@click.pass_obj
def cmd_brute(obj: dict, ciphertext: str) -> None:
    """Все варианты расшифрования (ciphertext-only, полный перебор ключей)."""
    for k, p in obj["cipher"].ciphertext_variants(ciphertext):
        click.echo(f"k={k:2d}\t{p}")


@cli.command("dict-attack")
@click.argument("ciphertext")
@click.pass_obj
def cmd_dict_attack(obj: dict, ciphertext: str) -> None:
    """Подобрать ключ по словарю (максимум слов из словаря)."""
    c, d = obj["cipher"], obj["dictionary"]
    k, plain, ratio = d.best_key(ciphertext, c)
    h, t = d.score(plain)
    click.echo(f"key={k}\n{plain}\nscore={h}/{t} ({ratio:.0%})")


@cli.command("demo")
@click.pass_obj
def cmd_demo(obj: dict) -> None:
    """Готовый сценарий для сдачи (печать всех пунктов)."""
    SubmissionDemo(obj["cipher"], obj["dictionary"]).run()


def main() -> None:
    try:
        cli()
    except KeyboardInterrupt:
        logger.warning("Прервано пользователем")
        sys.exit(130)


if __name__ == "__main__":
    main()
