import subprocess
import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "visualization.partyvideo/resources/lib"))
sys.dont_write_bytecode = True

from partyvideo import pot  # noqa: E402
from partyvideo.tools import Cancelled  # noqa: E402


class FakeProcess:
    def __init__(self, returncode=0, hangs=False):
        self.returncode = None if hangs else returncode
        self.killed = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self):
        return self.returncode


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.docker = Path(self.temp.name) / "docker"
        self.docker.touch()
        self.started = []
        self.removed = []
        self.process = FakeProcess()
        self.answers = True
        self.logged = []
        self.images = ""
        self.image_calls = []

    def provider(self, docker=None):
        def popen(command, **kwargs):
            self.started.append(command)
            return self.process

        def run(command, **kwargs):
            if command[1] == "image":
                self.image_calls.append(command[2:])
                return subprocess.CompletedProcess(command, 0, stdout=self.images)
            self.removed.append(command)
            return subprocess.CompletedProcess(command, 0)

        return pot.Provider(docker or self.docker, popen, run, lambda: self.answers)

    def test_without_docker_nothing_is_started(self):
        provider = self.provider(docker=Path(self.temp.name) / "missing")
        self.assertFalse(provider.start(threading.Event(), self.logged.append))
        provider.stop(force=True)
        self.assertEqual((self.started, self.removed), ([], []))

    def test_start_runs_the_pinned_image_locked_down_on_localhost(self):
        provider = self.provider()
        self.assertTrue(provider.start(threading.Event(), self.logged.append))
        command = self.started[0]
        self.assertEqual(command[-1], f"brainicism/bgutil-ytdlp-pot-provider:{pot.VERSION}")
        self.assertIn("127.0.0.1:4416:4416", command)
        for flag in ("--rm", "--read-only", "no-new-privileges"):
            self.assertIn(flag, command)
        self.assertEqual(command[command.index("--cap-drop") + 1], "ALL")

    def test_stop_removes_the_container_only_after_a_start(self):
        provider = self.provider()
        provider.stop()
        self.assertEqual(self.removed, [])
        provider.start(threading.Event(), self.logged.append)
        self.removed.clear()  # start räumt vorab einen alten Container weg
        provider.stop()
        provider.stop()
        self.assertEqual(self.removed, [[str(self.docker), "rm", "-f", pot.CONTAINER]])

    def test_images_of_other_versions_are_removed_after_a_start(self):
        self.images = f"aaa {pot.REPOSITORY}:1.9.0\nbbb {pot.IMAGE}\nccc {pot.REPOSITORY}:<none>\n"
        self.provider().start(threading.Event(), self.logged.append)
        removed = [call[1] for call in self.image_calls if call[0] == "rm"]
        self.assertEqual(removed, ["aaa", "ccc"])

    def test_failed_docker_run_is_reported_and_cleaned_up(self):
        self.process = FakeProcess(returncode=125)
        provider = self.provider()
        self.assertFalse(provider.start(threading.Event(), self.logged.append))
        self.assertIn("125", self.logged[0])

    def test_silent_service_gives_up_and_removes_the_container(self):
        self.answers = False
        timeout = pot.READY_TIMEOUT_SECONDS
        pot.READY_TIMEOUT_SECONDS = 0.0
        self.addCleanup(setattr, pot, "READY_TIMEOUT_SECONDS", timeout)
        provider = self.provider()
        self.assertFalse(provider.start(threading.Event(), self.logged.append))
        self.assertEqual(self.removed[-1][1:], ["rm", "-f", pot.CONTAINER])
        self.assertFalse(provider.active)

    def test_cancel_during_the_image_pull_kills_docker_run(self):
        self.process = FakeProcess(hangs=True)
        cancel = threading.Event()
        cancel.set()
        provider = self.provider()
        with self.assertRaises(Cancelled):
            provider.start(cancel, self.logged.append)
        self.assertTrue(self.process.killed)
        self.assertEqual(self.removed[-1][1:], ["rm", "-f", pot.CONTAINER])


if __name__ == "__main__":
    unittest.main()
