import json
from pathlib import Path

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "visualization.partyvideo"


def rpc(method, params):
    response = json.loads(
        xbmc.executeJSONRPC(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": method,
                    "params": params,
                }
            )
        )
    )
    if "error" in response:
        raise RuntimeError(response["error"].get("message", "Kodi RPC error"))
    return response["result"]


def paths():
    addon = xbmcaddon.Addon(ADDON_ID)
    return (
        Path(xbmcvfs.translatePath(addon.getAddonInfo("profile"))),
        Path(xbmcvfs.translatePath("special://temp/partyvideo/")),
    )


def send(command):
    if xbmcgui.Window(10000).getProperty("partyvideo.service") != "ready":
        raise RuntimeError(xbmcaddon.Addon(ADDON_ID).getLocalizedString(32010))
    rpc("JSONRPC.NotifyAll", {"sender": ADDON_ID, "message": "partyvideo_cmd", "data": command})


class Adapter:
    addon_id = ADDON_ID

    def __init__(self):
        self.progress = None
        self.last_state = None

    def selected(self):
        return rpc("Settings.GetSettingValue", {"setting": "musicplayer.visualisation"})["value"]

    def select(self, value):
        if (
            rpc("Settings.SetSettingValue", {"setting": "musicplayer.visualisation", "value": value})
            is not True
        ):
            raise RuntimeError("Visualisierung konnte nicht umgeschaltet werden")

    def open_visualisation(self):
        if xbmc.getCondVisibility("Player.HasAudio"):
            xbmc.executebuiltin("ActivateWindow(visualisation)")

    def close_visualisation(self):
        if xbmc.getCondVisibility("Window.IsActive(visualisation)"):
            xbmc.executebuiltin("ActivateWindow(home)")

    def max_height(self):
        return 720 if xbmcaddon.Addon(ADDON_ID).getSetting("max_height") == "720" else 1080

    def publish(self, status):
        state = status["state"]
        addon = xbmcaddon.Addon(ADDON_ID)
        if state in ("installing_tools", "downloading"):
            if self.progress is None:
                self.progress = xbmcgui.DialogProgressBG()
                self.progress.create("Party Video")
            label = addon.getLocalizedString(32013 if state == "installing_tools" else 32014)
            self.progress.update(int(status.get("progress") or 0), "Party Video", label)
        elif self.progress is not None:
            self.progress.close()
            self.progress = None
        if self.last_state is not None and state != self.last_state and state in ("idle", "playing"):
            xbmcgui.Dialog().notification(
                "Party Video",
                addon.getLocalizedString(32011 if state == "playing" else 32012),
                xbmcgui.NOTIFICATION_INFO,
                2000,
            )
        self.last_state = state
        window = xbmcgui.Window(10000)
        for key, value in status.items():
            window.setProperty("partyvideo." + key, "" if value is None else str(value))
        rpc("JSONRPC.NotifyAll", {"sender": ADDON_ID, "message": "partyvideo_status", "data": status})

    def error(self, code):
        from .ui import error

        error(code)

    def log(self, message):
        xbmc.log(f"[{ADDON_ID}] {message}", xbmc.LOGWARNING)
