"""Conservative evidence for single-storey homes linked by flat carports.

VBO points are anchors, not dwelling polygons and not proof of floor level.
Require low height above AHN DTM AND distinct substantial raised roof patches
AND a deeply indented footprint. Ordinary rectangular terraces keep the normal
roof-contact analysis. Missing evidence never silently changes an apartment.
"""
import json
from datetime import date
from hashlib import sha256, blake2b
from math import hypot
from pathlib import Path
from urllib.parse import urlencode, urljoin
from urllib.request import Request, urlopen

from qgis.PyQt.QtCore import QStandardPaths
from qgis.core import QgsGeometry, QgsPointXY, QgsRectangle

from .ahn import AhnRoofEvidence
from .segmentation import quantile

VBO_URL = "https://api.pdok.nl/kadaster/bag/ogc/v2/collections/verblijfsobject/items"
RD_URI = "http://www.opengis.net/def/crs/EPSG/0/28992"


def has_recesses(geom):
    hull = geom.convexHull().area()
    return hull > 0 and geom.area()/hull <= .82


def flat_candidate(geom, zones):
    if zones is None or not zones.reliable:
        return False
    values = list(zones.samples.values())
    low, middle, high = (quantile(values, q) for q in (.1, .5, .9))
    return (has_recesses(geom)
            and .3 <= high-middle <= 1.0 and high-low <= 1.5)


def load_vbos(bounds, feedback, offline=False):
    """Return original RD GeoJSON, with bounded paging and a daily local cache."""
    bbox = ",".join("%.2f" % v for v in bounds)
    key = sha256(bbox.encode()).hexdigest()[:20]
    enum = getattr(QStandardPaths, "StandardLocation", QStandardPaths)
    cache = Path(QStandardPaths.writableLocation(enum.GenericDataLocation)) / "Woningtype3DBagloos" / "vbo_v1"
    cache.mkdir(parents=True, exist_ok=True)
    path = cache / (date.today().isoformat() + "_" + key + ".json")
    if path.exists():
        return json.loads(path.read_text())
    if offline:
        previous = sorted(cache.glob("*_" + key + ".json"))
        return json.loads(previous[-1].read_text()) if previous else None
    url = VBO_URL + "?" + urlencode({"bbox": bbox, "bbox-crs": RD_URI,
                                     "crs": RD_URI, "f": "json", "limit": 1000})
    features, visited = [], set()
    while url:
        if feedback.isCanceled():
            return None
        if url in visited or len(features) >= 30000:
            raise ValueError("VBO-paginering overschrijdt de lokale werkset")
        visited.add(url)
        request = Request(url, headers={"Accept": "application/geo+json"})
        with urlopen(request, timeout=25) as response:
            payload = response.read(20 * 1024 * 1024 + 1)
        if len(payload) > 20 * 1024 * 1024:
            raise ValueError("VBO-antwoord te groot")
        data = json.loads(payload)
        features.extend(data.get("features", []))
        next_link = next((l["href"] for l in data.get("links", []) if l.get("rel") == "next"), None)
        url = urljoin(url, next_link) if next_link else None
        if url and not url.startswith(VBO_URL + "?"):
            raise ValueError("Onverwachte VBO-vervolglink")
    data = {"type": "FeatureCollection", "features": features}
    partial = path.with_suffix(".part")
    partial.write_text(json.dumps(data))
    partial.replace(path)
    return data


