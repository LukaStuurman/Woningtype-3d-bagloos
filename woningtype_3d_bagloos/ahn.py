"""AHN DSM: alleen kleine hoogtevensters rond gedeelde BAG-pandgrenzen.

Geen afhankelijkheid van 3DBAG, pdal, scipy, rasterio of een lokaal
volledig 3D-model. QGIS/GDAL leest de gecachte GeoTIFF-bestanden.
"""
from __future__ import annotations

from collections import OrderedDict
from hashlib import blake2b
from math import ceil, floor, hypot, isfinite, sqrt
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from qgis.PyQt.QtCore import QStandardPaths
from qgis.core import QgsGeometry, QgsPointXY, QgsRasterLayer

from .segmentation import RoofZones

WCS_URL = "https://service.pdok.nl/rws/ahn/wcs/v1_0"
COVERAGE = "dsm_05m"
TILE_SIZE = 64
CACHE_VERSION = "wcs_dsm_05m_64m_v1"
MAX_TILE_BYTES = 7 * 1024 * 1024
MAX_FAILED_REQUESTS = 3


def _segments(line):
    """Haal lijnsegmenten uit LineString/MultiLineString/GeometryCollection."""
    if line.isEmpty():
        return []
    if line.isMultipart():
        candidates = line.asGeometryCollection()
    else:
        candidates = [line]
    segments = []
    for geom in candidates:
        try:
            vertices = geom.asPolyline()
        except (TypeError, ValueError):
            continue
        for p, q in zip(vertices, vertices[1:]):
            length = hypot(q.x() - p.x(), q.y() - p.y())
            if length >= 0.7:
                segments.append((p, q, length))
    return sorted(segments, key=lambda item: -item[2])


def _point_in(poly, x, y):
    return poly.contains(QgsGeometry.fromPointXY(QgsPointXY(x, y)))


def _roof_cross_sections(a, b):
    """Meet alleen in het midden van een gedeelde/zeer nabije pandgrens."""
    if a.isEmpty() or b.isEmpty():
        return []
    # QgsGeometry.boundary() bestaat niet in alle QGIS 3/4 Python-bindings.
    # Gebruik rechtstreeks de buitenring(en) van de BAG-polygoon.
    try:
        polygons = a.asMultiPolygon() if a.isMultipart() else [a.asPolygon()]
    except (TypeError, ValueError):
        return []
    segments = []
    buffer_b = b.buffer(0.5, 5)
    for polygon in polygons:
        if not polygon or not polygon[0]:
            continue
        ring = QgsGeometry.fromPolylineXY(polygon[0])
        segments.extend(_segments(ring.intersection(buffer_b)))
    result = []
    for start, end, length in sorted(segments, key=lambda entry: -entry[2]):
        count = min(128, max(2, ceil(length / 0.5)))
        dx, dy = (end.x()-start.x())/length, (end.y()-start.y())/length
        nx, ny = -dy, dx
        for step in range(count):
            if len(result) >= 512:
                return result
            ratio = (step + 0.5)/count
            x = start.x() + ratio*(end.x()-start.x())
            y = start.y() + ratio*(end.y()-start.y())
            for sign in (1, -1):
                nxa, nya = sign*nx, sign*ny
                if (_point_in(a, x+nxa*1.25, y+nya*1.25)
                        and _point_in(b, x-nxa*1.25, y-nya*1.25)):
                    result.append((x, y, nxa, nya))
                    break
    return result


