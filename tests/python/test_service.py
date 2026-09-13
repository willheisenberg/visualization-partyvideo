import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

SERVICE = Path(__file__).resolve().parents[2] / "visualization.partyvideo" / "service.py"


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.state = Path(self.temp.name) / "state.json"
        self.state.write_text(json.dumps({"source": "/storage/video.mp4"}))
        self.visible = {"Player.HasAudio", "Window.IsActive(visualisation)", "Player.ShowInfo"}
        self.kodi = types.SimpleNamespace(
            Monitor=object,
            Player=object,
            LOGINFO=1,
            LOGDEBUG=0,
            log=Mock(),
            getGlobalIdleTime=Mock(return_value=3),
            getCondVisibility=lambda name: name in self.visible,
            executeJSONRPC=Mock(return_value=json.dumps({"result": {"value": "visualization.partyvideo"}})),
            executebuiltin=Mock(side_effect=self.builtin),
        )
        spec = importlib.util.spec_from_file_location("partyvideo_service", SERVICE)
        self.service = importlib.util.module_from_spec(spec)
        with patch.dict(
            sys.modules, {"xbmc": self.kodi, "xbmcaddon": Mock(), "xbmcvfs": Mock(), "xbmcgui": Mock()}
        ):
            with patch.object(sys, "dont_write_bytecode", True):
                spec.loader.exec_module(self.service)

    def builtin(self, command):
        if command == "Action(Info)":
            self.visible.symmetric_difference_update({"Player.ShowInfo"})
        elif command == "ActivateWindow(visualisation)":
            self.visible.add("Window.IsActive(visualisation)")
        elif command.startswith("Dialog.Close("):
            dialog = command.split("(")[1].split(",")[0]
            self.visible.discard(f"Window.IsActive({dialog})")

    def test_info_is_hidden_without_toggling_back_on_retry(self):
        self.service.show_visualisation(self.state)
        self.service.show_visualisation(self.state)
        self.kodi.executebuiltin.assert_called_once_with("Action(Info)")

    def test_opens_visualisation_and_closes_music_overlay(self):
        self.visible.discard("Window.IsActive(visualisation)")
        self.visible.add("Window.IsActive(musicosd)")
        for _ in range(3):
            self.service.show_visualisation(self.state)
        self.assertIn("Window.IsActive(visualisation)", self.visible)
        self.assertNotIn("Window.IsActive(musicosd)", self.visible)
        self.assertNotIn("Player.ShowInfo", self.visible)

    def test_does_nothing_without_audio(self):
        self.visible.discard("Player.HasAudio")
        self.service.show_visualisation(self.state)
        self.kodi.executebuiltin.assert_not_called()

    def test_does_nothing_for_another_visualisation(self):
        self.kodi.executeJSONRPC.return_value = json.dumps({"result": {"value": "other"}})
        self.service.show_visualisation(self.state)
        self.kodi.executebuiltin.assert_not_called()

    def test_empty_missing_or_invalid_state_does_not_take_over_ui(self):
        for content in ("{}", '{"source":""}', "null", "[1]", "{"):
            with self.subTest(content=content):
                self.state.write_text(content)
                self.service.show_visualisation(self.state)
                self.kodi.executebuiltin.assert_not_called()
        self.state.unlink()
        self.service.show_visualisation(self.state)
        self.kodi.executebuiltin.assert_not_called()

    def test_audio_start_callback_schedules_refresh(self):
        player = self.service.Player()
        self.assertTrue(player.track_started.is_set())
        player.track_started.clear()
        player.onAVStarted()
        self.assertTrue(player.track_started.is_set())

    def test_manual_back_returns_only_after_idle_period(self):
        self.visible = {"Player.HasAudio", "Window.IsActive(home)"}
        self.kodi.getGlobalIdleTime.return_value = 2
        self.assertFalse(self.service.idle_return_due())
        self.kodi.getGlobalIdleTime.return_value = 3
        self.assertTrue(self.service.idle_return_due())
        self.service.show_visualisation(self.state)
        self.assertIn("Window.IsActive(visualisation)", self.visible)

    def test_settings_and_unrelated_dialogs_remain_open(self):
        self.visible = {"Player.HasAudio", "Window.IsActive(settings)"}
        self.assertFalse(self.service.idle_return_due())
        self.visible = {"Player.HasAudio", "Window.IsActive(home)", "System.HasModalDialog"}
        self.service.show_visualisation(self.state)
        self.kodi.executebuiltin.assert_not_called()

    def test_async_activation_is_checked_before_info_toggle(self):
        self.visible = {"Player.HasAudio", "Window.IsActive(home)", "Player.ShowInfo"}
        self.kodi.executebuiltin.side_effect = None  # GUI has not yet processed the command.
        self.service.show_visualisation(self.state)
        self.kodi.executebuiltin.assert_called_once_with("ActivateWindow(visualisation)")
