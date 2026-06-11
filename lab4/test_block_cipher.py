import logging
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

import block_cipher


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


class TestXTEA(unittest.TestCase):
    def test_encrypt_decrypt_block_roundtrip(self) -> None:
        key = bytes(range(16))
        for rounds in (1, 8, 32, 64):
            c = block_cipher.XTEABlockCipher(key, rounds=rounds)
            for plain in (b"\x00" * 8, b"abcdefgh", bytes(range(8))):
                self.assertEqual(c.decrypt_block(c.encrypt_block(plain)), plain)

    def test_wrong_key_length(self) -> None:
        with self.assertRaises(ValueError):
            block_cipher.XTEABlockCipher(b"short")

    def test_wrong_block_length(self) -> None:
        c = block_cipher.XTEABlockCipher(bytes(16))
        with self.assertRaises(ValueError):
            c.encrypt_block(b"1234567")
        with self.assertRaises(ValueError):
            c.decrypt_block(b"1234567")


class TestCBC(unittest.TestCase):
    def setUp(self) -> None:
        self.key = bytes(i * 17 % 256 for i in range(16))
        self.cbc = block_cipher.CBCFileCipher(block_cipher.XTEABlockCipher(self.key))

    def test_roundtrip_bytes(self) -> None:
        for plain in (b"", b"a", b"hello world", b"x" * 1000):
            iv = bytes(8)
            blob = self.cbc.encrypt_bytes(plain, iv=iv)
            self.assertEqual(self.cbc.decrypt_bytes(blob), plain)

    def test_random_iv_changes_blob(self) -> None:
        p = b"same"
        b1 = self.cbc.encrypt_bytes(p)
        b2 = self.cbc.encrypt_bytes(p)
        self.assertNotEqual(b1, b2)
        self.assertEqual(self.cbc.decrypt_bytes(b1), p)
        self.assertEqual(self.cbc.decrypt_bytes(b2), p)

    def test_decrypt_short_file(self) -> None:
        with self.assertRaises(ValueError):
            self.cbc.decrypt_bytes(b"1234567")

    def test_pkcs7_unpad_invalid(self) -> None:
        with self.assertRaises(ValueError):
            self.cbc.decrypt_bytes(bytes(16) + b"\x00" * 8)


class TestLoadKey(unittest.TestCase):
    def test_key_hex(self) -> None:
        h = "0" * 32
        k = block_cipher.load_key_16(None, h)
        self.assertEqual(k, bytes(16))

    def test_key_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "k.bin"
            p.write_bytes(bytes(range(16)))
            k = block_cipher.load_key_16(p, None)
            self.assertEqual(k, bytes(range(16)))


class TestCLI(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_logging()

    def test_encrypt_decrypt_file(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("plain.txt").write_text("secret data", encoding="utf-8")
            Path("key.bin").write_bytes(bytes(range(16)))
            r = runner.invoke(
                block_cipher.cli,
                ["-v", "encrypt", "plain.txt", "out.bin", "--key-file", "key.bin"],
            )
            self.assertEqual(r.exit_code, 0, r.output)
            r2 = runner.invoke(
                block_cipher.cli,
                ["decrypt", "out.bin", "back.txt", "--key-file", "key.bin"],
            )
            self.assertEqual(r2.exit_code, 0, r2.output)
            self.assertEqual(Path("back.txt").read_text(encoding="utf-8"), "secret data")

    def test_prepare_samples_cli(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            r = runner.invoke(
                block_cipher.cli,
                ["prepare-samples", "--dir", "samples"],
            )
            self.assertEqual(r.exit_code, 0, r.output)
            self.assertTrue(Path("samples/plain.txt").is_file())
            self.assertTrue(Path("samples/key.bin").is_file())
            self.assertEqual(Path("samples/key.bin").stat().st_size, 16)


if __name__ == "__main__":
    unittest.main()
