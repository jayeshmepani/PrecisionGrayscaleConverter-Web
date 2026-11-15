import unittest

import numpy as np
from PIL import Image

from main import convert_to_enhanced_grayscale


class GrayscaleModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Include saturated primaries and a mixed colour so the modes are not
        # accidentally all exercised with neutral grayscale input.
        pixels = np.array(
            [
                [[255, 0, 0], [0, 255, 0]],
                [[0, 0, 255], [40, 100, 180]],
            ],
            dtype=np.uint8,
        )
        cls.rgb_image = Image.fromarray(pixels, mode="RGB")

    def test_all_seven_modes_return_eight_bit_grayscale(self):
        modes = [
            "Rec. 601",
            "Rec. 709",
            "Rec. 2100",
            "Gamma",
            "L*a*b* (L*)",
            "HSL (Lightness)",
            "HSV (Value)",
        ]

        for mode in modes:
            with self.subTest(mode=mode):
                result, alpha = convert_to_enhanced_grayscale(
                    self.rgb_image, mode, 8
                )
                self.assertEqual(result.shape, (2, 2))
                self.assertEqual(result.dtype, np.uint8)
                self.assertIsNone(alpha)
                self.assertTrue(np.all(result >= 0))
                self.assertTrue(np.all(result <= 255))

    def test_perceptual_modes_are_not_silently_rec709(self):
        rec709, _ = convert_to_enhanced_grayscale(self.rgb_image, "Rec. 709", 8)

        for mode in ("L*a*b* (L*)", "HSL (Lightness)", "HSV (Value)"):
            with self.subTest(mode=mode):
                result, _ = convert_to_enhanced_grayscale(self.rgb_image, mode, 8)
                self.assertFalse(
                    np.array_equal(result, rec709),
                    f"{mode} unexpectedly produced the Rec. 709 output",
                )

    def test_sixteen_bit_output_uses_uint16(self):
        result, _ = convert_to_enhanced_grayscale(self.rgb_image, "L*a*b* (L*)", 16)
        self.assertEqual(result.shape, (2, 2))
        self.assertEqual(result.dtype, np.uint16)

    def test_alpha_channel_is_returned_separately(self):
        rgba = Image.fromarray(
            np.array([[[255, 0, 0, 64], [0, 255, 0, 192]]], dtype=np.uint8),
            mode="RGBA",
        )
        result, alpha = convert_to_enhanced_grayscale(rgba, "Rec. 709", 8)
        self.assertEqual(result.shape, (1, 2))
        self.assertIsNotNone(alpha)
        self.assertEqual(np.array(alpha).tolist(), [[64, 192]])


if __name__ == "__main__":
    unittest.main()
