"""QGIS werkbalk + Processing-provider, compatibel met QGIS 3 en 4."""
from qgis.PyQt.QtGui import QIcon
try:
    from qgis.PyQt.QtGui import QAction  # Qt6
except ImportError:
    from qgis.PyQt.QtWidgets import QAction  # Qt5
from qgis.core import (
    QgsApplication, QgsProcessingProvider, QgsReferencedRectangle,
)

from .processor import WoningtypenBepalenAlgorithm


class WoningtypeBagloosProvider(QgsProcessingProvider):
    def id(self):
        return "woningtypebagloos"

    def name(self):
        return "Woningtype 3D-bagloos"

    def longName(self):
        return "Woningtype 3D-bagloos (BAG + lokaal AHN)"

    def loadAlgorithms(self):
        self.addAlgorithm(WoningtypenBepalenAlgorithm())


class WoningtypeBagloosPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.provider = None
        self.action = None

    def initProcessing(self):
        if self.provider is None:
            self.provider = WoningtypeBagloosProvider()
            QgsApplication.processingRegistry().addProvider(self.provider)

    def initGui(self):
        self.initProcessing()
        self.action = QAction(
            QIcon.fromTheme("applications-science"),
            "Woningtype 3D-bagloos",
            self.iface.mainWindow(),
        )
        self.action.setToolTip(
            "Bepaal woningtypen met BAG en kleine lokale AHN-dakprofielen; "
            "zonder 3DBAG-server."
        )
        self.action.triggered.connect(self.open_tool)
        self.iface.addPluginToVectorMenu("Woningtype 3D-bagloos", self.action)
        self.iface.addToolBarIcon(self.action)

    def open_tool(self):
        from qgis import processing
        canvas = self.iface.mapCanvas()
        extent = QgsReferencedRectangle(
            canvas.extent(), canvas.mapSettings().destinationCrs()
        )
        # Processing owns the single finalized output and its post-processor.
        processing.execAlgorithmDialog(
            "woningtypebagloos:bepaal_woningtypen",
            {
                "AREA_MODE": 0,
                "EXTENT": extent,
                "MODE": 0,
                "NATIONAL_AHN": False,
                "TILE_SIZE": 10000,
                "OUTPUT": "TEMPORARY_OUTPUT",
            },
        )

    def unload(self):
        if self.action is not None:
            self.iface.removePluginVectorMenu("Woningtype 3D-bagloos", self.action)
            self.iface.removeToolBarIcon(self.action)
            self.action.deleteLater()
            self.action = None
        if self.provider is not None:
            QgsApplication.processingRegistry().removeProvider(self.provider)
            self.provider = None
