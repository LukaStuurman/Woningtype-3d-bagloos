"""QGIS Processing: woningtypen BAG + selectieve AHN DSM-dakcontrole.

Kaartvenster, eigen gebied en heel Nederland worden als afzonderlijke modi
ondersteund. De verwerking verloopt per tegel, met vaste maximale werkset,
adaptieve splitsing in dichte stedelijke gebieden en precies één uitvoerfeature
per BAG-identificatie op basis van het pandcentrum.
"""
from __future__ import annotations

from collections import deque
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from qgis.PyQt.QtCore import QStandardPaths, QVariant
from qgis.core import (
    QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsFeatureRequest, QgsFeatureSink, QgsField, QgsFields, QgsGeometry,
    QgsProcessingAlgorithm, QgsProcessingException,
    QgsProcessingParameterBoolean, QgsProcessingParameterEnum,
    QgsProcessingParameterExtent, QgsProcessingParameterFeatureSink,
    QgsProcessingParameterNumber, QgsProject, QgsRectangle, QgsSpatialIndex,
    QgsVectorLayer,
)

from .ahn import AhnRoofEvidence
from .classify import (
    classify_pands, excluded_pand, living_pand, normalize_bag_id,
    normalized_text, safe_int,
)
from .tiling import NETHERLANDS_RD, area, subdivide, tile_owns_point, tile_windows
from .styling import WoningtypePostProcessor

PDOK_BAG_WFS = "https://service.pdok.nl/kadaster/bag/wfs/v2_0"
RD = QgsCoordinateReferenceSystem("EPSG:28992")
SURROUNDING_METERS = 25.0
MAX_BUILDINGS_PER_TILE = 30000
MIN_SUBTILE_METERS = 250.0
WRITE_BATCH_SIZE = 1000


