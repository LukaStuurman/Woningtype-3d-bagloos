"""QGIS Processing-algoritme: BAG panden + lokaal afgeleide AHN-dakcontacten."""
from __future__ import annotations

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsFeatureRequest, QgsFeatureSink, QgsField, QgsFields, QgsGeometry,
    QgsProcessing, QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterBoolean, QgsProcessingParameterEnum,
    QgsProcessingParameterExtent, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber, QgsProject, QgsRectangle,
    QgsSpatialIndex, QgsVectorLayer,
)

from .ahn import AhnRoofEvidence
from .classify import (
    classify_pands, excluded_pand, living_pand, normalize_bag_id,
    normalized_text, safe_int,
)

PDOK_BAG_WFS = "https://service.pdok.nl/kadaster/bag/wfs/v2_0"
RD = QgsCoordinateReferenceSystem("EPSG:28992")
MAX_BUILDINGS = 30000
SURROUNDING_METERS = 25.0


def _source():
    uri = (
        "pagingEnabled='true' pageSize='1000' restrictToRequestBBOX='1' "
        "srsname='EPSG:28992' typename='bag:pand' "
        "url='%s' version='2.0.0'" % PDOK_BAG_WFS
    )
    layer = QgsVectorLayer(uri, "BAG panden via PDOK", "WFS")
    if not layer.isValid():
        raise QgsProcessingException(
            "BAG WFS kon niet worden geopend. Controleer internet of probeer opnieuw."
        )
    return layer


def _field_name(layer, *candidates):
    names = {field.name().casefold(): field.name() for field in layer.fields()}
    for candidate in candidates:
        if candidate.casefold() in names:
            return names[candidate.casefold()]
    return None


def _value(feature, field):
    return feature.attribute(field) if field is not None else None


def _processing_extent(parameters, context, algorithm):
    provided = parameters.get("EXTENT")
    if provided not in (None, ""):
        return algorithm.parameterAsExtent(parameters, "EXTENT", context, RD)
    try:
        from qgis.utils import iface
        canvas = iface.mapCanvas() if iface else None
    except (ImportError, AttributeError):
        canvas = None
    if canvas is None:
        raise QgsProcessingException(
            "Geef een onderzoeksgebied op (EPSG:28992) of start vanuit de QGIS-kaart."
        )
    source_crs = canvas.mapSettings().destinationCrs()
    rectangle = QgsRectangle(canvas.extent())
    if source_crs != RD:
        rectangle = QgsCoordinateTransform(
            source_crs, RD, QgsProject.instance()
        ).transformBoundingBox(rectangle)
    return rectangle


