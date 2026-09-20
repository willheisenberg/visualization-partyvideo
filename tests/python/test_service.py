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
            LOGWARNING=2,
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

    def recovery(self):
        self.state.write_text(json.dumps({"source": "/storage/video.mp4", "revision": 12}))
        self.now = 0.0
        adapter = Mock()
        adapter.selected.return_value = self.service.ADDON_ID
        recovery = self.service.VisualisationRecovery(self.state.parent, adapter, lambda: self.now)
        self.assertFalse(recovery.tick())
        self.kodi.executebuiltin.side_effect = None  # Kodi processes commands asynchronously.
        return recovery

    def renderer(self, revision=12, state="playing"):
        (self.state.parent / "renderer.json").write_text(json.dumps({"revision": revision, "state": state}))

    def test_missing_renderer_reopens_only_after_window_has_closed(self):
        recovery = self.recovery()
        self.now = 4.9
        self.assertFalse(recovery.tick())
        self.now = 5.0
        self.assertTrue(recovery.tick())
        self.kodi.executebuiltin.assert_called_once_with("ActivateWindow(home)")
        self.now = 5.1
        self.assertTrue(recovery.tick())
        self.assertEqual(self.kodi.executebuiltin.call_count, 1)
        self.visible.discard("Window.IsActive(visualisation)")
        self.visible.add("Window.IsActive(home)")
        self.assertTrue(recovery.tick())
        self.assertEqual(self.kodi.executebuiltin.call_args.args, ("ActivateWindow(visualisation)",))
        self.renderer()
        self.now = 20
        self.assertFalse(recovery.tick())
        self.assertEqual(self.kodi.executebuiltin.call_count, 2)

    def test_ready_or_failed_renderer_never_reopens(self):
        for state in ("playing", "error"):
            with self.subTest(state=state):
                recovery = self.recovery()
                self.renderer(state=state)
                self.now = 6
                self.assertFalse(recovery.tick())
                self.kodi.executebuiltin.assert_not_called()

    def test_old_renderer_revision_does_not_confirm_new_source(self):
        recovery = self.recovery()
        self.renderer(revision=11)
        self.now = 6
        self.assertTrue(recovery.tick())

    def test_recovery_preserves_dialogs_screensaver_settings_and_recent_input(self):
        recovery = self.recovery()
        self.now = 6
        for condition in ("System.HasModalDialog", "System.ScreenSaverActive", "System.DPMSActive"):
            self.visible.add(condition)
            self.assertFalse(recovery.tick())
            self.visible.remove(condition)
        self.visible.discard("Player.HasAudio")
        self.assertFalse(recovery.tick())
        self.visible.add("Player.HasAudio")
        self.kodi.getGlobalIdleTime.return_value = 1
        self.assertFalse(recovery.tick())
        self.kodi.getGlobalIdleTime.return_value = 3
        recovery.adapter.selected.return_value = "other"
        self.assertFalse(recovery.tick())
        recovery.adapter.selected.return_value = self.service.ADDON_ID
        self.visible.discard("Window.IsActive(visualisation)")
        self.visible.add("Window.IsActive(settings)")
        self.assertFalse(recovery.tick())
        self.kodi.executebuiltin.assert_not_called()

    def test_stop_or_new_source_cancels_pending_reopen(self):
        for new_state in ({"revision": 13, "source": ""}, {"revision": 13, "source": "/other.mp4"}):
            recovery = self.recovery()
            self.now = 6
            self.assertTrue(recovery.tick())
            self.kodi.executebuiltin.reset_mock()
            self.state.write_text(json.dumps(new_state))
            self.assertFalse(recovery.tick())
            self.kodi.executebuiltin.assert_not_called()

    def test_window_change_timeout_does_not_repeat_navigation(self):
        recovery = self.recovery()
        self.now = 6
        self.assertTrue(recovery.tick())
        self.now = 9
        self.assertFalse(recovery.tick())
        self.now = 30
        self.assertFalse(recovery.tick())
        self.kodi.executebuiltin.assert_called_once_with("ActivateWindow(home)")

    def test_manual_navigation_during_recovery_is_not_overridden(self):
        recovery = self.recovery()
        self.now = 6
        self.assertTrue(recovery.tick())
        self.visible.discard("Window.IsActive(visualisation)")
        self.visible.add("Window.IsActive(settings)")
        self.assertFalse(recovery.tick())
        self.kodi.executebuiltin.assert_called_once_with("ActivateWindow(home)")

    def test_recovery_is_limited_to_two_attempts(self):
        recovery = self.recovery()
        for now in (6, 12):
            self.now = now
            self.visible = {"Player.HasAudio", "Window.IsActive(visualisation)"}
            self.assertTrue(recovery.tick())
            self.visible = {"Player.HasAudio", "Window.IsActive(home)"}
            self.assertTrue(recovery.tick())
        self.now = 30
        self.visible = {"Player.HasAudio", "Window.IsActive(visualisation)"}
        self.assertFalse(recovery.tick())
        self.assertEqual(self.kodi.executebuiltin.call_count, 4)
