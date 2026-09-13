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
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "zbo6jUGrwdk.mp4"
            target.touch()
            captured = {}

            class Fake:
                def __init__(self, options):
                    captured.update(options)

                def __enter__(self):
                    return self

                def __exit__(self, *args):
                    pass

                def extract_info(self, url, download):
                    return {"id": "zbo6jUGrwdk", "title": "Test"}

                def prepare_filename(self, info):
                    return str(target)

            result = download(
                "https://youtu.be/zbo6jUGrwdk",
                directory,
                "/tools",
                1080,
                threading.Event(),
                lambda value: None,
                lambda value: None,
                factory=Fake,
            )
            self.assertEqual(result, (str(target), "Test"))
            self.assertTrue(captured["noplaylist"])
            self.assertEqual(captured["fixup"], "never")
            self.assertEqual(captured["js_runtimes"], {"deno": {"path": "/tools/deno"}})
