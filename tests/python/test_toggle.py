"""Der Service besitzt jetzt Toggle, Quellenzustand und Wiederherstellung."""

import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "visualization.partyvideo/resources/lib"))
sys.dont_write_bytecode = True

from partyvideo.commands import Command  # noqa: E402
from partyvideo.controller import Controller  # noqa: E402
from partyvideo.statefile import read_json, write_json  # noqa: E402
from partyvideo.tools import Cancelled  # noqa: E402


class Adapter:
    addon_id = "visualization.partyvideo"

    def __init__(self):
        self.current = "other.visualisation"
        self.statuses = []
        self.errors = []

    def selected(self):
        return self.current

    def select(self, value):
        self.current = value

    def publish(self, status):
        self.statuses.append(status)

    def error(self, code):
        self.errors.append(code)

    def open_visualisation(self):
        pass

    def close_visualisation(self):
        pass

    def max_height(self):
        return 1080

    def log(self, message):
        pass


class Tools:
    def __init__(self, directory):
        self.directory = directory

    def ready(self):
        return True

    def recover(self):
        pass


class ControllerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.profile = Path(self.temp.name) / "profile"
        self.downloads = Path(self.temp.name) / "temp"
        self.video = Path(self.temp.name) / "local.mp4"
        self.video.touch()
        self.adapter = Adapter()
        self.controller = Controller(
            self.profile, self.downloads, self.adapter, Tools(self.profile / "tools")
        )
        self.controller.start()
        self.addCleanup(self.controller.shutdown)

    def wait(self):
        deadline = time.monotonic() + 3
        while self.controller.worker is not None and time.monotonic() < deadline:
            self.controller.tick()
            time.sleep(0.005)
        self.assertIsNone(self.controller.worker)

    def play_local(self):
        self.controller.command(Command.from_data({"action": "play", "path": str(self.video)}))

    def test_toggle_restores_visualisation_and_remembers_local_video(self):
        self.play_local()
        self.assertEqual(self.adapter.current, self.adapter.addon_id)
        self.controller.command(Command("toggle"))
        self.assertEqual(self.adapter.current, "other.visualisation")
        self.assertEqual(read_json(self.profile / "state.json")["source"], "")
        self.assertTrue(self.video.exists())
        self.controller.command(Command("toggle"))
        self.assertEqual(self.controller.active["source"], str(self.video))
        self.assertEqual(self.adapter.current, self.adapter.addon_id)

    def test_switching_sources_preserves_original_visualisation(self):
        self.play_local()
        self.play_local()
        self.controller.stop()
        self.assertEqual(self.adapter.current, "other.visualisation")

    def test_start_ignores_stale_renderer_and_cleans_only_owned_temp(self):
        write_json(
            self.profile / "renderer.json", {"revision": 100, "state": "error", "error": "decode_failed"}
        )
        stale = self.downloads / "stale.part"
        stale.touch()
        (self.downloads / "outside").symlink_to(self.video)
        self.controller.start()
        self.assertEqual(self.controller.status["revision"], 101)
        self.assertFalse(stale.exists())
        self.assertTrue(self.video.exists())
        self.play_local()
        self.controller.tick()
        self.assertEqual(self.controller.status["state"], "playing")

    def test_current_renderer_error_is_published(self):
        self.play_local()
        write_json(
            self.profile / "renderer.json",
            {
                "revision": self.controller.status["revision"],
                "state": "error",
                "error": "decode_failed",
            },
        )
        self.controller.tick()
        self.assertEqual(self.adapter.errors, ["decode_failed"])

    def test_youtube_removed_on_stop_and_reloaded_on_toggle(self):
        calls = []

        def download(url, job, *args):
            path = job / "test.mp4"
            path.touch()
            calls.append(path)
            return str(path), "YouTube Test"

        self.controller.downloader = download
        self.controller.command(Command.from_data({"action": "play", "url": "https://youtu.be/zbo6jUGrwdk"}))
        self.wait()
        self.assertTrue(calls[0].exists())
        self.controller.stop()
        self.assertFalse(calls[0].exists())
        self.controller.command(Command("toggle"))
        self.wait()
        self.assertEqual(len(calls), 2)
        self.assertTrue(calls[1].exists())

    def test_cancelled_download_never_reactivates_after_local_replacement(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def download(url, job, tools, height, cancel, *args):
            started.set()
            release.wait(2)
            # Simuliert einen Downloader, der zu spät noch Erfolg meldet.
            path = job / "late.mp4"
            path.touch()
            return str(path), "Late"

        self.controller.downloader = download
        self.controller.command(Command.from_data({"action": "play", "url": "https://youtu.be/zbo6jUGrwdk"}))
        self.assertTrue(started.wait(1))
        self.play_local()
        release.set()
        self.wait()
        self.assertEqual(self.controller.active["source"], str(self.video))
        self.assertEqual(list(self.downloads.iterdir()), [])

    def test_old_video_continues_during_download_and_stop_cancels(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        self.play_local()

        def download(url, job, tools, height, cancel, *args):
            started.set()
            release.wait(2)
            if cancel.is_set():
                raise Cancelled
            raise RuntimeError("download_failed")

        self.controller.downloader = download
        self.controller.command(Command.from_data({"action": "play", "url": "https://youtu.be/zbo6jUGrwdk"}))
        self.assertTrue(started.wait(1))
        self.assertEqual(read_json(self.profile / "state.json")["source"], str(self.video))
        self.controller.stop()
        release.set()
        self.wait()
        self.assertEqual(self.controller.status["state"], "idle")
        self.assertEqual(list(self.downloads.iterdir()), [])

    def test_replacing_youtube_removes_old_download_only_after_success(self):
        calls = []
        ready, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)

        def download(url, job, *args):
            if calls:
                ready.set()
                release.wait(2)
            path = job / "video.mp4"
            path.touch()
            calls.append(path)
            return str(path), "Test"

        self.controller.downloader = download
        command = Command.from_data({"action": "play", "url": "https://youtu.be/zbo6jUGrwdk"})
        self.controller.command(command)
        self.wait()
        old = calls[0]
        self.controller.command(command)
        self.assertTrue(ready.wait(1))
        self.assertTrue(old.exists())
        self.assertEqual(self.controller.active["source"], str(old))
        release.set()
        self.wait()
        self.assertFalse(old.exists())
        self.assertTrue(calls[1].exists())

    def test_repeated_play_runs_at_most_one_downloader(self):
        started, release = threading.Event(), threading.Event()
        self.addCleanup(release.set)
        concurrent = 0
        maximum = 0
        calls = 0

        def download(url, job, *args):
            nonlocal concurrent, maximum, calls
            concurrent += 1
            calls += 1
            maximum = max(maximum, concurrent)
            if calls == 1:
                started.set()
                release.wait(2)
            path = job / "video.mp4"
            path.touch()
            concurrent -= 1
            return str(path), "Test"

        self.controller.downloader = download
        command = Command.from_data({"action": "play", "url": "https://youtu.be/zbo6jUGrwdk"})
        self.controller.command(command)
        self.assertTrue(started.wait(1))
        self.controller.command(command)
        self.controller.command(command)
        release.set()
        self.wait()
        self.assertEqual(maximum, 1)
        self.assertEqual(calls, 2)
        self.assertEqual(len(list(self.downloads.iterdir())), 1)
