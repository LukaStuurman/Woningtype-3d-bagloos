"""Tests op de pure classificatiekern, geen QGIS of netwerk nodig."""
import unittest

from woningtype_3d_bagloos.classify import (
    APPARTEMENT, HOEK, TUSSEN, TWEEKAP, VRIJ, classify_pands,
    excluded_pand, normalize_bag_id, roof_continuity,
)


class WoningtypeTests(unittest.TestCase):
    @staticmethod
    def _home(n=1):
        return {"usage": "woonfunctie", "count_vbo": n}

    def test_vrijstaand_en_appartement(self):
        pands = [self._home(), self._home(3)]
        result = classify_pands(pands, {}, source="BAG")
        self.assertEqual([r["woningtype"] for r in result], [VRIJ, APPARTEMENT])

    def test_twee_onder_een_kap(self):
        pands = [self._home(), self._home()]
        adjacency = {0: {1}, 1: {0}}
        result = classify_pands(pands, adjacency, source="BAG")
        self.assertEqual([r["woningtype"] for r in result], [TWEEKAP, TWEEKAP])

    def test_hoek_en_tussenwoning(self):
        pands = [self._home() for _ in range(3)]
        adjacency = {0: {1}, 1: {0, 2}, 2: {1}}
        result = classify_pands(pands, adjacency)
        self.assertEqual([r["woningtype"] for r in result], [HOEK, TUSSEN, HOEK])

    def test_carport_separates_roof_contact(self):
        pands = [self._home(), self._home()]
        result = classify_pands(
            pands, {0: {1}, 1: {0}}, roof_links={(0, 1): False}
        )
        self.assertEqual([r["woningtype"] for r in result], [VRIJ, VRIJ])
        self.assertEqual(result[0]["dakgetest"], 1)
        self.assertEqual(result[0]["dakonzeker"], 0)

    def test_no_ahn_data_keeps_bag_assessment_and_warns(self):
        pands = [self._home(), self._home()]
        result = classify_pands(
            pands, {0: {1}, 1: {0}}, roof_links={(0, 1): None}
        )
        self.assertEqual([r["woningtype"] for r in result], [TWEEKAP, TWEEKAP])
        self.assertEqual(result[0]["dakonzeker"], 1)
        self.assertIn("controle nodig", result[0]["controle"])

    def test_niet_woonfunctie(self):
        result = classify_pands(
            [self._home(), {"usage": "winkelfunctie", "count_vbo": 1}], {}
        )
        self.assertEqual(result[1]["woningtype"], "")

    def test_dakhoogtes(self):
        self.assertIs(
            roof_continuity([7.0]*4, [7.2]*4, [8.0]*6, [8.1]*6), True
        )
        self.assertIs(
            roof_continuity([6.0]*4, [10.0]*4, [9.0]*6, [11.0]*6), False
        )
        self.assertIsNone(
            roof_continuity([7.0]*2, [7.0]*2, [7.0]*5, [7.0]*5)
        )
        self.assertIsNone(
            roof_continuity([1e38]*4, [1e38]*4, [2.0]*5, [2.0]*5)
        )

    def test_bag_identificatie_en_status(self):
        self.assertEqual(normalize_bag_id("NL.IMBAG.Pand.012345"), "012345")
        self.assertTrue(excluded_pand("Pand gesloopt"))
        self.assertFalse(excluded_pand("Pand in gebruik"))


if __name__ == "__main__":
    unittest.main()
