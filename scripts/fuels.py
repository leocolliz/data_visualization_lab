"""Harmonisation of the free-text `descCarburante` field.

MIMIT lets operators type their own commercial fuel name. Across 2024-2025 the
Nord-Est extract contains 59 distinct labels for what are really seven
products. Two things matter for this project:

1.  Premium grades must be kept *separate* from standard ones. Pooling them
    would make a station that happens to sell Blue Diesel look expensive when
    it is simply selling a different product.
2.  Methane, LNG and L-GNC are priced per **kilogram**, not per litre. They
    cannot appear in any EUR/litre comparison.
"""

# Canonical product -> the labels that map onto it. Matching is exact after
# casefolding and whitespace collapse, so a new label shows up as unmapped
# rather than being silently absorbed by a fuzzy rule.
_GROUPS = {
    "benzina": ["Benzina"],
    "benzina_premium": [
        "Blue Super", "Benzina speciale", "Benzina WR 100",
        "Benzina Shell V Power", "V-Power", "Benzina Plus 98",
        "Benzina Energy 98 ottani", "F101", "F-101", "Benzina 100 ottani",
        "Benzina Speciale 98 Ottani", "Benzina 102 Ottani", "Verde speciale",
        "R100",
    ],
    "gasolio": ["Gasolio"],
    "gasolio_premium": [
        "Blue Diesel", "Hi-Q Diesel", "Supreme Diesel", "HiQ Perform+",
        "Gasolio speciale", "Gasolio Premium", "Diesel Shell V Power",
        "DieselMax", "Excellium Diesel", "Excellium diesel", "S-Diesel",
        "Gasolio Oro Diesel", "Gasolio Ecoplus", "GP DIESEL", "E-DIESEL",
        "Gasolio Energy D", "V-Power Diesel", "Gasolio Plus",
        "Gasolio Prestazionale", "Diesel e+10",
    ],
    # Winter grade: sold mainly in Alpine provinces and priced above standard
    # diesel, so pooling it would bias exactly the provinces we are comparing.
    "gasolio_artico": [
        "Gasolio artico", "Gasolio Artico", "Gasolio Gelo", "Gasolio Alpino",
        "Blu Diesel Alpino", "Gasolio Artico Igloo",
    ],
    "hvo": [
        "HVOlution", "HVO", "HVO100", "REHVO", "Gasolio HVO", "BCHVO",
        "Diesel HVO", "HVO eco diesel", "HVOvolution", "Gasolio Bio HVO",
        "Diesel HVO Energy", "HVO Future", "GASOLIO HVO",
    ],
    "gpl": ["GPL"],
    "metano": ["Metano"],
    "gnl": ["GNL", "L-GNC"],
}

LABEL_TO_PRODUCT = {
    " ".join(lab.split()).casefold(): prod
    for prod, labs in _GROUPS.items()
    for lab in labs
}

# Products sold by the kilogram. Excluded from every EUR/litre view.
PER_KG = {"metano", "gnl"}

# The two products the geographic comparison is built on: the standard grades
# nearly every station sells, which makes them comparable across 5,300 pumps.
HEADLINE = ("benzina", "gasolio")

DISPLAY = {
    "benzina": "Petrol",
    "benzina_premium": "Petrol (premium)",
    "gasolio": "Diesel",
    "gasolio_premium": "Diesel (premium)",
    "gasolio_artico": "Diesel (winter grade)",
    "hvo": "HVO",
    "gpl": "LPG",
    "metano": "Methane (per kg)",
    "gnl": "LNG (per kg)",
}


def to_product(label):
    """Map a raw label to a canonical product, or None if unrecognised."""
    return LABEL_TO_PRODUCT.get(" ".join(str(label).split()).casefold())
