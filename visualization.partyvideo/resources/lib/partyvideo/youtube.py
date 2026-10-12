import importlib
import os
import queue
import shutil
import subprocess
import sys
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


class Logger:
    def __init__(self, log):
        self.log = log

    def debug(self, message):
        pass

    def warning(self, message):
        self.log(message)

    def error(self, message):
        self.log(message)


def download(url, directory, tools, height, cancel, progress, log, factory=None, provider=None, runner=None):
    url = youtube_url(url)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    check_cancel(cancel)
    runner = runner or token_download
    if factory is None:
        archive = str(Path(tools) / "yt-dlp")
        # Nur ein Download-Worker; Updates können deshalb gefahrlos neu importiert werden.
        for name in list(sys.modules):
            if name == "yt_dlp" or name.startswith("yt_dlp.") or name.startswith("yt_dlp_ejs"):
                del sys.modules[name]
        sys.path[:] = [entry for entry in sys.path if entry != archive]
        sys.path.insert(0, archive)
        sys.path_importer_cache.pop(archive, None)
        importlib.invalidate_caches()
        factory = importlib.import_module("yt_dlp").YoutubeDL

    def hook(data):
        check_cancel(cancel)
        total = data.get("total_bytes") or data.get("total_bytes_estimate")
        if total:
            progress(min(100, int(100 * data.get("downloaded_bytes", 0) / total)))

    def match_filter(info, *, incomplete=False):
        check_cancel(cancel)
        if info.get("is_live"):
            return "Live-Streams werden nicht als Endlosschleife heruntergeladen."
        return None

    options = {
        "format": format_chain(height),
        "outtmpl": str(directory / "%(id)s.%(ext)s"),
        "noplaylist": True,
        "fixup": "never",
        "progress_hooks": [hook],
        "js_runtimes": {"deno": {"path": str(Path(tools) / "deno")}},
        "logger": Logger(log),
        "quiet": True,
        "no_warnings": False,
        "socket_timeout": 15,
        "retries": 2,
        "fragment_retries": 2,
        "concurrent_fragment_downloads": 1,
        "match_filter": match_filter,
        "cachedir": False,
    }
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

        token = (provider, with_token)
        return _attempts(url, directory, options, factory, cancel, log, token)
    finally:
        if provider is not None:
            provider.stop()


def _attempts(url, directory, options, factory, cancel, log, token):
    provider, with_token = token
    for attempt in range(ATTEMPTS):
        try:
            with factory(options) as downloader:
                info = downloader.extract_info(url, download=True)
                check_cancel(cancel)
                if not info:
                    raise DownloadError("download_failed")
                path = Path(downloader.prepare_filename(info)).resolve()
                if not path.is_relative_to(directory.resolve()) or not path.is_file():
                    raise DownloadError("download_failed")
                return str(path), str(info.get("title") or info.get("id") or "YouTube")
        except Exception as exc:
            if cancel.is_set() or isinstance(exc, Cancelled):
                raise Cancelled from exc
            if "Requested format is not available" in str(exc):
                # Das Format fehlt dauerhaft; ein zweiter Anlauf ändert daran nichts.
                raise DownloadError("no_suitable_format") from exc
            if attempt + 1 >= ATTEMPTS:
                raise DownloadError("download_failed") from exc
            if provider is not None and provider.start(cancel, log):
                log(f"Download fehlgeschlagen ({exc}); neuer Versuch mit PO-Token.")
                return with_token()
            log(f"Download fehlgeschlagen ({exc}); neuer Versuch mit frischer Auflösung.")
            check_cancel(cancel)
            if cancel.wait(RETRY_PAUSE_SECONDS):
                raise Cancelled from exc
    raise DownloadError("download_failed")


RESULT_MARK = "PARTYVIDEO-RESULT\t"
PROGRESS_MARK = "PARTYVIDEO-PROGRESS\t"


def token_download(
    url, directory, tools, height, cancel, progress, log, popen=subprocess.Popen, interpreter=None
):
    """Lädt mit PO-Token in einem eigenen Prozess.

    Das Token-Plugin darf nicht in Kodis eingebettetes Python: Dort hat es Kodi beim
    ersten Versuch zum Absturz gebracht. Im System-Python trifft ein Fehler nur diesen
    einen Download.
    """
    tools = Path(tools)
    interpreter = interpreter or shutil.which("python3")
    if not interpreter:
        log("Kein System-Python für den Anlauf mit PO-Token gefunden.")
        raise DownloadError("download_failed")
    command = [
        interpreter, str(tools / "yt-dlp"),
        "--no-config", "--no-cache-dir", "--no-playlist", "--no-simulate", "--newline", "--progress",
        "--fixup", "never",
        "--format", format_chain(height),
        "--output", str(Path(directory) / "%(id)s.%(ext)s"),
        "--js-runtimes", f"deno:{tools / 'deno'}",
        "--extractor-args", f"youtube:player_client={PLAYER_CLIENT}",
        "--match-filters", "!is_live",
        "--socket-timeout", "15", "--retries", "2", "--fragment-retries", "2",
        "--progress-template",
        f"download:{PROGRESS_MARK}%(progress.downloaded_bytes)s\t%(progress.total_bytes)s",
        "--print", f"after_move:{RESULT_MARK}%(filepath)s\t%(title)s",
        url,
    ]  # fmt: skip
    # Kodi setzt Python-Variablen für seinen eigenen Interpreter; die gehören nicht hierher.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("PYTHON")}
    environment.update(
        PYTHONPATH=str(tools / PLUGIN_NAME), PYTHONDONTWRITEBYTECODE="1", PYTHONIOENCODING="utf-8"
    )
    process = popen(
        command,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        encoding="utf-8",
        errors="replace",
        env=environment,
    )
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
