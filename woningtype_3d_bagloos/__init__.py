"""QGIS entrypoint voor Woningtype 3D-bagloos."""


def classFactory(iface):
    from .plugin import WoningtypeBagloosPlugin
    return WoningtypeBagloosPlugin(iface)
