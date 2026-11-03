"""Handmatige CI-smoketest in een echte QGIS 4-container (zonder webrequests)."""
import tempfile
from unittest.mock import patch

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsApplication, QgsFeature, QgsField, QgsGeometry,
    QgsProcessingContext, QgsProcessingFeedback, QgsProject,
    QgsRectangle, QgsVectorLayer,
)

app = QgsApplication([], False)
app.initQgis()
try:
    from woningtype_3d_bagloos.ahn import AhnRoofEvidence, _roof_cross_sections
    from woningtype_3d_bagloos.classify import TWEEKAP, VRIJ
    from woningtype_3d_bagloos.plugin import WoningtypeBagloosProvider
    from woningtype_3d_bagloos.processor import WoningtypenBepalenAlgorithm

    a = QgsGeometry.fromWkt(
        "POLYGON((100 200,110 200,110 210,100 210,100 200))"
    )
    b = QgsGeometry.fromWkt(
        "POLYGON((110 200,120 200,120 210,110 210,110 200))"
    )
    assert len(_roof_cross_sections(a, b)) >= 3, "Grensprofiel niet gevonden"

    with tempfile.TemporaryDirectory() as cache:
        ahn = AhnRoofEvidence(
            QgsProcessingFeedback(), cache_dir=cache, offline=True
        )
        ahn.height = lambda x, y: 7.0
        assert ahn.check(a, b) is True, "AHN-dakcontact test niet geslaagd"

    bag = QgsVectorLayer("Polygon?crs=EPSG:28992", "Fictieve BAG", "memory")
    bag.dataProvider().addAttributes([
        QgsField("identificatie", QVariant.String),
        QgsField("bouwjaar", QVariant.Int),
        QgsField("gebruiksdoel", QVariant.String),
        QgsField("aantal_verblijfsobjecten", QVariant.Int),
        QgsField("status", QVariant.String),
    ])
    bag.updateFields()
    for n, geom in enumerate((a, b)):
        f = QgsFeature(bag.fields())
        f.setGeometry(geom)
        f.setAttributes([
            "000000000000%04d" % n, 2024,
            "woonfunctie", 1, "Pand in gebruik",
        ])
        assert bag.dataProvider().addFeatures([f])[0]
    bag.updateExtents()

    provider = WoningtypeBagloosProvider()
    provider.loadAlgorithms()
    assert len(provider.algorithms()) == 1
    algorithm = WoningtypenBepalenAlgorithm()
    algorithm.initAlgorithm()
    assert {p.name() for p in algorithm.parameterDefinitions()} == {
        "EXTENT", "MODE", "OFFLINE", "TOLERANCE", "OUTPUT",
    }

    context = QgsProcessingContext()
    context.setProject(QgsProject.instance())
    feedback = QgsProcessingFeedback()
    parameters = {
        "EXTENT": QgsRectangle(98, 198, 122, 212),
        "MODE": 1, "OFFLINE": True, "TOLERANCE": 0.20,
        "OUTPUT": "memory:",
    }
    with patch("woningtype_3d_bagloos.processor._source", return_value=bag):
        output, ok = algorithm.run(parameters, context, feedback)
    assert ok, output
    layer = context.temporaryLayerStore().mapLayer(output["OUTPUT"])
    assert layer and layer.isValid()
    features = list(layer.getFeatures())
    assert len(features) == 2
    assert all(f["Woningtype"] == TWEEKAP for f in features)
    assert all(f["bouwjaar"] == 2024 for f in features)

    # Ook het afwijkende dakcontactpad, zonder netwerkverzoeken.
    context2 = QgsProcessingContext()
    context2.setProject(QgsProject.instance())
    algorithm2 = WoningtypenBepalenAlgorithm()
    algorithm2.initAlgorithm()
    parameters["MODE"] = 0
    with patch("woningtype_3d_bagloos.processor._source", return_value=bag):
        with patch("woningtype_3d_bagloos.processor.AhnRoofEvidence.check", return_value=False):
            result, ok = algorithm2.run(parameters, context2, feedback)
    assert ok, result
    second = context2.temporaryLayerStore().mapLayer(result["OUTPUT"])
    assert second is not None
    assert [f["Woningtype"] for f in second.getFeatures()] == [VRIJ, VRIJ]
    print("QGIS 4 processing, polygonen, AHN-doorsnede en classificatie: OK")
finally:
    app.exitQgis()
