import os
import queue
import shutil
import subprocess
import threading
from pathlib import Path

from .commands import youtube_url
from .pot import PLAYER_CLIENT
from .tools import PLUGIN_NAME, Cancelled, check_cancel


def format_chain(height):
    height = 720 if height == 720 else 1080
    return "/".join(
        (
            f"bestvideo[vcodec^=avc1][height<={height}][fps<=30]",
            f"bestvideo[vcodec^=avc1][height<={height}]",
            f"best[vcodec^=avc1][height<={height}]",
        )
    )


# Ein zweiter Anlauf fängt die kurzlebigen 403er ab, ohne bei echten Ausfällen
# lange zu blockieren. Läuft Docker, holt er sich dafür einen PO-Token.
ATTEMPTS = 2
RETRY_PAUSE_SECONDS = 3.0
# Auch mit Token kommt gelegentlich ein 403; der Dienst läuft dann ohnehin schon.
TOKEN_ATTEMPTS = 2


class DownloadError(Exception):
    pass


def download(url, directory, tools, height, cancel, progress, log, provider=None, runner=None, fetch=None):
    """Lädt ein YouTube-Video; yt-dlp läuft dabei immer in einem eigenen Prozess (process_download)."""
    url = youtube_url(url)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    check_cancel(cancel)
    runner = runner or token_download
    fetch = fetch or process_download

    # YouTube weist die signierte Medien-URL gelegentlich mit 403 ab. yt-dlps eigene
    # "retries" holen dieselbe Adresse erneut und helfen dann nicht; nur eine frische
    # Auflösung erzeugt eine neue URL. Deshalb ein zweiter Anlauf von vorn.
    try:

        def with_token():
            for attempt in range(TOKEN_ATTEMPTS):
                try:
                    return runner(url, directory, tools, height, cancel, progress, log)
                except DownloadError as exc:
                    if str(exc) != "download_failed" or attempt + 1 >= TOKEN_ATTEMPTS:
                        raise
                    log("Download mit PO-Token fehlgeschlagen; noch ein Versuch.")
                    if cancel.wait(RETRY_PAUSE_SECONDS):
                        raise Cancelled from exc
            raise DownloadError("download_failed")

        plain = (fetch, url, directory, tools, height, progress)
        return _attempts(plain, cancel, log, (provider, with_token))
    finally:
        if provider is not None:
            provider.stop()


def _attempts(plain, cancel, log, token):
    fetch, url, directory, tools, height, progress = plain
    provider, with_token = token
    for attempt in range(ATTEMPTS):
        try:
            return fetch(url, directory, tools, height, cancel, progress, log)
        except DownloadError as exc:
            if cancel.is_set():
                raise Cancelled from exc
            if str(exc) == "no_suitable_format":
                # Das Format fehlt dauerhaft; ein zweiter Anlauf ändert daran nichts.
                raise
            if attempt + 1 >= ATTEMPTS:
                raise DownloadError("download_failed") from exc
            if provider is not None and provider.start(cancel, log):
                log("Download fehlgeschlagen; neuer Versuch mit PO-Token.")
                return with_token()
            log("Download fehlgeschlagen; neuer Versuch mit frischer Auflösung.")
            if cancel.wait(RETRY_PAUSE_SECONDS):
                raise Cancelled from exc
    raise DownloadError("download_failed")


RESULT_MARK = "PARTYVIDEO-RESULT\t"
PROGRESS_MARK = "PARTYVIDEO-PROGRESS\t"


def process_download(
    url, directory, tools, height, cancel, progress, log, popen=None, interpreter=None, token=False
):
    """Lädt mit yt-dlp in einem eigenen Prozess (System-Python), mit PO-Token, wenn token=True.

    yt-dlp gehört nicht in Kodis eingebettetes Python. Dort hat es Kodi zweimal abstürzen lassen:
    - Das Token-Plugin beim ersten Versuch.
    - yt_dlp/YoutubeDL.py enthält '\\N{FULLWIDTH COMMA}'. Python 3.11 merkt sich dafür prozessweit
      einen Zeiger in das unicodedata-Modul des ersten Interpreters; nach einem Neustart dieses
      Service ist er ungültig, und der nächste Import stürzt mit SIGSEGV ab.
    Im eigenen Prozess trifft ein Fehler nur diesen einen Download.
    """
    tools = Path(tools)
    popen = popen or subprocess.Popen
    interpreter = interpreter or shutil.which("python3")
    if not interpreter:
        log("Kein System-Python für yt-dlp gefunden.")
        raise DownloadError("download_failed")
    command = [
        interpreter, str(tools / "yt-dlp"),
        "--no-config", "--no-cache-dir", "--no-playlist", "--no-simulate", "--newline", "--progress",
        "--fixup", "never",
        "--format", format_chain(height),
        "--output", str(Path(directory) / "%(id)s.%(ext)s"),
        "--js-runtimes", f"deno:{tools / 'deno'}",
        "--match-filters", "!is_live",
        "--socket-timeout", "15", "--retries", "2", "--fragment-retries", "2",
        "--progress-template",
        f"download:{PROGRESS_MARK}%(progress.downloaded_bytes)s\t%(progress.total_bytes)s",
        "--print", f"after_move:{RESULT_MARK}%(filepath)s\t%(title)s",
    ]  # fmt: skip
    if token:
        command += ["--extractor-args", f"youtube:player_client={PLAYER_CLIENT}"]
    command.append(url)
    # Kodi setzt Python-Variablen für seinen eigenen Interpreter; die gehören nicht hierher.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
    environment.update(PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8")
    if token:
        environment["PYTHONPATH"] = str(tools / PLUGIN_NAME)
    try:
        process = popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
            errors="replace",
            env=environment,
        )
    except OSError as exc:
        log(f"yt-dlp ließ sich nicht starten: {exc}")
        raise DownloadError("download_failed") from exc
    lines = queue.Queue()

    def pump():
        for line in process.stdout:
            lines.put(line.rstrip("\n"))
        lines.put(None)

    threading.Thread(target=pump, name="partyvideo-token-output", daemon=True).start()
    result, missing_format = None, False
    try:
        while True:
            if cancel.is_set():
                raise Cancelled
            try:
                line = lines.get(timeout=0.2)
            except queue.Empty:
                continue
            if line is None:
                break
            if line.startswith(PROGRESS_MARK):
                done, _, total = line[len(PROGRESS_MARK) :].partition("\t")
                if done.isdigit() and total.isdigit() and int(total):
                    progress(min(100, int(100 * int(done) / int(total))))
            elif line.startswith(RESULT_MARK):
                result = line[len(RESULT_MARK) :].partition("\t")
            elif line.startswith(("ERROR", "WARNING")):
                missing_format = missing_format or "Requested format is not available" in line
                log(line)
    except BaseException:
        # Abbruch oder Fehler: den Prozess nicht weiterladen lassen.
        process.kill()
        raise
    finally:
        process.wait()
    if missing_format:
        raise DownloadError("no_suitable_format")
    if process.returncode != 0 or result is None:
        raise DownloadError("download_failed")
    path = Path(result[0]).resolve()
    if not path.is_relative_to(Path(directory).resolve()) or not path.is_file():
        raise DownloadError("download_failed")
    return str(path), result[2] or "YouTube"


def token_download(url, directory, tools, height, cancel, progress, log, popen=None, interpreter=None):
    """Anlauf mit PO-Token (Plugin aus tools/, Dienst im Docker-Container, siehe pot.py)."""
    return process_download(
        url, directory, tools, height, cancel, progress, log, popen, interpreter, token=True
    )