class AhnRoofEvidence:
    """Een lokale rastercache wordt gedeeld tussen opeenvolgende QGIS-runs."""

    def __init__(self, feedback, offline=False, cache_dir=None):
        self.feedback = feedback
        self.offline = bool(offline)
        if cache_dir is None:
            enum = getattr(QStandardPaths, "StandardLocation", QStandardPaths)
            data = QStandardPaths.writableLocation(enum.GenericDataLocation)
            if not data:
                raise RuntimeError("Geen beschrijfbare gebruikersmap voor AHN-cache")
            cache_dir = Path(data) / "Woningtype3DBagloos" / CACHE_VERSION
        self.cache = Path(cache_dir)
        self.cache.mkdir(parents=True, exist_ok=True)
        self.rasters = OrderedDict()
        self.roof_levels = OrderedDict()
        self.unavailable = set()
        self.failed = 0
        self.downloads = 0
        self.first_warning_sent = False

    def _path(self, key):
        return self.cache / ("dsm_%d_%d.tif" % key)

    def _download(self, key, destination):
        if self.offline or self.failed >= MAX_FAILED_REQUESTS:
            return False
        xmin, ymin = key[0] * TILE_SIZE, key[1] * TILE_SIZE
        params = [
            ("service", "WCS"), ("version", "2.0.1"), ("request", "GetCoverage"),
            ("coverageId", COVERAGE), ("format", "image/tiff"),
            ("subset", "x(%.1f,%.1f)" % (xmin-1.0, xmin+TILE_SIZE+1.0)),
            ("subset", "y(%.1f,%.1f)" % (ymin-1.0, ymin+TILE_SIZE+1.0)),
        ]
        url = WCS_URL + "?" + urlencode(params)
        partial = destination.with_suffix(".part")
        try:
            req = Request(url, headers={
                "Accept": "image/tiff", "User-Agent": "QGIS-Woningtype-3d-bagloos/0.1"
            })
            with urlopen(req, timeout=25) as response, partial.open("wb") as stream:
                bytecount = 0
                while True:
                    if self.feedback.isCanceled():
                        return False
                    chunk = response.read(65536)
                    if not chunk:
                        break
                    bytecount += len(chunk)
                    if bytecount > MAX_TILE_BYTES:
                        raise ValueError("AHN-tegel groter dan veiligheidslimiet")
                    stream.write(chunk)
            with partial.open("rb") as stream:
                prefix = stream.read(4)
            if prefix not in (b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"):
                raise ValueError("AHN WCS leverde geen TIFF")
            partial.replace(destination)
            self.downloads += 1
            if self.downloads == 1 or self.downloads % 25 == 0:
                self.feedback.pushInfo(
                    "AHN DSM: %d kleine tegels gedownload en lokaal gecachet (%s)"
                    % (self.downloads, self.cache)
                )
            return True
        except Exception as exc:
            self.failed += 1
            if not self.first_warning_sent:
                self.feedback.reportError(
                    "AHN-hoogtegegevens (tijdelijk) niet beschikbaar: %s. "
                    "Onzekere dakcontacten krijgen een controlemarkering." % exc
                )
                self.first_warning_sent = True
            return False
        finally:
            if partial.exists():
                partial.unlink()

    def _raster(self, x, y):
        key = floor(x / TILE_SIZE), floor(y / TILE_SIZE)
        if key in self.unavailable:
            return None
        if key in self.rasters:
            self.rasters.move_to_end(key)
            return self.rasters[key]
        path = self._path(key)
        if not path.exists() and not self._download(key, path):
            self.unavailable.add(key)
            return None
        raster = QgsRasterLayer(str(path), "AHN DSM (cache)", "gdal")
        if not raster.isValid():
            self.unavailable.add(key)
            return None
        self.rasters[key] = raster
        if len(self.rasters) > 10:
            self.rasters.popitem(last=False)
        return raster

    def height(self, x, y):
        raster = self._raster(x, y)
        if raster is None:
            return None
        value, valid = raster.dataProvider().sample(QgsPointXY(x, y), 1)
        if not valid or not isfinite(value) or value <= -100 or value >= 1000:
            return None
        return float(value)

    def roof_zones(self, geom):
        """Sample the actual footprint at 0.5 m; cache spatial roof components."""
        if geom.isEmpty():
            return None
        key = blake2b(bytes(geom.asWkb()), digest_size=12).digest()
        if key in self.roof_levels:
            self.roof_levels.move_to_end(key)
            return self.roof_levels[key]
        rect = geom.boundingBox()
        spacing = max(.5, sqrt(rect.width() * rect.height() / 4096.0))
        if rect.width() <= 0 or rect.height() <= 0:
            return None
        origin = rect.xMinimum(), rect.yMinimum()
        samples, expected = {}, 0
        for j in range(ceil(rect.height()/spacing)):
            if self.feedback.isCanceled():
                return None
            y = origin[1] + (j+.5)*spacing
            for i in range(ceil(rect.width()/spacing)):
                x = origin[0] + (i+.5)*spacing
                if _point_in(geom, x, y):
                    expected += 1
                    h = self.height(x, y)
                    if h is not None and isfinite(h):
                        samples[i, j] = h
        zones = RoofZones(samples, origin, spacing, expected)
        self.roof_levels[key] = zones
        # Spatial grids are larger than the previous scalar height cache.
        if len(self.roof_levels) > 128:
            self.roof_levels.popitem(last=False)
        return zones

    def main_roof_height(self, geom):
        zones = self.roof_zones(geom)
        return zones.level if zones is not None and zones.reliable else None

    def check(self, geom_a, geom_b):
        """Use paired spatial roof zones along ALL contact strips.

        Mixed main/garage boundaries must retain their real main-roof contact;
        taking the median over the whole boundary loses that information.
        Missing DSM cells never count as evidence for a detached house.
        """
        cuts = _roof_cross_sections(geom_a, geom_b)
        if len(cuts) < 2:
            return None
        a, b = self.roof_zones(geom_a), self.roof_zones(geom_b)
        if a is None or b is None or not a.reliable or not b.reliable:
            return None
        valid, low, run, longest = 0, 0, 0, 0
        previous = None
        for x, y, nx, ny in cuts:
            if self.feedback.isCanceled():
                return None
            ax, ay, bx, by = x+nx*1.25, y+ny*1.25, x-nx*1.25, y-ny*1.25
            za, zb = a.at(ax, ay), b.at(bx, by)
            if za is None or zb is None:
                run, previous = 0, None
                continue
            valid += 1
            is_main = False
            if za and zb:
                ha, hb = self.height(ax, ay), self.height(bx, by)
                if ha is not None and hb is not None and abs(ha-hb) <= 1.5:
                    is_main = True
            elif za is False or zb is False:
                low += 1
            if is_main:
                contiguous = previous is not None and hypot(x-previous[0], y-previous[1]) <= 1.0
                run = run+1 if contiguous else 1
                previous = (x, y)
                longest = max(longest, run)
            else:
                run, previous = 0, None
        # Four consecutive 0.5 m samples, not isolated tree/raster pixels.
        if longest >= 4:
            return True
        if valid >= .8 * len(cuts) and low >= .8 * valid and longest <= 1:
            return "bijgebouw"
        return None
