"""QGIS werkbalk + Processing-provider, compatibel met QGIS 3 en 4."""
from qgis.PyQt.QtCore import QTimer
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction
from qgis.core import (
    QgsApplication, QgsProcessingProvider, QgsProject, QgsReferencedRectangle,
    QgsVectorLayer,
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

    @staticmethod
    def _remove_empty_duplicate_results(existing_ids):
        """Ruim uitsluitend extra, lege uitvoerlagen van DEZE run op.

        Een QGIS-versie kan naast de gevulde output een lege tijdelijke
        placeholder laden. Raak nooit BAG-bronlagen, oude resultaten of
        andere projectlagen aan.
        """
        project = QgsProject.instance()
        created = [
            layer for layer in project.mapLayers().values()
            if layer.id() not in existing_ids
            and isinstance(layer, QgsVectorLayer)
            and layer.isValid()
            and layer.fields().indexFromName("Woningtype") >= 0
        ]
        if len(created) < 2 or not any(layer.featureCount() > 0 for layer in created):
            return
        for layer in created:
            if layer.featureCount() == 0:
                project.removeMapLayer(layer.id())

    def open_tool(self):
        from qgis import processing
        canvas = self.iface.mapCanvas()
        extent = QgsReferencedRectangle(
            canvas.extent(), canvas.mapSettings().destinationCrs()
        )
        existing_ids = set(QgsProject.instance().mapLayers())
        try:
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
        finally:
            # De Processing-dialog beheert het laden. Niet zelf een tweede
            # laag toevoegen; ruim een eventuele lege QGIS-placeholder op.
            QTimer.singleShot(
                0,
                lambda: self._remove_empty_duplicate_results(existing_ids),
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
