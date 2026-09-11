"""Stufe-0-Diagnose für visualization.partyvideo.

Prüft auf dem Zielgerät die Python-Umgebung, ob sich die Musikvisualisierung per
JSON-RPC setzen lässt und ob ein heruntergeladenes Deno aus dem Addon-Datenordner
startet. Wird in Plan 3 durch das echte Menü ersetzt.
"""

import json
import os
import platform
import shutil
import ssl
import stat
import struct
import subprocess
import urllib.request
import zipfile

import xbmc
import xbmcaddon
import xbmcgui
import xbmcvfs

ADDON_ID = "visualization.partyvideo"
VISUALISATION_SETTING = "musicplayer.visualisation"
DENO_URL = "https://github.com/denoland/deno/releases/latest/download/deno-aarch64-unknown-linux-gnu.zip"
# Bewusst nicht "tools": dort liegen ab Plan 4 nur geprüfte Werkzeuge.
STAGE0_TOOLS_DIR = "tools-stage0"


def log(message):
    xbmc.log(f"[{ADDON_ID}] probe: {message}", xbmc.LOGINFO)


def jsonrpc(method, params):
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    return json.loads(xbmc.executeJSONRPC(json.dumps(request)))


class Report:
    """Sammelt die Zeilen für den Textviewer und schreibt jede sofort ins kodi.log."""

    def __init__(self):
        self.lines = []

    def add(self, line):
        self.lines.append(line)
        if line:
            log(line.replace("[B]", "").replace("[/B]", ""))


def probe_environment(report):
    report.add(f"Python {platform.python_version()} ({platform.machine()})")
    report.add(f"Userland {struct.calcsize('P') * 8} Bit")
    report.add(ssl.OPENSSL_VERSION)
    report.add(f"CA-Datei: {ssl.get_default_verify_paths().cafile}")
    report.add(f"Kodi {xbmc.getInfoLabel('System.BuildVersion')}")


def probe_visualisation_setting(report):
    before = jsonrpc("Settings.GetSettingValue", {"setting": VISUALISATION_SETTING})
    if "result" not in before:
        report.add(f"GetSettingValue fehlgeschlagen: {before}")
        return
    old_value = before["result"].get("value")
    report.add(f"Wert vorher: {old_value!r}")
    try:
        changed = jsonrpc("Settings.SetSettingValue", {"setting": VISUALISATION_SETTING, "value": ADDON_ID})
        report.add(f"SetSettingValue(Addon): {changed.get('result', changed.get('error'))}")
        after = jsonrpc("Settings.GetSettingValue", {"setting": VISUALISATION_SETTING})
        report.add(f"Wert danach: {after.get('result', {}).get('value')!r}")
    finally:
        # Auch nach einer Exception den alten Wert zurückschreiben.
        restored = jsonrpc("Settings.SetSettingValue", {"setting": VISUALISATION_SETTING, "value": old_value})
        report.add(f"SetSettingValue(vorher): {restored.get('result', restored.get('error'))}")


def fetch_deno(report, tools_dir, archive, deno):
    """Lädt und entpackt Deno. Gibt zurück, ob die Datei startbereit ist."""
    step = "Verzeichnis anlegen"
    try:
        os.makedirs(tools_dir, exist_ok=True)
        step = "Download"
        with urllib.request.urlopen(DENO_URL, timeout=60) as response, open(archive, "wb") as target:
            shutil.copyfileobj(response, target)
        step = "Entpacken"
        with zipfile.ZipFile(archive) as zf:
            zf.extract("deno", tools_dir)
        step = "Ausführbar machen"
        os.chmod(deno, os.stat(deno).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except Exception as exc:  # Diagnose: jeden Fehler anzeigen
        report.add(f"{step} fehlgeschlagen: {exc!r}")
        return False
    return True


def start_deno(report, deno):
    try:
        result = subprocess.run([deno, "--version"], capture_output=True, text=True, timeout=120)
    except Exception as exc:  # Diagnose: jeden Fehler anzeigen
        report.add(f"Start fehlgeschlagen: {exc!r}")
        return
    report.add(f"Exit-Code {result.returncode}")
    for line in (result.stdout or result.stderr).strip().splitlines()[:3]:
        report.add(line)


def remove_deno(report, tools_dir, archive, deno):
    """Meldet die Größe von deno und löscht Datei, Archiv und Verzeichnis. Fehler brechen nichts ab."""
    if os.path.isfile(deno):
        try:
            report.add(f"deno: {deno}, {os.path.getsize(deno) / 1024 / 1024:.1f} MB")
        except OSError as exc:
            report.add(f"Größe von {deno} nicht lesbar: {exc!r}")
    for path in (archive, deno):
        if os.path.lexists(path):
            try:
                os.remove(path)
            except OSError as exc:
                report.add(f"Löschen fehlgeschlagen: {path}: {exc!r}")
    if os.path.isdir(tools_dir):
        try:
            os.rmdir(tools_dir)
        except OSError as exc:
            report.add(f"Verzeichnis nicht entfernt: {tools_dir}: {exc!r}")


def probe_deno(report, tools_dir):
    archive = os.path.join(tools_dir, "deno.zip")
    deno = os.path.join(tools_dir, "deno")
    try:
        if fetch_deno(report, tools_dir, archive, deno):
            start_deno(report, deno)
    finally:
        # Ungeprüftes Deno nie liegen lassen.
        remove_deno(report, tools_dir, archive, deno)


def run_probe(report, title, probe, *args):
    """Führt eine Probe aus; eine unerwartete Exception wird gemeldet, die übrigen Probes laufen weiter."""
    if report.lines:
        report.add("")
    report.add(f"[B]{title}[/B]")
    try:
        probe(report, *args)
    except Exception as exc:  # Diagnose: jeden Fehler anzeigen
        report.add(f"{title} abgebrochen: {exc!r}")


def main():
    addon = xbmcaddon.Addon()
    tools_dir = os.path.join(xbmcvfs.translatePath(addon.getAddonInfo("profile")), STAGE0_TOOLS_DIR)
    dialog = xbmcgui.Dialog()
    report = Report()

    run_probe(report, "Umgebung", probe_environment)
    run_probe(report, "Visualisierungs-Einstellung", probe_visualisation_setting)
    question = (
        "Deno testweise herunterladen (rund 45 MB) und starten? Die Datei wird nach dem Test wieder gelöscht."
    )
    if dialog.yesno("Party Video", question):
        dialog.notification("Party Video", "Deno wird geladen …", xbmcgui.NOTIFICATION_INFO, 5000)
        run_probe(report, "Deno", probe_deno, tools_dir)

    dialog.textviewer("Party Video – Stufe 0", "\n".join(report.lines))


if __name__ == "__main__":
    main()
