"""Stufe 0: belegt nur, dass der Service-Erweiterungspunkt neben Visualisierung und Script startet."""

import xbmc

ADDON_ID = "visualization.partyvideo"


def main():
    xbmc.log(f"[{ADDON_ID}] service: gestartet", xbmc.LOGINFO)
    xbmc.Monitor().waitForAbort()
    xbmc.log(f"[{ADDON_ID}] service: beendet", xbmc.LOGINFO)


if __name__ == "__main__":
    main()
