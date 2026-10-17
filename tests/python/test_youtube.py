import sys
import tempfile
import threading
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "visualization.partyvideo/resources/lib"))
sys.dont_write_bytecode = True

from partyvideo.commands import CommandError, parse_args, youtube_url  # noqa: E402
from partyvideo.youtube import download, format_chain  # noqa: E402


class YoutubeTests(unittest.TestCase):
    def test_supported_urls_are_normalized_without_playlist(self):
        expected = "https://www.youtube.com/watch?v=zbo6jUGrwdk"
        for url in (
            "https://youtu.be/zbo6jUGrwdk?t=20",
            expected + "&list=whatever",
            "https://www.youtube.com/shorts/zbo6jUGrwdk",
        ):
            self.assertEqual(youtube_url(url), expected)

    def test_foreign_hosts_and_malformed_ids_rejected(self):
        for url in (
            "https://youtube.com.attacker/watch?v=zbo6jUGrwdk",
            "file:///tmp/a",
            "https://youtu.be/no",
            "https://youtube.com@evil.com/watch?v=zbo6jUGrwdk",
            "https://youtu.be:123/zbo6jUGrwdk",
        ):
            with self.subTest(url=url), self.assertRaises(CommandError):
                youtube_url(url)

    def test_no_arguments_open_menu(self):
        self.assertEqual(parse_args([]).action, "menu")

    def test_arguments_keep_equals_and_reject_ambiguous_commands(self):
        command = parse_args(["action=play", "url=https://www.youtube.com/watch?v=zbo6jUGrwdk"])
        self.assertIn("watch?v=", command.url)
        for args in (["action=stop", "action=play"], ["action=play"], ["action=oops"], ["path=smb://a"]):
            with self.assertRaises(CommandError):
                parse_args(args)

    def test_format_chain_matches_spec(self):
        self.assertEqual(
            format_chain(720),
            "bestvideo[vcodec^=avc1][height<=720][fps<=30]/"
            "bestvideo[vcodec^=avc1][height<=720]/best[vcodec^=avc1][height<=720]",
        )
        self.assertNotIn("+", format_chain(1080))

    def test_download_options_use_deno_no_playlist_or_ffmpeg_merge(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zbo6jUGrwdk.mp4"
            target.touch()
            seen = {}

            def popen(command, **kwargs):
                seen["command"] = command
                return FakeTokenProcess([f"PARTYVIDEO-RESULT\t{target}\tTest"])

            with patch("subprocess.Popen", popen), patch("shutil.which", return_value="/usr/bin/python3"):
                result = download(
                    "https://youtu.be/zbo6jUGrwdk", directory, "/tools", 1080,
                    threading.Event(), lambda value: None, lambda value: None,
                )  # fmt: skip
            command = seen["command"]
            self.assertEqual(result, (str(target), "Test"))
            self.assertIn("--no-playlist", command)
            self.assertEqual(command[command.index("--fixup") + 1], "never")
            self.assertEqual(command[command.index("--js-runtimes") + 1], "deno:/tools/deno")


def fake_fetch(behaviours, target, attempts):
    """Ersetzt den Download im eigenen Prozess: Ausnahmen werden zu dessen DownloadError-Gründen."""
    from partyvideo.youtube import DownloadError

    def fetch(url, directory, tools, height, cancel, progress, log):
        attempts.append(url)
        outcome = behaviours[len(attempts) - 1]
        if isinstance(outcome, Exception):
            missing = "Requested format is not available" in str(outcome)
            raise DownloadError("no_suitable_format" if missing else "download_failed") from outcome
        return str(target), str(outcome.get("title") or outcome.get("id"))

    return fetch


class RetryTests(unittest.TestCase):
    """Ein 403 trifft die signierte Medien-URL; nur eine frische Auflösung hilft."""

    def setUp(self):
        # Die echte Pause würde die Suite nur ausbremsen.
        from partyvideo import youtube

        self._pause = youtube.RETRY_PAUSE_SECONDS
        youtube.RETRY_PAUSE_SECONDS = 0.0

    def tearDown(self):
        from partyvideo import youtube

        youtube.RETRY_PAUSE_SECONDS = self._pause

    def run_download(self, behaviours, directory, target, cancel=None, provider=None):
        attempts = []
        result = download(
            "https://youtu.be/zbo6jUGrwdk",
            directory,
            "/tools",
            1080,
            cancel or threading.Event(),
            lambda value: None,
            lambda value: None,
            fetch=fake_fetch(behaviours, target, attempts),
            provider=provider,
        )
        return result, attempts

    def test_second_attempt_succeeds_after_a_403(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zbo6jUGrwdk.mp4"
            target.touch()
            behaviours = [
                Exception("unable to download video data: HTTP Error 403: Forbidden"),
                {"id": "zbo6jUGrwdk", "title": "Test"},
            ]
            result, attempts = self.run_download(behaviours, directory, target)
            self.assertEqual(result, (str(target), "Test"))
            self.assertEqual(len(attempts), 2, "keine zweite Aufloesung versucht")

    def test_gives_up_after_the_retry(self):
        from partyvideo.youtube import DownloadError

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zbo6jUGrwdk.mp4"
            target.touch()
            behaviours = [Exception("HTTP Error 403: Forbidden")] * 3
            with self.assertRaises(DownloadError) as caught:
                self.run_download(behaviours, directory, target)
            self.assertEqual(str(caught.exception), "download_failed")

    def test_missing_format_is_not_retried(self):
        from partyvideo.youtube import DownloadError

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zbo6jUGrwdk.mp4"
            target.touch()
            behaviours = [Exception("Requested format is not available")] * 3
            with self.assertRaises(DownloadError) as caught:
                self.run_download(behaviours, directory, target)
            self.assertEqual(str(caught.exception), "no_suitable_format")

    def test_cancelling_is_not_retried(self):
        from partyvideo.tools import Cancelled

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zbo6jUGrwdk.mp4"
            target.touch()
            cancel = threading.Event()
            cancel.set()
            behaviours = [Exception("stopped")] * 3
            with self.assertRaises(Cancelled):
                self.run_download(behaviours, directory, target, cancel=cancel)


class FakeProvider:
    def __init__(self, starts=True):
        self.starts, self.events = starts, []

    def start(self, cancel, log):
        self.events.append("start")
        return self.starts

    def stop(self):
        self.events.append("stop")


class TokenRetryTests(unittest.TestCase):
    """Nach einem Fehlschlag lädt der zweite Anlauf mit PO-Token, wenn Docker läuft."""

    def run_download(self, behaviours, directory, provider, runner):
        attempts = []
        result = download(
            "https://youtu.be/zbo6jUGrwdk",
            directory,
            "/tools",
            1080,
            threading.Event(),
            lambda value: None,
            lambda value: None,
            fetch=fake_fetch(behaviours, Path(directory) / "zbo6jUGrwdk.mp4", attempts),
            provider=provider,
            runner=runner,
        )
        return result, attempts

    def test_token_attempt_runs_outside_and_the_service_is_removed(self):
        with tempfile.TemporaryDirectory() as directory:
            provider, calls = FakeProvider(), []

            def runner(url, target, tools, height, cancel, progress, log):
                calls.append((url, str(target), tools, height))
                return "/x/video.mp4", "Titel"

            result, attempts = self.run_download([Exception("HTTP Error 403")], directory, provider, runner)
            self.assertEqual(result, ("/x/video.mp4", "Titel"))
            self.assertEqual(len(attempts), 1)
            url = "https://www.youtube.com/watch?v=zbo6jUGrwdk"
            self.assertEqual(calls, [(url, directory, "/tools", 1080)])
            self.assertEqual(provider.events, ["start", "stop"])

    def test_without_a_service_the_retry_stays_a_fresh_resolution(self):
        from partyvideo import youtube

        pause, youtube.RETRY_PAUSE_SECONDS = youtube.RETRY_PAUSE_SECONDS, 0.0
        self.addCleanup(setattr, youtube, "RETRY_PAUSE_SECONDS", pause)
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "zbo6jUGrwdk.mp4").touch()
            provider = FakeProvider(starts=False)
            behaviours = [Exception("HTTP Error 403"), {"id": "zbo6jUGrwdk", "title": "Test"}]
            _, attempts = self.run_download(behaviours, directory, provider, self.fail)
            self.assertEqual(len(attempts), 2)

    def test_service_is_not_started_when_the_first_attempt_works(self):
        with tempfile.TemporaryDirectory() as directory:
            (Path(directory) / "zbo6jUGrwdk.mp4").touch()
            provider = FakeProvider()
            self.run_download([{"id": "zbo6jUGrwdk", "title": "Test"}], directory, provider, self.fail)
            self.assertNotIn("start", provider.events)

    def test_token_attempt_is_repeated_once_then_the_service_is_removed(self):
        from partyvideo import youtube
        from partyvideo.youtube import DownloadError

        pause, youtube.RETRY_PAUSE_SECONDS = youtube.RETRY_PAUSE_SECONDS, 0.0
        self.addCleanup(setattr, youtube, "RETRY_PAUSE_SECONDS", pause)
        tries = []

        def runner(*args):
            tries.append(1)
            raise DownloadError("download_failed")

        with tempfile.TemporaryDirectory() as directory:
            provider = FakeProvider()
            with self.assertRaises(DownloadError):
                self.run_download([Exception("HTTP Error 403")], directory, provider, runner)
            self.assertEqual(len(tries), 2)
            self.assertEqual(provider.events, ["start", "stop"])

    def test_missing_format_with_token_is_not_repeated(self):
        from partyvideo.youtube import DownloadError

        tries = []

        def runner(*args):
            tries.append(1)
            raise DownloadError("no_suitable_format")

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DownloadError):
                self.run_download([Exception("HTTP Error 403")], directory, FakeProvider(), runner)
            self.assertEqual(len(tries), 1)


