import importlib
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "visualization.partyvideo/resources/lib"))
sys.dont_write_bytecode = True


class UiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.profile = Path(self.directory.name)
        self.dialog = Mock()
        self.window = Mock()
        self.adapter = types.ModuleType("partyvideo.kodi")
        self.adapter.ADDON_ID = "visualization.partyvideo"
        self.adapter.paths = lambda: (self.profile, self.profile / "temp")
        self.adapter.send = Mock()
        kodi = {
            "xbmcgui": types.SimpleNamespace(
                Dialog=lambda: self.dialog, Window=lambda _: self.window, NOTIFICATION_ERROR="error"
            ),
            "xbmcaddon": Mock(),
            "partyvideo.kodi": self.adapter,
        }
        with patch.dict(sys.modules, kodi):
            sys.modules.pop("partyvideo.ui", None)
            self.ui = importlib.import_module("partyvideo.ui")

    def test_interactive_first_download_requires_confirmation(self):
        self.dialog.yesno.return_value = False
        self.ui.dispatch({"action": "play", "url": "https://youtu.be/zbo6jUGrwdk"}, interactive=True)
        self.adapter.send.assert_not_called()
        self.dialog.yesno.return_value = True
        self.ui.dispatch({"action": "play", "url": "https://youtu.be/zbo6jUGrwdk"}, interactive=True)
        self.assertEqual(self.adapter.send.call_args.args[0]["action"], "play")

    def test_bot_command_does_not_open_confirmation(self):
        self.ui.dispatch({"action": "play", "url": "https://youtu.be/zbo6jUGrwdk"})
        self.dialog.yesno.assert_not_called()
        self.adapter.send.assert_called_once()

    def test_running_visual_toggle_only_sends_stop(self):
        self.window.getProperty.return_value = "/tmp/video.mp4"
        self.ui.toggle()
        self.assertEqual(self.adapter.send.call_args.args[0]["action"], "stop")

    def test_menu_youtube_selection_sends_normalized_url(self):
        self.dialog.select.return_value = 1
        self.dialog.input.return_value = "https://youtu.be/zbo6jUGrwdk"
        self.dialog.yesno.return_value = True
        self.ui.menu()
        self.assertEqual(
            self.adapter.send.call_args.args[0]["url"], "https://www.youtube.com/watch?v=zbo6jUGrwdk"
        )

    def test_cancel_menu_does_not_send_command(self):
        self.dialog.select.return_value = -1
        self.ui.menu()
        self.adapter.send.assert_not_called()

    def test_first_menu_item_disables_active_visual(self):
        self.window.getProperty.return_value = "/tmp/video.mp4"
        self.dialog.select.return_value = 0
        with patch.object(self.ui, "text", side_effect=lambda number: str(number)):
            self.ui.menu()
        self.assertEqual(self.dialog.select.call_args.args[1][0], "32003")
        self.assertEqual(self.adapter.send.call_args.args[0]["action"], "stop")

    def test_first_menu_item_enables_saved_source(self):
        self.window.getProperty.return_value = ""
        video = self.profile / "video.mp4"
        video.touch()
        import json

        (self.profile / "last_selection.json").write_text(json.dumps({"action": "play", "path": str(video)}))
        self.dialog.select.return_value = 0
        with patch.object(self.ui, "text", side_effect=lambda number: str(number)):
            self.ui.menu()
        self.assertEqual(self.dialog.select.call_args.args[1][0], "32015")
        self.assertEqual(self.adapter.send.call_args.args[0]["path"], str(video))
