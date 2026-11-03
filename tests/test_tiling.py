"""Controleer dat landelijke tegeluitvoer volledig én duplicaatvrij is."""
import unittest
from woningtype_3d_bagloos.tiling import area, subdivide, tile_owns_point, tile_windows


class TilingTests(unittest.TestCase):
    def test_tiles_cover_extent_once(self):
        extent = (0, 0, 23000, 15500)
        tiles = list(tile_windows(extent, 10000))
        self.assertEqual(len(tiles), 6)
        self.assertAlmostEqual(sum(area(tile) for tile in tiles), area(extent))
        for x, y in ((0, 0), (9999.99, 100), (10000, 100),
                     (22999, 15499), (23000, 15500)):
            self.assertEqual(
                sum(tile_owns_point(tile, extent, x, y) for tile in tiles), 1
            )

    def test_adaptive_split_preserves_ownership(self):
        overall = (0, 0, 1000, 1000)
        left, right = subdivide(overall)
        self.assertEqual(area(left) + area(right), area(overall))
        for x, y in ((200, 200), (500, 500), (999, 999)):
            self.assertEqual(
                sum(tile_owns_point(tile, overall, x, y)
                    for tile in (left, right)), 1
            )

    def test_invalid_extent_and_tile_size(self):
        with self.assertRaises(ValueError):
            list(tile_windows((0, 0, 10, 10), 0))
        with self.assertRaises(ValueError):
            list(tile_windows((10, 0, 0, 10), 10))


if __name__ == "__main__":
    unittest.main()