class FakeTokenProcess:
    def __init__(self, lines, returncode=0):
        self.stdout, self.returncode, self.killed = iter(lines), None, False
        self._code = returncode

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True

    def wait(self):
        self.returncode = -9 if self.killed else self._code
        return self.returncode


class TokenProcessTests(unittest.TestCase):
    def run_token(self, lines, directory, returncode=0, cancel=None):
        from partyvideo.youtube import token_download

        self.commands, self.environments, self.progress, self.logged = [], [], [], []

        def popen(command, **kwargs):
            self.commands.append(command)
            self.environments.append(kwargs["env"])
            self.process = FakeTokenProcess(lines, returncode)
            return self.process

        return token_download(
            "https://www.youtube.com/watch?v=zbo6jUGrwdk",
            directory,
            "/tools",
            720,
            cancel or threading.Event(),
            self.progress.append,
            self.logged.append,
            popen=popen,
            interpreter="/usr/bin/python3",
        )

    def test_result_progress_and_command_line(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zbo6jUGrwdk.mp4"
            target.touch()
            lines = [
                "[youtube] irgendwas\n",
                "PARTYVIDEO-PROGRESS\t50\t200\n",
                "PARTYVIDEO-PROGRESS\t200\tNA\n",
                f"PARTYVIDEO-RESULT\t{target}\tMein\tTitel\n",
            ]
            self.assertEqual(self.run_token(lines, directory), (str(target.resolve()), "Mein\tTitel"))
            self.assertEqual(self.progress, [25])
            command = self.commands[0]
            self.assertEqual(command[:2], ["/usr/bin/python3", "/tools/yt-dlp"])
            self.assertIn("youtube:player_client=mweb", command)
            self.assertIn("deno:/tools/deno", command)
            self.assertIn("height<=720", command[command.index("--format") + 1])
            self.assertEqual(self.environments[0]["PYTHONPATH"], "/tools/pot-plugin.zip")

    def test_errors_are_logged_and_reported(self):
        from partyvideo.youtube import DownloadError

        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(DownloadError) as caught:
                self.run_token(["ERROR: HTTP Error 403: Forbidden\n"], directory, returncode=1)
            self.assertEqual(str(caught.exception), "download_failed")
            self.assertEqual(self.logged, ["ERROR: HTTP Error 403: Forbidden"])
            with self.assertRaises(DownloadError) as caught:
                self.run_token(["ERROR: Requested format is not available\n"], directory, returncode=1)
            self.assertEqual(str(caught.exception), "no_suitable_format")

    def test_result_outside_the_job_directory_is_rejected(self):
        from partyvideo.youtube import DownloadError

        with tempfile.TemporaryDirectory() as directory, tempfile.NamedTemporaryFile() as other:
            with self.assertRaises(DownloadError):
                self.run_token([f"PARTYVIDEO-RESULT\t{other.name}\tX\n"], directory)

    def test_cancel_kills_the_process(self):
        from partyvideo.tools import Cancelled

        cancel = threading.Event()
        cancel.set()
        with tempfile.TemporaryDirectory() as directory, self.assertRaises(Cancelled):
            self.run_token([], directory, cancel=cancel)
        self.assertTrue(self.process.killed)


class OwnProcessTests(unittest.TestCase):
    """yt-dlp nie in Kodis Python: '\\N{…}' in YoutubeDL.py ließ Kodi nach Service-Neustart abstürzen."""

    def test_download_runs_yt_dlp_in_its_own_process_without_token_plugin(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zbo6jUGrwdk.mp4"
            target.touch()
            seen = {}

            def popen(command, **kwargs):
                seen["command"], seen["env"] = command, kwargs["env"]
                return FakeTokenProcess([f"PARTYVIDEO-RESULT\t{target}\tTitel"])

            before = set(sys.modules)
            with patch("subprocess.Popen", popen), patch("shutil.which", return_value="/usr/bin/python3"):
                result = download(
                    "https://youtu.be/zbo6jUGrwdk", directory, "/tools", 1080,
                    threading.Event(), lambda value: None, lambda value: None,
                )  # fmt: skip
            self.assertEqual(result, (str(target), "Titel"))
            self.assertFalse({m for m in set(sys.modules) - before if m.startswith("yt_dlp")})
            self.assertEqual(seen["command"][:2], ["/usr/bin/python3", "/tools/yt-dlp"])
            self.assertNotIn("--extractor-args", seen["command"])
            self.assertNotIn("PYTHONPATH", seen["env"])
            self.assertIn("--no-playlist", seen["command"])
            self.assertIn("never", seen["command"][seen["command"].index("--fixup") + 1])
