import importlib
import sys
from pathlib import Path

from .commands import youtube_url
from .tools import Cancelled, check_cancel


def format_chain(height):
    height = 720 if height == 720 else 1080
    return "/".join(
        (
            f"bestvideo[vcodec^=avc1][height<={height}][fps<=30]",
            f"bestvideo[vcodec^=avc1][height<={height}]",
            f"best[vcodec^=avc1][height<={height}]",
        )
    )


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


def download(url, directory, tools, height, cancel, progress, log, factory=None):
    url = youtube_url(url)
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    check_cancel(cancel)
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
        code = "no_suitable_format" if "Requested format is not available" in str(exc) else "download_failed"
        raise DownloadError(code) from exc
