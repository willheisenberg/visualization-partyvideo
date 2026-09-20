"""Öffnet Party Video beim Musikstart und Titelwechsel automatisch."""

import json
import queue
import sys
import threading
import time
from pathlib import Path

import xbmc
import xbmcgui

sys.path.insert(0, str(Path(__file__).parent / "resources" / "lib"))
sys.dont_write_bytecode = True

from partyvideo.commands import Command  # noqa: E402
from partyvideo.controller import Controller  # noqa: E402
from partyvideo.kodi import Adapter, paths  # noqa: E402
from partyvideo.statefile import read_json  # noqa: E402
from partyvideo.tools import Tools  # noqa: E402

ADDON_ID = "visualization.partyvideo"
RETURN_AFTER_SECONDS = 3


class VisualisationRecovery:
    """Begrenzt einen fehlenden Rendererstart durch erneutes Öffnen beheben."""

    def __init__(self, profile, adapter, clock=time.monotonic):
        self.profile, self.adapter, self.clock = profile, adapter, clock
        self.revision = None
        self.attempts = 0
        self.deadline = 0.0
        self.waiting_until = None
        self.confirmed = False

    def tick(self):
        """True während eines Fensterwechsels: automatische Navigation aussetzen."""
        state = read_json(self.profile / "state.json")
        revision = state.get("revision") if state.get("source") else None
        now = self.clock()
        if revision != self.revision:
            self.revision = revision
            self.attempts = 0
            self.deadline = now + 5.0
            self.waiting_until = None
            self.confirmed = False
        if revision is None:
            return False

        if self.waiting_until is not None:
            # ActivateWindow ist asynchron. Erst nach dem Verlassen wieder öffnen.
            allowed = self._allowed()
            if allowed and xbmc.getCondVisibility("Window.IsActive(home)"):
                xbmc.executebuiltin("ActivateWindow(visualisation)")
                self.waiting_until = None
                self.deadline = now + 5.0
                return True
            if allowed and xbmc.getCondVisibility("Window.IsActive(visualisation)"):
                if now < self.waiting_until:
                    return True
            self.waiting_until = None
            self.attempts = 2  # Keine Navigationsschleife bei fehlendem GUI-Wechsel.
            return False

        renderer = read_json(self.profile / "renderer.json")
        if renderer.get("revision") == revision and renderer.get("state") in ("playing", "error"):
            self.confirmed = True
        if self.confirmed or self.attempts >= 2 or now < self.deadline:
            return False
        if not self._allowed() or not xbmc.getCondVisibility("Window.IsActive(visualisation)"):
            return False
        self.attempts += 1
        self.waiting_until = now + 2.0
        xbmc.log(
            f"[{ADDON_ID}] Rendererstart fehlt für Revision {revision}; "
            f"öffne Visualisierung neu (Versuch {self.attempts}/2)", xbmc.LOGWARNING,
        )
        xbmc.executebuiltin("ActivateWindow(home)")
        return True

    def _allowed(self):
        return (
            xbmc.getCondVisibility("Player.HasAudio")
            and xbmc.getGlobalIdleTime() >= RETURN_AFTER_SECONDS
            and not any(xbmc.getCondVisibility(condition) for condition in (
                "System.HasModalDialog", "System.ScreenSaverActive", "System.DPMSActive",
            ))
            and self.adapter.selected() == ADDON_ID
        )


def idle_return_due():
    """Nach Bedienpause aus Hauptmenü/Musikansicht zurück, nicht aus Einstellungen."""
    return xbmc.getGlobalIdleTime() >= RETURN_AFTER_SECONDS and any(
        xbmc.getCondVisibility(f"Window.IsActive({window})")
        for window in ("home", "music", "musicplaylist", "visualisation", "musicosd", "songinformation")
    )


