from dataclasses import asdict

import xbmcaddon
import xbmcgui

from .commands import Command
from .kodi import ADDON_ID, paths, send
from .statefile import read_json


def text(number):
    return xbmcaddon.Addon(ADDON_ID).getLocalizedString(number)


def error(code):
    codes = [
        "invalid_url",
        "network_path_unsupported",
        "file_not_found",
        "tools_install_failed",
        "download_failed",
        "no_suitable_format",
        "open_failed",
        "no_video_stream",
        "unsupported_codec",
        "decode_failed",
        "invalid_command",
    ]
    message = text(32100 + codes.index(code)) if code in codes else code
    xbmcgui.Dialog().notification("Party Video", message, xbmcgui.NOTIFICATION_ERROR, 5000)


def confirm_tools():
    profile, _ = paths()
    if not (profile / "tools" / "versions.json").is_file():
        return xbmcgui.Dialog().yesno("Party Video", text(32009))
    return True


def dispatch(command, interactive=False):
    command = Command.from_data(command)
    if interactive and (command.url or command.action == "update_tools") and not confirm_tools():
        return
    send(asdict(command))


def active():
    window = xbmcgui.Window(10000)
    return bool(window.getProperty("partyvideo.source")) or window.getProperty("partyvideo.state") in (
        "installing_tools",
        "downloading",
    )


def choose_source(choice):
    dialog = xbmcgui.Dialog()
    if choice == 0:
        url = dialog.input(text(32001))
        if url:
            dispatch({"action": "play", "url": url}, interactive=True)
    elif choice == 1:
        path = dialog.browse(1, text(32002), "video", ".mp4|.mkv|.webm|.mov")
        if path:
            dispatch({"action": "play", "path": path})


def menu():
    dialog = xbmcgui.Dialog()
    labels = [text(32003 if active() else 32015)] + [text(n) for n in (32001, 32002, 32004, 32005)]
    choice = dialog.select("Party Video", labels)
    if choice == 0:
        toggle()
    elif choice in (1, 2):
        choose_source(choice - 1)
    elif choice == 3:
        dispatch({"action": "status"})
        window = xbmcgui.Window(10000)
        dialog.textviewer(
            "Party Video",
            "\n".join(
                f"{field}: {window.getProperty('partyvideo.' + field)}"
                for field in ("state", "title", "progress", "error", "warning")
            ),
        )
    elif choice == 4:
        dispatch({"action": "update_tools"}, interactive=True)


def toggle():
    if active():
        dispatch({"action": "stop"})
    else:
        profile, _ = paths()
        selection = read_json(profile / "last_selection.json")
        if not selection:
            dialog = xbmcgui.Dialog()
            choose_source(dialog.select("Party Video", [text(32001), text(32002)]))
        else:
            dispatch(selection, interactive=True)
