import logging
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

import stream_ciphers


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


class TestLCG(unittest.TestCase):
    def test_lcg_deterministic(self) -> None:
        a = stream_ciphers.LinearCongruentialGenerator(12345)
        b = stream_ciphers.LinearCongruentialGenerator(12345)
        for _ in range(100):
            self.assertEqual(a.next_u32(), b.next_u32())

    def test_key_file_lcg_length(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "k.bin"
            stream_ciphers.KeyFileGenerator.write_lcg(p, 500, seed=1)
            self.assertEqual(p.stat().st_size, 500)


class TestVernam(unittest.TestCase):
    def test_roundtrip(self) -> None:
        plain = b"secret message"
        key = b"k" * len(plain)
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            pf, kf, cf, rf = t / "p.bin", t / "k.bin", t / "c.bin", t / "r.bin"
            pf.write_bytes(plain)
            kf.write_bytes(key)
            stream_ciphers.VernamCipher.encrypt_file(pf, kf, cf)
            stream_ciphers.VernamCipher.decrypt_file(cf, kf, rf)
            self.assertEqual(rf.read_bytes(), plain)

    def test_xor_known(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            pf = t / "p.bin"
            kf = t / "k.bin"
            of = t / "o.bin"
            pf.write_bytes(bytes([0x00, 0xFF, 0x55]))
            kf.write_bytes(bytes([0xAA, 0x55, 0xFF]))
            stream_ciphers.VernamCipher.xor_files(pf, kf, of)
            self.assertEqual(of.read_bytes(), bytes([0xAA, 0xAA, 0xAA]))

    def test_key_too_short(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            pf, kf, of = t / "p.bin", t / "k.bin", t / "o.bin"
            pf.write_bytes(b"abcd")
            kf.write_bytes(b"ab")
            with self.assertRaises(ValueError):
                stream_ciphers.VernamCipher.xor_files(pf, kf, of)


class TestChaCha20(unittest.TestCase):
    def test_key_derivation_length(self) -> None:
        k = stream_ciphers.chacha20_key_from_keyfile_material(b"any-length-password")
        self.assertEqual(len(k), 32)

    def test_file_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            inp, outp, back, kf = t / "i.bin", t / "o.bin", t / "b.bin", t / "key.bin"
            inp.write_bytes(b"file stream data")
            kf.write_bytes(b"material from key file")
            key32 = stream_ciphers.chacha20_key_from_keyfile_material(kf.read_bytes())
            stream_ciphers.ChaCha20FileCipher(key32).encrypt_file(inp, outp)
            stream_ciphers.ChaCha20FileCipher(key32).decrypt_file(outp, back)
            self.assertEqual(back.read_bytes(), b"file stream data")
            self.assertGreaterEqual(outp.stat().st_size, 16 + len(b"file stream data"))

    def test_decrypt_short_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            bad = t / "bad.bin"
            out = t / "o.bin"
            bad.write_bytes(b"short")
            key32 = stream_ciphers.chacha20_key_from_keyfile_material(b"x")
            with self.assertRaises(ValueError):
                stream_ciphers.ChaCha20FileCipher(key32).decrypt_file(bad, out)


class TestCLI(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_logging()

    def test_gen_key_secrets(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            r = runner.invoke(
                stream_ciphers.cli,
                ["gen-key", "k.bin", "-n", "32", "--method", "secrets"],
            )
            self.assertEqual(r.exit_code, 0, r.output)
            self.assertEqual(Path("k.bin").stat().st_size, 32)

    def test_gen_key_lcg_requires_seed(self) -> None:
        runner = CliRunner()
        r = runner.invoke(stream_ciphers.cli, ["gen-key", "k.bin", "-n", "10", "--method", "lcg"])
        self.assertNotEqual(r.exit_code, 0)

    def test_prepare_samples_cli(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            r = runner.invoke(
                stream_ciphers.cli,
                ["prepare-samples", "--dir", "samples", "--method", "secrets"],
            )
            self.assertEqual(r.exit_code, 0, r.output)
            plain = Path("samples/plain.txt")
            key = Path("samples/key.bin")
            self.assertTrue(plain.is_file())
            self.assertTrue(key.is_file())
            self.assertEqual(plain.stat().st_size, key.stat().st_size)

    def test_vernam_cli(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("p.txt").write_bytes(b"hi")
            Path("key.bin").write_bytes(b"\x01\x02")
            r = runner.invoke(
                stream_ciphers.cli,
                ["vernam-encrypt", "p.txt", "key.bin", "c.bin"],
            )
            self.assertEqual(r.exit_code, 0, r.output)
            r2 = runner.invoke(
                stream_ciphers.cli,
                ["vernam-decrypt", "c.bin", "key.bin", "out.txt"],
            )
            self.assertEqual(r2.exit_code, 0)
            self.assertEqual(Path("out.txt").read_bytes(), b"hi")

    def test_chacha_cli(self) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem():
            Path("p.bin").write_bytes(b"secret data")
            Path("key.bin").write_bytes(b"my-key-material")
            r = runner.invoke(
                stream_ciphers.cli,
                ["chacha-encrypt", "p.bin", "key.bin", "c.bin"],
            )
            self.assertEqual(r.exit_code, 0, r.output)
            r2 = runner.invoke(
                stream_ciphers.cli,
                ["chacha-decrypt", "c.bin", "key.bin", "out.bin"],
            )
            self.assertEqual(r2.exit_code, 0, r2.output)
            self.assertEqual(Path("out.bin").read_bytes(), b"secret data")
