"""Lichte, deterministische woningtypering (geen QGIS- of 3DBAG-afhankelijkheid)."""
from __future__ import annotations

HOEK = "hoekwoning"
TUSSEN = "tussenwoning/geschakeld"
TWEEKAP = "twee-onder-een-kap"
VRIJ = "vrijstaande woning"
APPARTEMENT = "appartement"

EXCLUDED_STATUSES = {"niet gerealiseerd", "niet gerealiseerd pand", "pand gesloopt"}


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError, OverflowError):
        return default


def normalized_text(value):
    if value is None:
        return ""
    return str(value).strip()


def living_pand(usage):
    return "woonfunctie" in normalized_text(usage).casefold()


def excluded_pand(status):
    return normalized_text(status).casefold() in EXCLUDED_STATUSES


def normalize_bag_id(value):
    text = normalized_text(value)
    return text.replace("NL.IMBAG.Pand.", "", 1) if text.startswith("NL.IMBAG.Pand.") else text


def roof_continuity(edge_a, edge_b, inside_a, inside_b):
    """Indicatief dakcontact uit AHN-DSM; onzekere data -> None.

    Een gelijk hoog dak is geen sluitend bewijs voor één constructief dak. Bij
    scherpe hoogteverschillen of een lage verbindingsbouw is een los contact
    aannemelijk. De grenswaarden zijn conservatieve heuristieken.
    """
    import statistics
    from math import isfinite

    def valid(seq):
        return [float(v) for v in seq if v is not None
                and isinstance(v, (int, float)) and isfinite(v) and -100 < v < 1000]

    a, b, ia, ib = (valid(v) for v in (edge_a, edge_b, inside_a, inside_b))
    if min(len(a), len(b)) < 3 or min(len(ia), len(ib)) < 3:
        return None
    ha, hb = statistics.median(a), statistics.median(b)
    pa, pb = sorted(ia)[int((len(ia)-1)*0.85)], sorted(ib)[int((len(ib)-1)*0.85)]
    delta = abs(ha - hb)
    deep_a, deep_b = pa - ha, pb - hb
    if delta >= 3.0:
        return False
    # Twee lage dakstroken tussen veel hogere panddelen: waarschijnlijk aanbouw.
    if deep_a >= 3.5 and deep_b >= 3.5 and delta < 1.5:
        return False
    if delta <= 0.85 and deep_a <= 2.75 and deep_b <= 2.75:
        return True
    return None


def classify_pands(records, neighbours, roof_links=None, source="AHN"):
    """Geef woningtypen en diagnostiek in dezelfde volgorde als records terug.

    records: [{usage, count_vbo}, ...]
    neighbours: {index: set(buurindex)}
    roof_links: {(min_idx,max_idx): True/False/None}
    Alleen een bewezen False verwijdert een geometrisch aangrenzende buur.
    """
    roof_links = roof_links or {}
    out = []
    effective = {}
    for i in range(len(records)):
        effective[i] = [
            j for j in sorted(neighbours.get(i, set()))
            if roof_links.get((min(i, j), max(i, j))) is not False
        ]

    for i, record in enumerate(records):
        has_home = living_pand(record.get("usage"))
        is_apartment = has_home and safe_int(record.get("count_vbo")) > 1
        adjacent = effective[i]
        if not has_home:
            category = ""
        elif is_apartment:
            category = APPARTEMENT
        elif not adjacent:
            category = VRIJ
        elif len(adjacent) >= 2:
            category = TUSSEN
        else:
            neighbour = adjacent[0]
            neighbouring_record = records[neighbour]
            if len(effective[neighbour]) >= 2 or (
                living_pand(neighbouring_record.get("usage"))
                and safe_int(neighbouring_record.get("count_vbo")) > 1
            ):
                category = HOEK
            else:
                category = TWEEKAP

        tests = [roof_links.get((min(i, j), max(i, j)))
                 for j in sorted(neighbours.get(i, set())) if
                 (min(i, j), max(i, j)) in roof_links]
        verified = sum(t is not None for t in tests)
        connected = sum(t is True for t in tests)
        uncertain = (len(neighbours.get(i, set())) - verified) if source == "AHN" else 0
        if not has_home:
            quality = "niet van toepassing"
        elif source == "BAG":
            quality = "BAG-geometrie; geen hoogtecontrole"
        elif not neighbours.get(i):
            quality = "geen aangrenzende BAG-panden"
        elif uncertain:
            quality = "controle nodig: AHN-contact ontbreekt of is onzeker"
        else:
            quality = "AHN-dakcontact indicatief"

        out.append({
            "woningtype": category,
            "dakburen": len(neighbours.get(i, set())),
            "dakverbonden": connected,
            "dakgetest": verified,
            "dakonzeker": uncertain,
            "controle": quality,
        })
    return out