class WoningtypenBepalenAlgorithm(QgsProcessingAlgorithm):
    EXTENT = "EXTENT"
    MODE = "MODE"
    OFFLINE = "OFFLINE"
    TOLERANCE = "TOLERANCE"
    OUTPUT = "OUTPUT"

    def createInstance(self):
        return WoningtypenBepalenAlgorithm()

    def name(self):
        return "bepaal_woningtypen"

    def displayName(self):
        return "Bepaal woningtypen met BAG en lokaal AHN"

    def group(self):
        return "Woningtype 3D-bagloos"

    def groupId(self):
        return "woningtypen"

    def shortHelpString(self):
        return (
            "Bepaalt pandwoningtypen uitsluitend met BAG-pandcontouren en kleine "
            "AHN DSM-hoogtetermijnen. De 3DBAG-server wordt nooit gebruikt.\n"
            "Het resultaat is indicatief: controleer AHN-onzekerheden en "
            "afwijkende daken vóór gebruik bij ontwerpstroomberekeningen."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterExtent(
            self.EXTENT,
            "Onderzoeksgebied (leeg = huidige kaartuitsnede)",
            optional=True
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.MODE,
            "Dakcontrolemethode",
            options=[
                "BAG + lokaal afgeleide AHN DSM-dakcontacten (aanbevolen)",
                "Alleen BAG-pandcontouren (geen AHN-download)",
            ],
            defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.OFFLINE,
            "AHN: alleen bestaande lokaal gecachte tegels gebruiken",
            defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.TOLERANCE,
            "Maximale afstand aangrenzende pandcontouren (m)",
            type=QgsProcessingParameterNumber.Double,
            minValue=0.0, maxValue=1.0, defaultValue=0.20
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Woningtypen (polygonen)"
        ))

    def processAlgorithm(self, parameters, context, feedback):
        extent = _processing_extent(parameters, context, self)
        if extent.isEmpty() or extent.width() <= 0 or extent.height() <= 0:
            raise QgsProcessingException("Het gekozen onderzoeksgebied is leeg.")
        if extent.width() * extent.height() > 100000000:
            raise QgsProcessingException(
                "Kies een gebied van maximaal 100 km² per verwerking. "
                "Gebruik meerdere kleine gebieden voor grotere projecten."
            )

        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        mode = self.parameterAsEnum(parameters, self.MODE, context)
        offline = self.parameterAsBool(parameters, self.OFFLINE, context)
        bag = _source()
        fields = {
            "id": _field_name(bag, "identificatie"),
            "year": _field_name(bag, "bouwjaar", "oorspronkelijk_bouwjaar"),
            "usage": _field_name(bag, "gebruiksdoel"),
            "count": _field_name(bag, "aantal_verblijfsobjecten"),
            "status": _field_name(bag, "status"),
        }
        if not all(fields[key] for key in ("id", "usage", "count")):
            raise QgsProcessingException(
                "BAG WFS mist identificatie, gebruiksdoel of aantal_verblijfsobjecten."
            )

        query = QgsRectangle(extent)
        query.grow(SURROUNDING_METERS)
        feedback.pushInfo("BAG-pandcontouren ophalen inclusief %.0fm buurbuffer"
                          % SURROUNDING_METERS)
        request = QgsFeatureRequest().setFilterRect(query)
        records = []
        seen = set()
        for feature in bag.getFeatures(request):
            if feedback.isCanceled():
                return {}
            if excluded_pand(_value(feature, fields["status"])):
                continue
            geom = feature.geometry()
            if geom is None or geom.isEmpty():
                continue
            identifier = normalize_bag_id(_value(feature, fields["id"]))
            if not identifier:
                continue
            if identifier in seen:
                continue
            seen.add(identifier)
            raw_year = safe_int(_value(feature, fields["year"]), 0)
            records.append({
                "id": identifier,
                "year": raw_year if raw_year > 0 else None,
                "usage": normalized_text(_value(feature, fields["usage"])),
                "count_vbo": safe_int(_value(feature, fields["count"])),
                "geom": QgsGeometry(geom),
                "output": geom.intersects(QgsGeometry.fromRect(extent)),
            })
            if len(records) > MAX_BUILDINGS:
                raise QgsProcessingException(
                    "Meer dan %d BAG-panden gevonden. Zoom verder in en probeer opnieuw."
                    % MAX_BUILDINGS
                )
        feedback.pushInfo("BAG-pandcontouren: %d gevonden" % len(records))

        # Ruimtelijke index: alleen echte naburen, geen O(n²)-vergelijkingen.
        index = QgsSpatialIndex()
        for i, record in enumerate(records):
            feat = QgsFeature()
            feat.setId(i)
            feat.setGeometry(record["geom"])
            index.addFeature(feat)
        neighbours = {i: set() for i in range(len(records))}
        for i, record in enumerate(records):
            if feedback.isCanceled():
                return {}
            if record["usage"] == "" or (
                "overige" in record["usage"].casefold()
                and not living_pand(record["usage"])
                and record["count_vbo"] == 1
            ):
                continue
            bbox = QgsRectangle(record["geom"].boundingBox())
            bbox.grow(tolerance)
            for j in index.intersects(bbox):
                if j <= i:
                    continue
                other = records[j]
                if other["usage"] == "" or (
                    "overige" in other["usage"].casefold()
                    and not living_pand(other["usage"])
                    and other["count_vbo"] == 1
                ):
                    continue
                g1, g2 = record["geom"], other["geom"]
                if g1.intersects(g2) or g1.distance(g2) <= tolerance:
                    neighbours[i].add(j)
                    neighbours[j].add(i)
            if i % 200 == 0:
                feedback.setProgress(int(35 * i / max(1, len(records))))

        roof_links = {}
        mode_source = "AHN" if mode == 0 else "BAG"
        if mode == 0:
            ahn = AhnRoofEvidence(feedback, offline=offline)
            candidate_pairs = [
                (i, j)
                for i, nset in neighbours.items()
                for j in sorted(nset)
                if j > i
                and living_pand(records[i]["usage"])
                and living_pand(records[j]["usage"])
                and records[i]["count_vbo"] <= 1
                and records[j]["count_vbo"] <= 1
            ]
            feedback.pushInfo(
                "AHN: alleen %d gedeelde woonpandgrenzen controleren; "
                "geen 3DBAG-requests" % len(candidate_pairs)
            )
            for num, (i, j) in enumerate(candidate_pairs, 1):
                if feedback.isCanceled():
                    return {}
                roof_links[i, j] = ahn.check(
                    records[i]["geom"], records[j]["geom"]
                )
                if num % 10 == 0 or num == len(candidate_pairs):
                    feedback.setProgress(35 + int(55 * num / max(1, len(candidate_pairs))))
            feedback.pushInfo(
                "AHN: %d rastertegels gedownload, %d contacten gecontroleerd"
                % (ahn.downloads, len(candidate_pairs))
            )

        decisions = classify_pands(records, neighbours, roof_links, mode_source)
        result_fields = QgsFields()
        for name, variant in (
            ("identificatie", QVariant.String),
            ("bouwjaar", QVariant.Int),
            ("gebruiksdoel", QVariant.String),
            ("aantal_vbo", QVariant.Int),
            ("Woningtype", QVariant.String),
            ("Dakbron", QVariant.String),
            ("DakBuren", QVariant.Int),
            ("DakGetest", QVariant.Int),
            ("DakVerbonden", QVariant.Int),
            ("DakOnzeker", QVariant.Int),
            ("Controle", QVariant.String),
        ):
            result_fields.append(QgsField(name, variant))

        sink, destination = self.parameterAsSink(
            parameters, self.OUTPUT, context,
            result_fields, bag.wkbType(), RD
        )
        if sink is None:
            raise QgsProcessingException("Kon de uitvoerlaag niet schrijven.")

        written, uncertain = 0, 0
        for record, decision in zip(records, decisions):
            if feedback.isCanceled():
                return {}
            if not record["output"]:
                continue
            result = QgsFeature(result_fields)
            result.setGeometry(record["geom"])
            result.setAttributes([
                record["id"], record["year"], record["usage"],
                record["count_vbo"], decision["woningtype"],
                "AHN DSM lokaal" if mode == 0 else "BAG-pandcontouren",
                decision["dakburen"], decision["dakgetest"],
                decision["dakverbonden"], decision["dakonzeker"],
                decision["controle"],
            ])
            if not sink.addFeature(result, QgsFeatureSink.FastInsert):
                raise QgsProcessingException("Schrijven van een BAG-pand mislukt.")
            written += 1
            if decision["dakonzeker"] and decision["woningtype"]:
                uncertain += 1
        feedback.setProgress(100)
        feedback.pushInfo(
            "Klaar: %d panden, waaronder %d woonpanden met onzekere "
            "AHN-dakcontacten." % (written, uncertain)
        )
        return {self.OUTPUT: destination}
