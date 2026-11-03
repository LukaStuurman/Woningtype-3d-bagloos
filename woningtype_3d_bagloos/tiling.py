"""Geheugenarme verwerking in tegels, los van QGIS te testen."""
from __future__ import annotations

from math import ceil


# RD New-uitsnede met ruime marge rondom alle Nederlandse BAG-panden.
NETHERLANDS_RD = (-50000.0, 246000.0, 297000.0, 630000.0)


def tile_windows(bounds, tile_size):
    """Genereer halfopen rechthoektegels die een gebied exact afdekken.

    bounds: xmin, ymin, xmax, ymax (RD meters).
    """
    xmin, ymin, xmax, ymax = map(float, bounds)
    size = float(tile_size)
    if size <= 0 or xmax <= xmin or ymax <= ymin:
        raise ValueError("Ongeldige tegelgrootte of onderzoeksgebied")
    nx = int(ceil((xmax - xmin) / size))
    ny = int(ceil((ymax - ymin) / size))
    for iy in range(ny):
        y0 = ymin + iy * size
        y1 = min(ymin + (iy + 1) * size, ymax)
        for ix in range(nx):
            x0 = xmin + ix * size
            x1 = min(xmin + (ix + 1) * size, xmax)
            yield (x0, y0, x1, y1)


def subdivide(bounds):
    """Splits een te drukke tegel over de langste as, zonder overlap."""
    x0, y0, x1, y1 = map(float, bounds)
    if (x1 - x0) >= (y1 - y0):
        middle = (x0 + x1) / 2.0
        return (x0, y0, middle, y1), (middle, y0, x1, y1)
    middle = (y0 + y1) / 2.0
    return (x0, y0, x1, middle), (x0, middle, x1, y1)


def tile_owns_point(tile, full_extent, x, y):
    """Wijs een pand deterministisch aan precies één tegel toe.

    Het pandcentrum wordt op de globale bbox geklemd. Zo worden panden
    net over de rand van het gekozen kaartvenster niet dubbel weggeschreven.
    """
    tx0, ty0, tx1, ty1 = tile
    xmin, ymin, xmax, ymax = full_extent
    if xmin >= xmax or ymin >= ymax:
        return False
    x = min(max(x, xmin), xmax - 1e-8)
    y = min(max(y, ymin), ymax - 1e-8)
    return tx0 <= x < tx1 and ty0 <= y < ty1


def area(bounds):
    x0, y0, x1, y1 = bounds
    return max(0.0, x1-x0)*max(0.0, y1-y0)