def show_visualisation(state_path):
    """Nur für aktive Party-Video-Musikwiedergabe die Titelansicht ausblenden."""
    if not xbmc.getCondVisibility("Player.HasAudio"):
        return
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if not isinstance(state, dict) or not state.get("source"):
            return
        response = json.loads(
            xbmc.executeJSONRPC(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": 1,
                        "method": "Settings.GetSettingValue",
                        "params": {"setting": "musicplayer.visualisation"},
                    }
                )
            )
        )
        if response.get("result", {}).get("value") != ADDON_ID:
            return
    except (OSError, ValueError, AttributeError):
        return

    music_dialogs = ("musicosd", "songinformation")
    if xbmc.getCondVisibility("System.HasModalDialog") and not any(
        xbmc.getCondVisibility(f"Window.IsActive({dialog})") for dialog in music_dialogs
    ):
        return
    for dialog in music_dialogs:
        if xbmc.getCondVisibility(f"Window.IsActive({dialog})"):
            xbmc.executebuiltin(f"Dialog.Close({dialog},true)")
            return  # GUI-Anweisungen asynchron; Zustand im nächsten Durchlauf neu lesen.
    if not xbmc.getCondVisibility("Window.IsActive(visualisation)"):
        xbmc.log(f"[{ADDON_ID}] öffne Visualisierung", xbmc.LOGINFO)
        xbmc.executebuiltin("ActivateWindow(visualisation)")
        return
    # Info ist ein Toggle: niemals senden, wenn die Information schon aus ist.
    if xbmc.getCondVisibility("Window.IsActive(visualisation)") and xbmc.getCondVisibility("Player.ShowInfo"):
        xbmc.log(f"[{ADDON_ID}] blende Titelinfo aus", xbmc.LOGINFO)
        xbmc.executebuiltin("Action(Info)")
    xbmc.log(f"[{ADDON_ID}] automatische Visualisierung geprüft", xbmc.LOGDEBUG)


class Player(xbmc.Player):
    def __init__(self):
        super().__init__()
        self.track_started = threading.Event()
        self.track_started.set()  # Auch beim Service-Neustart während laufender Musik.

    def onAVStarted(self):
        self.track_started.set()
        xbmc.log(f"[{ADDON_ID}] Titelstart erkannt", xbmc.LOGINFO)


class Monitor(xbmc.Monitor):
    def __init__(self, commands):
        super().__init__()
        self.commands = commands

    def onNotification(self, sender, method, data):
        if sender == ADDON_ID and method == "Other.partyvideo_cmd":
            try:
                self.commands.put_nowait(json.loads(data))
            except (ValueError, queue.Full):
                xbmc.log(f"[{ADDON_ID}] ungültiger Befehl oder Warteschlange voll", xbmc.LOGWARNING)


def main():
    profile, temporary = paths()
    state_path = profile / "state.json"
    commands = queue.Queue(maxsize=64)
    monitor = Monitor(commands)
    player = Player()
    controller = Controller(profile, temporary, Adapter(), Tools(profile / "tools"))
    recovery = VisualisationRecovery(profile, controller.adapter)
    window = xbmcgui.Window(10000)
    window.clearProperty("partyvideo.service")
    try:
        controller.start()
        window.setProperty("partyvideo.service", "ready")
        xbmc.log(f"[{ADDON_ID}] service: ready (YouTube und Befehlskanal)", xbmc.LOGINFO)
        pending = []
        next_idle_check = 0.0
        while not monitor.abortRequested():
            try:
                # Begrenztes Batch, damit Renderer/Abbruch auch bei vielen Befehlen drankommen.
                for _ in range(16):
                    try:
                        data = commands.get_nowait()
                    except queue.Empty:
                        break
                    try:
                        controller.command(Command.from_data(data))
                    except (OSError, ValueError, RuntimeError) as exc:
                        controller.fail(str(exc))
                controller.tick()
                recovering = recovery.tick()
                if player.track_started.is_set():
                    player.track_started.clear()
                    now = time.monotonic()
                    pending = [now + delay for delay in (0.25, 0.75, 1.5)]
                if not recovering and pending and time.monotonic() >= pending[0]:
                    pending.pop(0)
                    show_visualisation(state_path)
                now = time.monotonic()
                if not recovering and not pending and now >= next_idle_check:
                    next_idle_check = now + 0.5
                    if idle_return_due():
                        show_visualisation(state_path)
            except Exception as exc:
                xbmc.log(f"[{ADDON_ID}] Service-Fehler: {exc}", xbmc.LOGERROR)
            if monitor.waitForAbort(0.1):
                break
    finally:
        window.clearProperty("partyvideo.service")
        controller.shutdown()
        xbmc.log(f"[{ADDON_ID}] service: beendet", xbmc.LOGINFO)


if __name__ == "__main__":
    main()