def _source():
    uri = (
        "pagingEnabled='true' pageSize='1000' restrictToRequestBBOX='1' "
        "srsname='EPSG:28992' typename='bag:pand' "
        "url='%s' version='2.0.0'" % PDOK_BAG_WFS
    )
    layer = QgsVectorLayer(uri, "BAG panden via PDOK", "WFS")
    if not layer.isValid():
        raise QgsProcessingException(
            "PDOK BAG WFS kan niet worden geopend. "
            "Controleer de verbinding en probeer het later opnieuw."
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


def _bounds(rect):
    return (
        rect.xMinimum(), rect.yMinimum(),
        rect.xMaximum(), rect.yMaximum(),
    )


def _rect(bounds):
    return QgsRectangle(*bounds)


def _processing_extent(parameters, context, algorithm, area_mode):
    if area_mode == 2:
        return QgsRectangle(*NETHERLANDS_RD)

    supplied = parameters.get("EXTENT")
    if supplied not in (None, ""):
        return algorithm.parameterAsExtent(parameters, "EXTENT", context, RD)

    if area_mode == 1:
        raise QgsProcessingException(
            "Kies een onderzoeksgebied bij 'Zelf gekozen gebied'."
        )

    try:
        from qgis.utils import iface
        canvas = iface.mapCanvas() if iface else None
    except (ImportError, AttributeError):
        canvas = None
    if canvas is None:
        raise QgsProcessingException(
            "Zoom naar een onderzoeksgebied in QGIS of geef een extent op."
        )
    source_crs = canvas.mapSettings().destinationCrs()
    rectangle = QgsRectangle(canvas.extent())
    if source_crs.isValid() and source_crs != RD:
        rectangle = QgsCoordinateTransform(
            source_crs, RD, QgsProject.instance()
        ).transformBoundingBox(rectangle)
    return rectangle


def _save_location():
    """Voor landelijke uitvoer nooit alle polygonen in een geheugenlaag bewaren."""
    # PyQt5/QGIS 3 kent soms alleen het directe QStandardPaths-enum.
    enum = getattr(QStandardPaths, "StandardLocation", QStandardPaths)
    where = QStandardPaths.writableLocation(enum.GenericDataLocation)
    if not where:
        raise QgsProcessingException(
            "Geen lokale gegevensmap gevonden. Kies expliciet een GeoPackage-output."
        )
    directory = Path(where) / "Woningtype3DBagloos" / "resultaten"
    directory.mkdir(parents=True, exist_ok=True)
    name = "woningtypen_nederland_%s_%s.gpkg" % (
        datetime.now().strftime("%Y%m%d_%H%M%S"), uuid4().hex[:8]
    )
    return str(directory / name)


def _get_records(bag, fields, tile, overall, feedback):
    """Lees een tegel plus buurbuffer; return None als adaptief splitsen nodig is."""
    request_rect = _rect(tile)
    request_rect.grow(SURROUNDING_METERS)
    request = QgsFeatureRequest().setFilterRect(request_rect)
    selected_fields = [name for name in fields.values() if name]
    request.setSubsetOfAttributes(selected_fields, bag.fields())
    records, local_ids = [], set()

    for feature in bag.getFeatures(request):
        if feedback.isCanceled():
            return []
        if excluded_pand(_value(feature, fields["status"])):
            continue
        geom = feature.geometry()
        if geom is None or geom.isEmpty():
            continue
        identifier = normalize_bag_id(_value(feature, fields["id"]))
        if not identifier or identifier in local_ids:
            continue
        local_ids.add(identifier)
        year = safe_int(_value(feature, fields["year"]), 0)
        records.append({
            "id": identifier,
            "year": year if year > 0 else None,
            "usage": normalized_text(_value(feature, fields["usage"])),
            "count_vbo": safe_int(_value(feature, fields["count"])),
            "geom": QgsGeometry(geom),
        })
        if len(records) > MAX_BUILDINGS_PER_TILE:
            return None
    return records


def _excluded_neighbour(record):
    # Garages, bergingen en andere BAG-panden zonder woonfunctie horen niet
    # in de graaf van aangrenzende HOOFDWONINGEN. De oude check op 1 VBO
    # miste veel garagepanden die nul VBO's hebben.
    return not living_pand(record["usage"])


def _find_neighbours(records, tolerance, feedback):
    spatial = QgsSpatialIndex()
    for idx, record in enumerate(records):
        feature = QgsFeature()
        feature.setId(idx)
        feature.setGeometry(record["geom"])
        spatial.addFeature(feature)

    neighbours = {i: set() for i in range(len(records))}
    for i, record in enumerate(records):
        if feedback.isCanceled():
            return neighbours
        if _excluded_neighbour(record):
            continue
        bounds = QgsRectangle(record["geom"].boundingBox())
        bounds.grow(tolerance)
        for j in spatial.intersects(bounds):
            if j <= i or _excluded_neighbour(records[j]):
                continue
            first, second = record["geom"], records[j]["geom"]
            if first.intersects(second) or first.distance(second) <= tolerance:
                neighbours[i].add(j)
                neighbours[j].add(i)
    return neighbours


def _roof_links(records, neighbours, evidence, feedback):
    links = {}
    for i, neighbours_i in neighbours.items():
        if feedback.isCanceled():
            break
        if not living_pand(records[i]["usage"]) or records[i]["count_vbo"] > 1:
            continue
        for j in neighbours_i:
            if j <= i:
                continue
            if not living_pand(records[j]["usage"]) or records[j]["count_vbo"] > 1:
                continue
            links[i, j] = evidence.check(records[i]["geom"], records[j]["geom"])
    return links


def _result_fields():
    fields = QgsFields()
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
        ("DakBijgeb", QVariant.Int),
        ("DakOnzeker", QVariant.Int),
        ("Controle", QVariant.String),
    ):
        fields.append(QgsField(name, variant))
    return fields


