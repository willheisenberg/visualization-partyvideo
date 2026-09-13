"""Geprüfte Zipimport-/aarch64-Werkzeuge, als Paar atomar austauschbar."""

import hashlib
import json
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path


class Cancelled(Exception):
    pass


def check_cancel(cancel):
    if cancel.is_set():
        raise Cancelled


def fetch(url, destination, cancel):
    request = urllib.request.Request(url, headers={"User-Agent": "PartyVideo/0.3"})
    with urllib.request.urlopen(request, timeout=20) as response, Path(destination).open("wb") as out:
        size = 0
        while True:
            check_cancel(cancel)
            chunk = response.read(128 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > 256 * 1024 * 1024:
                raise ValueError("Werkzeug-Download zu groß")
            out.write(chunk)


def verify(path, sums, filename):
    expected = None
    for line in Path(sums).read_text().splitlines():
        fields = line.split()
        if (
            len(fields) == 2
            and fields[1].lstrip("*") == filename
            and re.fullmatch(r"[a-fA-F0-9]{64}", fields[0])
        ):
            expected = fields[0].lower()
    if expected is None or hashlib.sha256(Path(path).read_bytes()).hexdigest() != expected:
        raise ValueError(f"Prüfsumme stimmt nicht: {filename}")


class Tools:
    def __init__(self, directory, downloader=fetch, runner=subprocess.run):
        self.directory = Path(directory)
        self.fetch = downloader
        self.run = runner

    def ready(self):
        return all((self.directory / name).is_file() for name in ("yt-dlp", "deno", "versions.json"))

    def _release(self, repository, stage, cancel):
        metadata = stage / (repository.split("/")[1] + "-release.json")
        self.fetch(f"https://api.github.com/repos/{repository}/releases/latest", metadata, cancel)
        tag = json.loads(metadata.read_text())["tag_name"]
        if not re.fullmatch(r"[A-Za-z0-9._-]+", tag):
            raise ValueError("Ungültige Release-Version")
        return tag, f"https://github.com/{repository}/releases/download/{tag}"

    def install(self, cancel, progress):
        self.directory.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix="tools-stage-", dir=self.directory.parent))
        backup = self.directory.with_name("tools-previous")
        try:
            tag, base = self._release("yt-dlp/yt-dlp", stage, cancel)
            self.fetch(base + "/yt-dlp", stage / "yt-dlp", cancel)
            self.fetch(base + "/SHA2-256SUMS", stage / "sums", cancel)
            verify(stage / "yt-dlp", stage / "sums", "yt-dlp")
            with zipfile.ZipFile(stage / "yt-dlp") as archive:
                if "yt_dlp/__init__.py" not in archive.namelist():
                    raise ValueError("Kein yt-dlp-Zipimport-Paket")
            progress(40)
            deno_tag, base = self._release("denoland/deno", stage, cancel)
            name = "deno-aarch64-unknown-linux-gnu.zip"
            self.fetch(base + "/" + name, stage / "deno.zip", cancel)
            self.fetch(base + "/" + name + ".sha256sum", stage / "sums", cancel)
            verify(stage / "deno.zip", stage / "sums", name)
            with zipfile.ZipFile(stage / "deno.zip") as archive:
                with archive.open("deno") as source, (stage / "deno").open("wb") as target:
                    shutil.copyfileobj(source, target)
            (stage / "deno").chmod(0o755)
            result = self.run([str(stage / "deno"), "--version"], capture_output=True, text=True, timeout=20)
            if result.returncode != 0 or not result.stdout.startswith("deno "):
                raise ValueError("Deno kann auf diesem Gerät nicht starten")
            check_cancel(cancel)
            (stage / "versions.json").write_text(json.dumps({"yt-dlp": tag, "deno": deno_tag}))
            for path in stage.iterdir():
                if path.name not in ("yt-dlp", "deno", "versions.json"):
                    path.unlink()
            # Während des Austauschs läuft kein Downloader. Altes Paar bleibt bei Fehler erhalten.
            if backup.exists():
                shutil.rmtree(backup)
            if self.directory.exists():
                self.directory.rename(backup)
            try:
                stage.rename(self.directory)
            except OSError:
                if backup.exists():
                    backup.rename(self.directory)
                raise
            if backup.exists():
                shutil.rmtree(backup)
            progress(100)
        finally:
            if stage.exists():
                shutil.rmtree(stage)

    def recover(self):
        backup = self.directory.with_name("tools-previous")
        if not self.directory.exists() and backup.exists():
            backup.rename(self.directory)
        for path in self.directory.parent.glob("tools-stage-*"):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
