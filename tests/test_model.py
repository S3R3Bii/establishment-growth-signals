from pathlib import Path
from fractions import Fraction as F
import sys, unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from model import (
    source_number,
    valid_target,
    quantize,
    fixed,
    predict,
    summarize,
    SCALE,
)


class GrowthFixtures(unittest.TestCase):
    def test_half_even_zero(self):
        self.assertEqual(quantize(F(1, 2 * SCALE)), 0)

    def test_half_even_up(self):
        self.assertEqual(quantize(F(3, 2 * SCALE)), 2)

    def test_half_even_down(self):
        self.assertEqual(quantize(F(5, 2 * SCALE)), 2)

    def test_negative_round(self):
        self.assertEqual(quantize(F(-3, 2 * SCALE)), -2)

    def test_fixed_sign(self):
        self.assertEqual(fixed(-SCALE - 1), "-1.000000000001")

    def test_direct_source_flag(self):
        self.assertIsNone(source_number("D"))
        self.assertIsNone(source_number("S"))
        self.assertIsNone(source_number("X"))
        self.assertIsNone(source_number("N"))

    def test_denom_fraction(self):
        self.assertEqual(source_number("2.5"), F(5, 2))

    def test_missing_target_not_inferred(self):
        self.assertFalse(
            valid_target(
                dict(
                    job_creation_continuers="D",
                    denom="1000",
                    job_creation="100",
                    job_creation_births="20",
                )
            )
        )

    def test_zero_denom_invalid(self):
        self.assertFalse(valid_target(dict(job_creation_continuers="20", denom="0")))

    def test_zero_target_valid(self):
        self.assertTrue(valid_target(dict(job_creation_continuers="0", denom="1000")))

    def test_half_pool_hand(self):
        self.assertEqual(predict(F(10), F(100), F(40), F(200), F(1, 2)), 15 * SCALE)

    def test_own_endpoint(self):
        self.assertEqual(predict(F(10), F(100), F(40), F(200), F(1)), 10 * SCALE)

    def test_pool_endpoint(self):
        self.assertEqual(predict(F(10), F(100), F(40), F(200), F(0)), 20 * SCALE)

    def test_outside_weight_rejected(self):
        with self.assertRaises(ValueError):
            predict(F(1), F(1), F(1), F(1), F(2))

    def test_equal_series_differs_from_case_mean(self):
        rows = [
            dict(st="A", sector="11", error_scaled=SCALE, target_denom=F(1)),
            dict(st="A", sector="11", error_scaled=3 * SCALE, target_denom=F(1)),
            dict(st="B", sector="11", error_scaled=10 * SCALE, target_denom=F(10)),
        ]
        r = summarize(rows)
        self.assertEqual(F(r["mae"]), 6)
        self.assertEqual(F(r["mse"]), F(105, 2))
        self.assertEqual(F(r["weighted_mae"]), F(26, 3))

    def test_empty_summary(self):
        self.assertEqual(summarize([])["n"], 0)


if __name__ == "__main__":
    unittest.main()