class WoningtypenBepalenAlgorithm(QgsProcessingAlgorithm):
    AREA_MODE = "AREA_MODE"
    EXTENT = "EXTENT"
    MODE = "MODE"
    NATIONAL_AHN = "NATIONAL_AHN"
    TILE_SIZE = "TILE_SIZE"
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
            "Verwerkt het huidige kaartvenster, een gekozen gebied of heel "
            "Nederland. Landelijke verwerking gebeurt in 10-km-tegels (instelbaar), "
            "met adaptieve onderverdeling, lokale ruimtelijke indices en "
            "Geopackage-uitvoer op schijf. De 3DBAG-server wordt niet benaderd.\n"
            "Voor heel Nederland staat extra AHN-hoogtecontrole standaard uit: "
            "die kan miljoenen rasteropvragingen veroorzaken. Zet haar expliciet "
            "aan als je dit toch nodig hebt, of werk eerst BAG-landelijk af "
            "en controleer daarna deelgebieden met AHN.\n"
            "Alle woningtypen zijn indicatief; controleer twijfelgevallen."
        )

    def initAlgorithm(self, config=None):
        self.addParameter(QgsProcessingParameterEnum(
            self.AREA_MODE, "Welk gebied verwerken?",
            options=[
                "Huidig QGIS-kaartvenster",
                "Zelf gekozen gebied",
                "Heel Nederland (tegels, schrijft naar GeoPackage)",
            ],
            defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterExtent(
            self.EXTENT,
            "Kaartvenster of zelfgekozen gebied (niet nodig voor heel Nederland)",
            optional=True
        ))
        self.addParameter(QgsProcessingParameterEnum(
            self.MODE, "Dakcontrolemethode",
            options=[
                "BAG + AHN DSM-dakcontacten uit lokale cache / PDOK",
                "Alleen BAG-pandcontouren (snelste, geen AHN-download)",
            ],
            defaultValue=0
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.NATIONAL_AHN,
            "HEEL NEDERLAND: AHN-hoogtecontrole expliciet inschakelen (zwaar)",
            defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.TILE_SIZE, "BAG-tegelgrootte (meters, standaard 10 km)",
            type=QgsProcessingParameterNumber.Integer,
            minValue=1000, maxValue=10000, defaultValue=10000
        ))
        self.addParameter(QgsProcessingParameterBoolean(
            self.OFFLINE,
            "AHN: uitsluitend eerder gecachte rastertegels gebruiken",
            defaultValue=False
        ))
        self.addParameter(QgsProcessingParameterNumber(
            self.TOLERANCE, "Maximale afstand tussen pandcontouren (m)",
            type=QgsProcessingParameterNumber.Double,
            minValue=0.0, maxValue=1.0, defaultValue=0.20
        ))
        self.addParameter(QgsProcessingParameterFeatureSink(
            self.OUTPUT, "Woningtypen (GeoPackage aanbevolen)"
        ))

    def processAlgorithm(self, parameters, context, feedback):
        area_mode = self.parameterAsEnum(parameters, self.AREA_MODE, context)
        if area_mode not in (0, 1, 2):
            raise QgsProcessingException("Onbekende gebiedsmodus.")
        extent = _processing_extent(parameters, context, self, area_mode)
        if extent.isEmpty() or extent.width() <= 0 or extent.height() <= 0:
            raise QgsProcessingException("Onderzoeksgebied is leeg.")
        bounds = _bounds(extent)
        tile_size = self.parameterAsInt(parameters, self.TILE_SIZE, context)
        tolerance = self.parameterAsDouble(parameters, self.TOLERANCE, context)
        requested_mode = self.parameterAsEnum(parameters, self.MODE, context)
        allow_national_ahn = self.parameterAsBool(
            parameters, self.NATIONAL_AHN, context
        )
        mode = (1 if area_mode == 2 and requested_mode == 0
                and not allow_national_ahn else requested_mode)
        offline = self.parameterAsBool(parameters, self.OFFLINE, context)

        if area_mode == 2 and mode == 1 and requested_mode == 0:
            feedback.pushInfo(
                "Landelijke veiligheidsinstelling: BAG-contouren zonder AHN. "
                "Schakel 'HEEL NEDERLAND: AHN' in voor dakhoogteonderzoek, "
                "of verwerk een kleiner gebied met AHN."
            )
        if area_mode == 2 and mode == 0:
            feedback.pushInfo(
                "WAARSCHUWING: landelijke AHN-controle kan zeer veel WCS-verzoeken "
                "veroorzaken. Caches worden gebruikt, maar de uitvoering blijft zwaar."
            )

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

        output_params = dict(parameters)
        output = output_params.get(self.OUTPUT)
        if area_mode == 2 and (output in (None, "", "TEMPORARY_OUTPUT")
                               or isinstance(output, str)
                               and output.upper() == "TEMPORARY_OUTPUT"):
            output_params[self.OUTPUT] = _save_location()
            feedback.pushInfo(
                "Landelijke uitvoer wordt rechtstreeks naar schijf geschreven: %s"
                % output_params[self.OUTPUT]
            )
        elif area_mode == 2 and isinstance(output, str) and (
                output.lower().startswith("memory:")):
            raise QgsProcessingException(
                "Kies een .gpkg-uitvoer op schijf voor heel Nederland, "
                "geen geheugenlaag."
            )

        result_fields = _result_fields()
        sink, dest_id = self.parameterAsSink(
            output_params, self.OUTPUT, context,
            result_fields, bag.wkbType(), RD
        )
        if sink is None:
            raise QgsProcessingException("Kan uitvoerlaag niet maken.")

        ahn = AhnRoofEvidence(feedback, offline=offline) if mode == 0 else None
        queue = deque(tile_windows(bounds, tile_size))
        total_tiles = len(queue)
        done_area, total_area = 0.0, area(bounds)
        count, uncertain, dense_splits, tiles_done = 0, 0, 0, 0

        feedback.pushInfo(
            "Start %s: %d begintegels van maximaal %d x %d m."
            % (["kaartvenster", "zelfgekozen gebied", "heel Nederland"][area_mode],
               total_tiles, tile_size, tile_size)
        )

        overall_geometry = QgsGeometry.fromRect(extent) if area_mode != 2 else None

        while queue:
            if feedback.isCanceled():
                feedback.pushInfo(
                    "Verwerking geannuleerd; eventuele deels geschreven output "
                    "is onvolledig en mag niet als landelijke dekking worden gebruikt."
                )
                return {}
            tile = queue.popleft()
            records = _get_records(bag, fields, tile, bounds, feedback)
            if records is None:
                if max(tile[2]-tile[0], tile[3]-tile[1]) <= MIN_SUBTILE_METERS:
                    raise QgsProcessingException(
                        "Zelfs de kleinste BAG-tegel bevat te veel panden. "
                        "Verwerking gestopt om RAM-uitputting te vermijden."
                    )
                first, second = subdivide(tile)
                queue.appendleft(second)
                queue.appendleft(first)
                dense_splits += 1
                continue

            neighbours = _find_neighbours(records, tolerance, feedback)
            roof_links = (_roof_links(records, neighbours, ahn, feedback)
                          if ahn is not None else {})
            decisions = classify_pands(
                records, neighbours, roof_links,
                source="AHN" if ahn is not None else "BAG",
            )

            batch = []
            for record, decision in zip(records, decisions):
                geom = record["geom"]
                center = geom.centroid()
                if center.isEmpty():
                    center = geom.pointOnSurface()
                if center.isEmpty():
                    continue
                point = center.asPoint()
                if not tile_owns_point(tile, bounds, point.x(), point.y()):
                    continue
                if overall_geometry is not None and not geom.intersects(overall_geometry):
                    continue

                result = QgsFeature(result_fields)
                result.setGeometry(geom)
                result.setAttributes([
                    record["id"], record["year"], record["usage"],
                    record["count_vbo"], decision["woningtype"],
                    "AHN DSM lokaal" if mode == 0 else "BAG-pandcontouren",
                    decision["dakburen"], decision["dakgetest"],
                    decision["dakverbonden"], decision["dakbijgeb"],
                    decision["dakonzeker"], decision["controle"],
                ])
                batch.append(result)
                count += 1
                if decision["dakonzeker"] and decision["woningtype"]:
                    uncertain += 1
                if len(batch) >= WRITE_BATCH_SIZE:
                    if not sink.addFeatures(batch, QgsFeatureSink.FastInsert):
                        raise QgsProcessingException("Kon een BAG-resultaatbatch niet opslaan.")
                    batch.clear()

            if batch and not sink.addFeatures(batch, QgsFeatureSink.FastInsert):
                raise QgsProcessingException("Kon de laatste BAG-resultaatbatch niet opslaan.")

            tiles_done += 1
            done_area += area(tile)
            feedback.setProgress(min(99.0, 100.0 * done_area / total_area))
            if tiles_done == 1 or tiles_done % 25 == 0:
                feedback.pushInfo(
                    "Tegels gereed: %d (extra gesplitst: %d). Panden opgeslagen: %d. "
                    "Voortgang: %.1f%%"
                    % (tiles_done, dense_splits, count, 100.0*done_area/total_area)
                )

        feedback.setProgress(100)
        # QGIS laadt slechts de ENIGE uitvoersink. Koppel styling uitsluitend
        # aan die output (niet aan de tijdelijke BAG WFS of een tweede laag).
        # De post-processor draait in de GUI-thread zodra QGIS de laag laadt.
        if context.willLoadLayerOnCompletion(dest_id):
            details = context.layerToLoadOnCompletionDetails(dest_id)
            suffix = "AHN-dakcontrole" if mode == 0 else "BAG-contouren"
            details.name = "Woningtypen - %s" % suffix
            details.setPostProcessor(
                WoningtypePostProcessor.create(details.name)
            )
        feedback.pushInfo(
            "Klaar: %d panden opgeslagen uit %d tegels; %d woonpanden "
            "met onzekere AHN-dakcontacten. Uitvoer: %s"
            % (count, tiles_done, uncertain, dest_id)
        )
        return {self.OUTPUT: dest_id}
