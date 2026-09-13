import hashlib
import io
import json
import sys
import tempfile
import threading
import types
import unittest
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "visualization.partyvideo/resources/lib"))
sys.dont_write_bytecode = True

from partyvideo.statefile import read_json, write_json  # noqa: E402
from partyvideo.tools import Cancelled, Tools, check_cancel, verify  # noqa: E402


def archive(name, content):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as file:
        file.writestr(name, content)
    return buffer.getvalue()


class ToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.ytdlp = archive("yt_dlp/__init__.py", "version='test'")
        self.deno = archive("deno", b"test executable")
        self.bad_hash = False
        self.fail_run = False
        self.urls = []
        self.tools = Tools(self.root / "tools", self.fetch, self.run_deno)

    def fetch(self, url, path, cancel):
        check_cancel(cancel)
        self.urls.append(url)
        if url.endswith("releases/latest"):
            payload = json.dumps({"tag_name": "v1.2.3"}).encode()
        elif url.endswith("/yt-dlp"):
            payload = self.ytdlp
        elif url.endswith("/SHA2-256SUMS"):
            payload = (hashlib.sha256(self.ytdlp).hexdigest() + "  yt-dlp\n").encode()
        elif url.endswith(".sha256sum"):
            digest = "0" * 64 if self.bad_hash else hashlib.sha256(self.deno).hexdigest()
            payload = (digest + "  deno-aarch64-unknown-linux-gnu.zip\n").encode()
        else:
            payload = self.deno
        Path(path).write_bytes(payload)

    def run_deno(self, *args, **kwargs):
        return types.SimpleNamespace(returncode=int(self.fail_run), stdout="deno 1.2.3\n")

    def install(self):
        self.tools.install(threading.Event(), lambda value: None)

    def test_verified_pair_is_installed_from_pinned_release(self):
        self.install()
        self.assertTrue(self.tools.ready())
        self.assertEqual((self.tools.directory / "yt-dlp").read_bytes(), self.ytdlp)
        self.assertTrue(all("/download/v1.2.3/" in url for url in self.urls if "/download/" in url))
        self.assertEqual(list(self.root.glob("tools-stage-*")), [])

    def test_bad_deno_hash_keeps_both_old_tools(self):
        self.install()
        original = (self.tools.directory / "yt-dlp").read_bytes()
        self.ytdlp = archive("yt_dlp/__init__.py", "new=True")
        self.bad_hash = True
        with self.assertRaises(ValueError):
            self.install()
        self.assertEqual((self.tools.directory / "yt-dlp").read_bytes(), original)
        self.assertTrue(self.tools.ready())

    def test_unusable_deno_does_not_replace_old_pair(self):
        self.install()
        self.fail_run = True
        with self.assertRaises(ValueError):
            self.install()
        self.assertTrue(self.tools.ready())

    def test_cancel_removes_staging_files(self):
        cancel = threading.Event()
        cancel.set()
        with self.assertRaises(Cancelled):
            self.tools.install(cancel, lambda value: None)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_checksum_must_match_exact_filename(self):
        binary, sums = self.root / "binary", self.root / "sums"
        binary.write_bytes(b"test")
        sums.write_text(hashlib.sha256(b"test").hexdigest() + "  yt-dlp-other\n")
        with self.assertRaises(ValueError):
            verify(binary, sums, "yt-dlp")

    def test_failed_atomic_write_preserves_original(self):
        target = self.root / "state.json"
        write_json(target, {"revision": 1})
        (self.root / "state.json.tmp").symlink_to("/dev/full")
        with self.assertRaises(OSError):
            write_json(target, {"revision": 2})
        self.assertEqual(read_json(target), {"revision": 1})
