import logging
import unittest

from click.testing import CliRunner

import dlog_lab


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


class TestHelpers(unittest.TestCase):
    def test_isqrt_ceil(self) -> None:
        self.assertEqual(dlog_lab.isqrt_ceil(0), 0)
        self.assertEqual(dlog_lab.isqrt_ceil(1), 1)
        self.assertEqual(dlog_lab.isqrt_ceil(2), 2)
        self.assertEqual(dlog_lab.isqrt_ceil(4), 2)
        self.assertEqual(dlog_lab.isqrt_ceil(28), 6)
        self.assertEqual(dlog_lab.isqrt_ceil(100_000), 317)


class TestBruteForce(unittest.TestCase):
    def test_finds_known_x(self) -> None:
        x, mults, _ = dlog_lab.brute_force_log(2, 22, 29)
        self.assertEqual(x, 26)
        self.assertEqual(mults, 26)
        self.assertEqual(pow(2, x, 29), 22)

    def test_y_equal_one_returns_zero(self) -> None:
        x, mults, _ = dlog_lab.brute_force_log(7, 1, 13)
        self.assertEqual((x, mults), (0, 0))

    def test_small_known_value(self) -> None:
        x, mults, _ = dlog_lab.brute_force_log(3, 13, 17)
        self.assertEqual(x, 4)
        self.assertEqual(mults, 4)

    def test_returns_none_when_no_solution(self) -> None:
        x, _, _ = dlog_lab.brute_force_log(4, 3, 7, n=5)
        self.assertIsNone(x)

    def test_pairs_consistent_with_a_pow_x(self) -> None:
        a, y, p = 2, 22, 29
        _, _, pairs = dlog_lab.brute_force_log(a, y, p)
        for x, val in pairs:
            self.assertEqual(val, pow(a, x, p))


class TestBSGS(unittest.TestCase):
    def test_finds_known_x(self) -> None:
        x, mults, trace = dlog_lab.bsgs(2, 22, 29)
        self.assertIsNotNone(x)
        self.assertEqual(pow(2, x, 29), 22)
        self.assertGreater(mults, 0)
        self.assertGreater(trace.m, 0)
        self.assertGreater(trace.k, 0)
        self.assertGreaterEqual(trace.m * trace.k, trace.n)

    def test_y_equal_one_returns_zero(self) -> None:
        x, mults, trace = dlog_lab.bsgs(7, 1, 13)
        self.assertEqual((x, mults), (0, 0))
        self.assertEqual(trace.found, (0, 0, 0))

    def test_small_known_value(self) -> None:
        x, _, _ = dlog_lab.bsgs(3, 13, 17)
        self.assertEqual(pow(3, x, 17), 13)

    def test_matches_brute_force(self) -> None:
        cases = [(2, 22, 29), (3, 13, 17), (5, 4, 23), (2, 17, 19), (3, 1, 17)]
        for a, y, p in cases:
            with self.subTest(a=a, y=y, p=p):
                bx, _, _ = dlog_lab.brute_force_log(a, y, p)
                sx, _, _ = dlog_lab.bsgs(a, y, p)
                self.assertIsNotNone(bx)
                self.assertIsNotNone(sx)
                self.assertEqual(pow(a, sx, p), pow(a, bx, p))

    def test_bsgs_uses_fewer_mults_than_brute_for_large_x(self) -> None:
        p, a, secret = 100003, 2, 54321
        y = pow(a, secret, p)
        _, brute_mults, _ = dlog_lab.brute_force_log(a, y, p)
        _, bsgs_mults, _ = dlog_lab.bsgs(a, y, p)
        self.assertGreater(brute_mults, 10 * bsgs_mults)

    def test_m_and_k_cover_n(self) -> None:
        for p in (29, 101, 1009, 9973):
            with self.subTest(p=p):
                _, _, t = dlog_lab.bsgs(2, 1, p)
                if t.m and t.k:
                    self.assertGreaterEqual(t.m * t.k, t.n)


class TestErrors(unittest.TestCase):
    def test_invalid_modulus(self) -> None:
        with self.assertRaises(ValueError):
            dlog_lab.bsgs(2, 1, 1)
        with self.assertRaises(ValueError):
            dlog_lab.brute_force_log(2, 1, 1)

    def test_invalid_base(self) -> None:
        with self.assertRaises(ValueError):
            dlog_lab.bsgs(0, 1, 7)

    def test_negative_n(self) -> None:
        with self.assertRaises(ValueError):
            dlog_lab.bsgs(2, 1, 7, n=-1)


class TestFormatters(unittest.TestCase):
    def test_brute_trace_string(self) -> None:
        _, _, pairs = dlog_lab.brute_force_log(2, 22, 29)
        text = dlog_lab.format_brute_trace(29, pairs)
        self.assertIn("a^x mod 29", text)
        self.assertIn("26", text)

    def test_brute_trace_truncates(self) -> None:
        p, a, secret = 1_000_003, 2, 999_990
        y = pow(a, secret, p)
        _, _, pairs = dlog_lab.brute_force_log(a, y, p)
        text = dlog_lab.format_brute_trace(p, pairs, max_rows=20)
        self.assertIn("...", text)

    def test_bsgs_trace_string(self) -> None:
        _, _, trace = dlog_lab.bsgs(2, 22, 29)
        text = dlog_lab.format_bsgs_trace(2, 29, trace)
        self.assertIn("Шаг младенца", text)
        self.assertIn("Шаг великана", text)
        self.assertIn("Найдено", text)


class TestCLI(unittest.TestCase):
    def tearDown(self) -> None:
        _reset_logging()

    def test_brute_cli(self) -> None:
        runner = CliRunner()
        r = runner.invoke(dlog_lab.cli, ["brute", "2", "22", "29"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertIn("Найдено: x = 26", r.output)
        self.assertIn("умножений: 26", r.output)

    def test_bsgs_cli(self) -> None:
        runner = CliRunner()
        r = runner.invoke(dlog_lab.cli, ["bsgs", "2", "22", "29"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertIn("Шаг младенца", r.output)
        self.assertIn("Шаг великана", r.output)
        self.assertIn("Результат: x = 26", r.output)

    def test_compare_cli(self) -> None:
        runner = CliRunner()
        r = runner.invoke(dlog_lab.cli, ["compare", "2", "22", "29"])
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertIn("BSGS:", r.output)
        self.assertIn("Перебор:", r.output)

    def test_demo_cli(self) -> None:
        runner = CliRunner()
        r = runner.invoke(dlog_lab.cli, ["demo"], catch_exceptions=False)
        self.assertEqual(r.exit_code, 0, r.output)
        self.assertIn("Шаг младенца", r.output)
        self.assertIn("BSGS", r.output)


if __name__ == "__main__":
    unittest.main()
