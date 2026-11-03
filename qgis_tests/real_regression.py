"""The 27 actual screenshot buildings, original BAG and freshly captured AHN.

No generated contours, mocked heights or hand-authored roof links. The only
substitutions route network I/O to the versioned original PDOK snapshots.
"""
import json
import os
import sys
import tempfile
from collections import Counter
from hashlib import sha256
from pathlib import Path
from unittest.mock import patch

from qgis.core import (Qgis, QgsApplication, QgsCategorizedSymbolRenderer,
                       QgsProcessingContext, QgsProcessingFeedback, QgsProject,
                       QgsRectangle, QgsVectorLayer)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "qgis_tests" / "data"
sys.path.insert(0, str(ROOT))
app = QgsApplication([], False)
app.initQgis()
sys.path.append(str(Path(QgsApplication.pkgDataPath()) / "python" / "plugins"))
from processing.core.Processing import Processing
Processing.initialize()
import processing
from woningtype_3d_bagloos.ahn import AhnRoofEvidence
from woningtype_3d_bagloos.plugin import WoningtypeBagloosProvider
from woningtype_3d_bagloos.processor import _find_neighbours, _roof_links
from woningtype_3d_bagloos.classify import classify_pands


def run():
    manifest = json.loads((DATA / "provenance.json").read_text())
    for name, digest in manifest["files"].items():
        assert sha256((DATA / name).read_bytes()).hexdigest() == digest, name
    expected = json.loads((DATA / "expected.json").read_text())
    bag = QgsVectorLayer(str(DATA / "bag.geojson"), "PDOK BAG snapshot", "ogr")
    assert bag.isValid() and bag.featureCount() == 27
    feedback = QgsProcessingFeedback()
    records = [{"id": f["identificatie"], "usage": f["gebruiksdoel"],
                "count_vbo": f["aantal_verblijfsobjecten"], "geom": f.geometry()}
               for f in bag.getFeatures()]
    neighbours = _find_neighbours(records, .2, feedback)
    roof = AhnRoofEvidence(feedback, offline=True, cache_dir=DATA / "ahn")
    links = _roof_links(records, neighbours, roof, feedback)
    decisions = classify_pands(records, neighbours, links)
    for r, d in zip(records, decisions):
        assert d["woningtype"] == expected[r["id"]]["woningtype"], (r["id"], d)
        assert d["dakonzeker"] == 0, (r["id"], d)
    # Repeat under reversed feature ordering and swapped contact orientation.
    for (i, j), value in links.items():
        assert roof.check(records[j]["geom"], records[i]["geom"]) == value, (i, j)
    reverse = list(reversed(records))
    reverse_neighbours = _find_neighbours(reverse, .2, feedback)
    reverse_links = _roof_links(reverse, reverse_neighbours, roof, feedback)
    for r, d in zip(reverse, classify_pands(reverse, reverse_neighbours, reverse_links)):
        assert d["woningtype"] == expected[r["id"]]["woningtype"], (r["id"], d)

    provider = WoningtypeBagloosProvider()
    assert QgsApplication.processingRegistry().addProvider(provider)
    project = QgsProject.instance()
    sentinel = QgsVectorLayer("Point?crs=EPSG:28992", "Existing source", "memory")
    project.addMapLayer(sentinel)

    def snapshot_evidence(*args, **kwargs):
        return AhnRoofEvidence(args[0], offline=True, cache_dir=DATA / "ahn")

    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as directory:
        # Real Processing execution, output finalization, loading and automatic
        # post-processing. No manual styling or empty-layer cleanup in this test.
        for n, destination in enumerate(("TEMPORARY_OUTPUT", str(Path(directory) / "real.gpkg"))):
            before = set(project.mapLayers())
            context = QgsProcessingContext()
            context.setProject(project)
            with patch("woningtype_3d_bagloos.processor._source", return_value=bag), \
                    patch("woningtype_3d_bagloos.processor.AhnRoofEvidence", side_effect=snapshot_evidence):
                processing.runAndLoadResults("woningtypebagloos:bepaal_woningtypen", {
                    "AREA_MODE": 1, "EXTENT": QgsRectangle(162260, 388275, 162620, 388465),
                    "MODE": 0, "OFFLINE": True, "TOLERANCE": .2,
                    "TILE_SIZE": 1000, "OUTPUT": destination,
                }, context=context, feedback=feedback)
            created = set(project.mapLayers()) - before
            assert len(created) == 1, created
            layer = project.mapLayer(created.pop())
            assert layer.isValid() and layer.featureCount() == 27
            assert isinstance(layer.renderer(), QgsCategorizedSymbolRenderer)
            assert layer.renderer().classAttribute() == "Woningtype"
            features = list(layer.getFeatures())
            assert len({f["identificatie"] for f in features}) == 27
            for f in features:
                assert f["Woningtype"] == expected[f["identificatie"]]["woningtype"], f.attributes()
                assert f["DakOnzeker"] == 0, f.attributes()
            assert project.mapLayer(sentinel.id()) is sentinel
            project.removeMapLayer(layer.id())
    project.removeMapLayer(sentinel.id())
    print("QGIS", Qgis.QGIS_VERSION, "real BAG/AHN: 27/27; reversed order/orientation;",
          "memory + GeoPackage: exactly one automatically styled layer", flush=True)
    print(dict(Counter((expected[r["id"]]["case"], d["woningtype"])
                       for r, d in zip(records, decisions))), flush=True)


try:
    run()
finally:
    QgsProject.instance().clear()
    app.exitQgis()
