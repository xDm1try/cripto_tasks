import logging
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

import caesar


def _reset_logging() -> None:
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
        try:
            h.close()
        except Exception:
            pass


def setUpModule() -> None:
    _reset_logging()


class TestCaesarCipher(unittest.TestCase):
    def setUp(self) -> None:
        self.c = caesar.CaesarCipher()

    def test_encrypt_decrypt_roundtrip(self) -> None:
        s = "Hello, World! 123 xyz"
        for k in range(26):
            ciph = self.c.encrypt(s, k)
            self.assertEqual(self.c.decrypt(ciph, k), s)

    def test_encrypt_known(self) -> None:
        self.assertEqual(self.c.encrypt("abc", 1), "bcd")
        self.assertEqual(self.c.encrypt("XYZ", 3), "ABC")
        self.assertEqual(self.c.encrypt("z", 1), "a")

    def test_key_wrap(self) -> None:
        self.assertEqual(self.c.encrypt("a", 26), "a")
        self.assertEqual(self.c.encrypt("a", 52), "a")

    def test_non_letters_unchanged(self) -> None:
        self.assertEqual(self.c.encrypt(" !?9\n", 5), " !?9\n")

    def test_known_plaintext_key(self) -> None:
        self.assertEqual(self.c.known_plaintext_key("abc", "def"), 3)
        self.assertEqual(self.c.known_plaintext_key("Hello", "Khoor"), 3)
        self.assertIsNone(self.c.known_plaintext_key("123", "456"))

    def test_known_plaintext_majority_vote(self) -> None:
        self.assertEqual(self.c.known_plaintext_key("aaaax", "bbbbx"), 1)

    def test_ciphertext_variants_count(self) -> None:
        out = self.c.ciphertext_variants("a")
        self.assertEqual(len(out), 26)
        self.assertTrue(any(k == 0 and p == "a" for k, p in out))


class TestWordDictionary(unittest.TestCase):
    def test_score(self) -> None:
        d = caesar.WordDictionary({"hello", "world"})
        self.assertEqual(d.score("Hello world!"), (2, 2))
        self.assertEqual(d.score("zzz"), (0, 1))

    def test_best_key(self) -> None:
        c = caesar.CaesarCipher()
        d = caesar.WordDictionary({"hello", "world"})
        cipher = c.encrypt("Hello world", 7)
        k, plain, ratio = d.best_key(cipher, c)
        self.assertEqual(k, 7)
        self.assertEqual(plain.lower(), "hello world")
        self.assertEqual(ratio, 1.0)

    def test_load_from_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "w.txt"
            p.write_text("alpha\nbeta\n", encoding="utf-8")
            d = caesar.WordDictionary.load(p)
            self.assertEqual(d.words, {"alpha", "beta"})

    def test_load_empty_file_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "empty.txt"
            p.write_text("", encoding="utf-8")
            d = caesar.WordDictionary.load(p)
            self.assertIn("hello", d.words)


class TestCLI(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_logging()

    def test_encrypt_decrypt_cli(self) -> None:
        runner = CliRunner()
        r = runner.invoke(caesar.cli, ["encrypt", "abc", "-k", "1"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertEqual(r.output.strip(), "bcd")
        r2 = runner.invoke(caesar.cli, ["decrypt", "bcd", "-k", "1"])
        self.assertEqual(r2.exit_code, 0)
        self.assertEqual(r2.output.strip(), "abc")

    def test_kpa_cli(self) -> None:
        runner = CliRunner()
        r = runner.invoke(
            caesar.cli,
            ["kpa", "--plain", "Hello", "--cipher", "Khoor"],
        )
        self.assertEqual(r.exit_code, 0)
        self.assertEqual(r.output.strip(), "3")


if __name__ == "__main__":
    unittest.main()
