"""PO-Token-Dienst für yt-dlp als Docker-Container, nur für die Dauer eines Anlaufs.

YouTube weist Medien-URLs ohne Herkunftsnachweis (PO-Token) zeitweise mit 403 ab.
Der Dienst erzeugt den Token, das yt-dlp-Plugin holt ihn dort ab. Beide stammen aus
bgutil-ytdlp-pot-provider und müssen dieselbe Version haben.
"""

import subprocess
import time
import urllib.request
from pathlib import Path

from .tools import Cancelled

VERSION = "2.0.2"
REPOSITORY = "brainicism/bgutil-ytdlp-pot-provider"
IMAGE = f"{REPOSITORY}:{VERSION}"
CONTAINER = "partyvideo-pot"
PORT = 4416
DOCKER = "/storage/.kodi/addons/service.system.docker/bin/docker"

PLUGIN_URL = (
    "https://github.com/Brainicism/bgutil-ytdlp-pot-provider/releases/download/"
    f"{VERSION}/bgutil-ytdlp-pot-provider.zip"
)
PLUGIN_SHA256 = "a26b980bf6d8e8400d8f21445daa4d8381bf6183d20f0be309391f86b31e27ef"

# yt-dlps Vorgabe-Clients fragen gar keinen Token an; dieser tut es und lädt damit.
PLAYER_CLIENT = "mweb"

# Der erste Start lädt das Image (rund 100 MB).
START_TIMEOUT_SECONDS = 300.0
READY_TIMEOUT_SECONDS = 30.0


def ping(timeout=2):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/ping", timeout=timeout) as response:
            return response.status == 200
    except (OSError, ValueError):
        return False


class Provider:
    def __init__(self, docker=DOCKER, popen=subprocess.Popen, runner=subprocess.run, ready=ping):
        self.docker = str(docker)
        self.popen = popen
        self.run = runner
        self.ready = ready
        self.active = False

    def available(self):
        return Path(self.docker).is_file()

    def stop(self, force=False):
        """Entfernt den Container. ``force`` räumt auch einen Rest früherer Läufe ab."""
        if not (self.active or force) or not self.available():
            return
        self.active = False
        try:
            self.run(
                [self.docker, "rm", "-f", CONTAINER],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    def start(self, cancel, log):
        """Startet den Dienst und wartet, bis er antwortet. Falsch, wenn er fehlt."""
        if not self.available():
            return False
        self.stop(force=True)
        self.active = True
        command = [
            self.docker, "run", "-d", "--rm", "--init",
            "--name", CONTAINER,
            "-p", f"127.0.0.1:{PORT}:{PORT}",
            "--read-only",
            "--tmpfs", "/tmp:rw,size=16m",
            "--cap-drop", "ALL",
            "--security-opt", "no-new-privileges",
            "--memory", "512m",
            "--pids-limit", "256",
            IMAGE,
        ]  # fmt: skip
        try:
            process = self.popen(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            log(f"PO-Token-Dienst startet nicht: {exc}")
            return False
        try:
            deadline = time.monotonic() + START_TIMEOUT_SECONDS
            while process.poll() is None:
                if time.monotonic() >= deadline:
                    raise TimeoutError
                if cancel.wait(0.2):
                    raise Cancelled
            if process.returncode != 0:
                log(f"PO-Token-Dienst startet nicht (docker run: {process.returncode}).")
                return False
            deadline = time.monotonic() + READY_TIMEOUT_SECONDS
            while not self.ready():
                if time.monotonic() >= deadline:
                    raise TimeoutError
                if cancel.wait(0.5):
                    raise Cancelled
            self._remove_old_images()
            return True
        except TimeoutError:
            log("PO-Token-Dienst antwortet nicht rechtzeitig.")
        except Cancelled:
            self._abort(process)
            raise
        self._abort(process)
        return False

    def _remove_old_images(self):
        """Nach einem Versionswechsel bliebe das alte Image sonst für immer liegen."""
        try:
            listing = self.run(
                [self.docker, "image", "ls", "--format", "{{.ID}} {{.Repository}}:{{.Tag}}", REPOSITORY],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            for line in (listing.stdout or "").splitlines():
                # Über die ID, weil ein Image ohne Tag keinen brauchbaren Namen hat.
                identifier, _, name = line.partition(" ")
                if identifier and name.startswith(REPOSITORY + ":") and name != IMAGE:
                    self.run(
                        [self.docker, "image", "rm", identifier],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=20,
                        check=False,
                    )
        except (OSError, subprocess.SubprocessError):
            pass

    def _abort(self, process):
        if process.poll() is None:
            process.kill()
            process.wait()
        self.stop()