def refine_home(record, zones, anchors, ground):
    """Return True only if every registered home has its own supported patch."""
    if not flat_candidate(record["geom"], zones):
        return False
    count = record["count_vbo"]
    if not 1 <= count <= 2 or len(anchors) != count:
        return False
    high = quantile(list(zones.samples.values()), .9)
    # AHN DTM masks buildings. Use actual terrain samples outside the footprint,
    # including courtyards, rather than requiring terrain underneath a roof.
    box = record["geom"].boundingBox()
    box.grow(3)
    terrain = []
    for j in range(9):
        y = box.yMinimum() + j*box.height()/8
        for i in range(9):
            x = box.xMinimum() + i*box.width()/8
            if record["geom"].intersects(QgsGeometry.fromPointXY(QgsPointXY(x, y))):
                continue
            h = ground.height(x, y)
            if h is not None:
                terrain.append(h)
    if (len(terrain) < 6 or quantile(terrain, .9)-quantile(terrain, .1) > 1
            or not 1.8 <= high-quantile(terrain, .5) <= 4.5):
        return False
    remaining = {p for p, h in zones.samples.items() if h >= high-.15}
    components = []
    while remaining:
        seed = remaining.pop()
        component, queue = {seed}, [seed]
        while queue:
            x, y = queue.pop()
            for p in ((x-1, y), (x+1, y), (x, y-1), (x, y+1)):
                if p in remaining:
                    remaining.remove(p)
                    component.add(p)
                    queue.append(p)
        if len(component)*zones.spacing**2 >= max(12, record["geom"].area()*.05):
            components.append(component)
    if len(components) != count:
        return False
    matched = set()
    for anchor in anchors:
        distances = [min(hypot(zones.origin[0]+(x+.5)*zones.spacing-anchor.x(),
                               zones.origin[1]+(y+.5)*zones.spacing-anchor.y())
                         for x, y in component) for component in components]
        index = min(range(len(distances)), key=distances.__getitem__)
        if distances[index] > 3 or index in matched:
            return False
        matched.add(index)
    if count == 2:
        # A tiny offset in duplicated/stacked VBO points is not horizontal
        # separation. Require genuinely separated, independently anchored roofs.
        if hypot(anchors[0].x()-anchors[1].x(), anchors[0].y()-anchors[1].y()) < 8:
            return False
    zones.threshold = high-.15
    zones.main = set().union(*components)
    record["flat_roof_evidence"] = True
    record["home_evidence"] = "indicatieve dakdelen: VBO + AHN DSM/DTM; BAG-aantal VBO behouden"
    return True


def prepare_homes(records, roof, feedback, offline=False, vbo_data=None, ground=None):
    roof.roof_levels.clear()
    roof.refinements.clear()
    candidates = [r for r in records if "woonfunctie" in r["usage"].casefold()
                  and 1 <= r["count_vbo"] <= 2
                  and has_recesses(r["geom"])
                  and flat_candidate(r["geom"], roof.roof_zones(r["geom"]))]
    if not candidates:
        return
    box = QgsRectangle()
    for r in candidates:
        box.combineExtentWith(r["geom"].boundingBox())
    box.grow(1)
    try:
        data = vbo_data if vbo_data is not None else load_vbos(
            (box.xMinimum(), box.yMinimum(), box.xMaximum(), box.yMaximum()), feedback, offline)
        if data is None:
            feedback.pushInfo("Gelijkvloerse woningen: geen lokaal VBO-bewijs beschikbaar; normale beoordeling behouden.")
            return
        points = []
        seen = set()
        for f in data.get("features", []):
            props = f.get("properties", {})
            ident = props.get("identificatie")
            if (not ident or ident in seen or "woonfunctie" not in str(props.get("gebruiksdoel", ""))
                    or props.get("status") not in ("Verblijfsobject in gebruik", "Verblijfsobject in gebruik (niet ingemeten)")):
                continue
            xy = f["geometry"]["coordinates"]
            points.append(QgsPointXY(xy[0], xy[1]))
            seen.add(ident)
        if ground is None:
            ground = AhnRoofEvidence(feedback, offline=offline, coverage="dtm_05m")
        for r in candidates:
            anchors = [p for p in points if r["geom"].contains(QgsGeometry.fromPointXY(p))]
            if refine_home(r, roof.roof_zones(r["geom"]), anchors, ground):
                key = blake2b(bytes(r["geom"].asWkb()), digest_size=12).digest()
                roof.refinements[key] = lambda zones, r=r, anchors=anchors: refine_home(r, zones, anchors, ground)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        feedback.reportError("Aanvullend VBO/maaiveldonderzoek niet beschikbaar: %s; normale beoordeling behouden." % exc)
