"""AHN DSM: alleen kleine hoogtevensters rond gedeelde BAG-pandgrenzen.

Geen afhankelijkheid van 3DBAG, pdal, scipy, rasterio of een lokaal
volledig 3D-model. QGIS/GDAL leest de gecachte GeoTIFF-bestanden.
"""
from __future__ import annotations

from collections import OrderedDict
from math import ceil, floor, hypot, isfinite
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from qgis.PyQt.QtCore import QStandardPaths
from qgis.core import QgsGeometry, QgsPointXY, QgsRasterLayer

from .classify import roof_continuity

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
        count = min(10, max(2, ceil(length / 2.5)))
        dx, dy = (end.x()-start.x())/length, (end.y()-start.y())/length
        nx, ny = -dy, dx
        for step in range(count):
            if len(result) >= 12:
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

    def check(self, geom_a, geom_b):
        """True/False/None: vermoedelijk dakdoorlopend / gescheiden / onzeker."""
        cuts = _roof_cross_sections(geom_a, geom_b)
        if len(cuts) < 3:
            return None
        edge_a, edge_b, inside_a, inside_b = [], [], [], []
        for x, y, nx, ny in cuts:
            if self.feedback.isCanceled():
                return None
            ax, ay = x+nx*1.25, y+ny*1.25
            bx, by = x-nx*1.25, y-ny*1.25
            ha, hb = self.height(ax, ay), self.height(bx, by)
            if ha is None or hb is None:
                continue
            edge_a.append(ha)
            edge_b.append(hb)
            inside_a.append(ha)
            inside_b.append(hb)
            for depth in (3.0, 5.0):
                ia = x+nx*depth, y+ny*depth
                ib = x-nx*depth, y-ny*depth
                if _point_in(geom_a, ia, y+ny*depth):
                    inside_a.append(self.height(ia, y+ny*depth))
                if _point_in(geom_b, ib, y-ny*depth):
                    inside_b.append(self.height(ib, y-ny*depth))
        return roof_continuity(edge_a, edge_b, inside_a, inside_b)
