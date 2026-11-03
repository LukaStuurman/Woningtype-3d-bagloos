"""Eén herkenbare woningtypenlaag met vaste QGIS-categoriesymbologie.

Styles uitsluitend op de uiteindelijke Processing-uitvoer en niet op de
achterliggende BAG WFS of tijdelijke verwerkingstegels.
"""
from qgis.core import (
    QgsCategorizedSymbolRenderer,
    QgsFillSymbol,
    QgsProcessingLayerPostProcessorInterface,
    QgsRendererCategory,
    QgsVectorLayer,
)

# Vaste kleuren; ook voor categorieën die in de actuele selectie ontbreken.
WONINGTYPE_COLORS = (
    ("vrijstaande woning", "#2a9d8f", "Vrijstaande woning"),
    ("twee-onder-een-kap", "#6c5ce7", "Twee-onder-een-kap"),
    ("hoekwoning", "#e9a23b", "Hoekwoning"),
    ("tussenwoning/geschakeld", "#db6942", "Tussenwoning / geschakeld"),
    ("appartement", "#377fbc", "Appartement"),
    ("", "#d2d6d9", "Overig / geen woonfunctie"),
)


def style_woningtypen(layer):
    """Pas een categorierenderer toe op de enige uitvoerlaag."""
    if not isinstance(layer, QgsVectorLayer) or not layer.isValid():
        return False
    if layer.fields().indexFromName("Woningtype") < 0:
        return False
    categories = []
    for value, color, label in WONINGTYPE_COLORS:
        symbol = QgsFillSymbol.createSimple({
            "color": color,
            "outline_color": "#4b5563",
            "outline_width": "0.16",
            "outline_width_unit": "MM",
        })
        categories.append(QgsRendererCategory(value, symbol, label))
    layer.setRenderer(QgsCategorizedSymbolRenderer("Woningtype", categories))
    layer.setName("Woningtypen (BAG + AHN)")
    layer.triggerRepaint()
    return True


class WoningtypePostProcessor(QgsProcessingLayerPostProcessorInterface):
    """QGIS roept deze handler op als het RESULTAAT geladen wordt.

    Styling in processAlgorithm zelf zou ook fout kunnen gaan bij verwerking
    in een aparte QGIS-thread. Deze callback draait altijd in de GUI-thread.
    """
    # Houd Python-objecten in leven tot QGIS de post-processing heeft voltooid.
    _references = []

    @classmethod
    def create(cls):
        processor = cls()
        cls._references.append(processor)
        return processor

    def postProcessLayer(self, layer, context, feedback):
        if style_woningtypen(layer) and feedback is not None:
            feedback.pushInfo("Woningtypen: categoriekleuren toegepast op Woningtype.")
