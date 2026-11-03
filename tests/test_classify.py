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

    def test_aanliggende_garage_als_apart_bag_pand_is_geen_woonbuur(self):
        # Sommige garages zijn eigen BAG-panden zonder VBO, dus niet 1 VBO.
        houses = [
            self._home(),
            {"usage": "overige gebruiksfunctie", "count_vbo": 0},
            self._home(),
        ]
        result = classify_pands(
            houses, {0: {1}, 1: {0, 2}, 2: {1}}, source="BAG"
        )
        self.assertEqual(
            [r["woningtype"] for r in result], [VRIJ, "", VRIJ]
        )

    def test_carport_separates_roof_contact(self):
        pands = [self._home(), self._home()]
        result = classify_pands(
            pands, {0: {1}, 1: {0}}, roof_links={(0, 1): False}
        )
        self.assertEqual([r["woningtype"] for r in result], [VRIJ, VRIJ])
        self.assertEqual(result[0]["dakgetest"], 1)
        self.assertEqual(result[0]["dakonzeker"], 0)

    def test_vier_woningen_twee_tweekappers_met_lage_garagebrug(self):
        # Twee hoofdwoningparen, verbonden door lage garages, zijn geen rij.
        pands = [self._home() for _ in range(4)]
        neighbours = {0: {1}, 1: {0, 2}, 2: {1, 3}, 3: {2}}
        roof_links = {(0, 1): True, (1, 2): "bijgebouw", (2, 3): True}
        result = classify_pands(pands, neighbours, roof_links)
        self.assertEqual(
            [r["woningtype"] for r in result], [TWEEKAP] * 4
        )

    def test_lage_doorlopende_garagedaken_zijn_geen_hoofddaken(self):
        # Lokale aansluitingshoogte is identiek, maar het hoofdgebouw is
        # aan weerszijden minstens 6 meter hoger dan de garages.
        self.assertEqual(
            roof_continuity(
                [4.0] * 6, [4.1] * 6,
                [4.0] * 12, [4.1] * 12,
                main_a=10.0, main_b=10.2,
            ), "bijgebouw"
        )
        # Normale gedeelde kap: hoofdgebouw en grens liggen op zelfde dak.
        self.assertIs(
            roof_continuity(
                [8.0] * 6, [8.1] * 6,
                [8.5] * 12, [8.6] * 12,
                main_a=9.0, main_b=9.2,
            ), True
        )

    def test_twee_huizen_alleen_via_lage_garages_blijven_vrijstaand(self):
        # De garage is onderdeel van dezelfde BAG-pandcontour als het huis.
        # Beide hoofdgebouwen staan los maar de garages verbinden het paar.
        pands = [self._home(), self._home()]
        result = classify_pands(
            pands, {0: {1}, 1: {0}}, {(0, 1): "bijgebouw"}
        )
        self.assertEqual(
            [r["woningtype"] for r in result], [VRIJ, VRIJ]
        )
        self.assertEqual([r["dakbijgeb"] for r in result], [1, 1])
        self.assertIn("niet als hoofddak", result[0]["controle"])

    def test_alleen_garageketting_is_geen_bewijs_voor_rijtjeshuis(self):
        # Bij drie garages op rij kunnen we zonder dakvlakgeometrie niet
        # bepalen welke twee woningen samen één paar vormen.
        pands = [self._home() for _ in range(3)]
        result = classify_pands(
            pands, {0: {1}, 1: {0, 2}, 2: {1}},
            {(0, 1): "bijgebouw", (1, 2): "bijgebouw"}
        )
        self.assertNotIn(TUSSEN, [r["woningtype"] for r in result])
        self.assertEqual(result[1]["dakbijgeb"], 2)

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
