import logging
import tempfile
import unittest
from pathlib import Path

from click.testing import CliRunner

import entropy_lab


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


class TestFrequencies(unittest.TestCase):
    def test_byte_frequencies(self) -> None:
        c = entropy_lab.byte_frequencies(b"aba")
        self.assertEqual(c[ord("a")], 2)
        self.assertEqual(c[ord("b")], 1)
        self.assertEqual(sum(c.values()), 3)

    def test_empty(self) -> None:
        self.assertEqual(dict(entropy_lab.byte_frequencies(b"")), {})


class TestEntropy(unittest.TestCase):
    def test_single_symbol_zero(self) -> None:
        c = entropy_lab.byte_frequencies(b"ZZZZ")
        self.assertAlmostEqual(entropy_lab.entropy_from_frequencies(c), 0.0)

    def test_empty_zero(self) -> None:
        self.assertEqual(entropy_lab.entropy_from_frequencies(entropy_lab.Counter()), 0.0)

    def test_fair_coin_one_bit(self) -> None:
        c = entropy_lab.byte_frequencies(b"01" * 5000)
        h = entropy_lab.entropy_from_frequencies(c)
        self.assertAlmostEqual(h, 1.0)

    def test_uniform_four_symbols(self) -> None:
        c = entropy_lab.Counter({0: 1, 1: 1, 2: 1, 3: 1})
        self.assertAlmostEqual(entropy_lab.entropy_from_frequencies(c), 2.0)

    def test_theoretical_max(self) -> None:
        self.assertAlmostEqual(entropy_lab.theoretical_max_entropy(256), 8.0)
        self.assertAlmostEqual(entropy_lab.theoretical_max_entropy(2), 1.0)


class TestFileRoundtrip(unittest.TestCase):
    def test_from_file_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "t.bin"
            p.write_bytes(b"aabb")
            c = entropy_lab.frequencies_from_file(p)
            self.assertEqual(c[ord("a")], 2)
            self.assertEqual(c[ord("b")], 2)


class TestCLI(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_logging()

    def test_freq_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.bin"
            p.write_bytes(b"aaa")
            runner = CliRunner()
            r = runner.invoke(entropy_lab.cli, ["freq", str(p), "--top", "5"])
            self.assertEqual(r.exit_code, 0, r.output)
            self.assertIn("Всего символов", r.output)

    def test_entropy_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.bin"
            p.write_bytes(b"01" * 100)
            runner = CliRunner()
            r = runner.invoke(entropy_lab.cli, ["entropy", str(p)])
            self.assertEqual(r.exit_code, 0, r.output)
            self.assertIn("H =", r.output)

    def test_demo_creates_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            runner = CliRunner()
            r = runner.invoke(
                entropy_lab.cli,
                ["demo", "-n", "5000", "--seed", "1"],
                catch_exceptions=False,
            )
            self.assertEqual(r.exit_code, 0, r.output)
            samples = Path("samples")
            self.assertTrue((samples / "sample_const.bin").is_file())
            self.assertTrue((samples / "sample_uniform255.bin").is_file())


if __name__ == "__main__":
    unittest.main()
