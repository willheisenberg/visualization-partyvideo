import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class CommandError(ValueError):
    pass


def youtube_url(url):
    if not isinstance(url, str):
        raise CommandError("invalid_url")
    try:
        parsed = urlsplit(url.strip())
        if parsed.scheme not in ("http", "https") or parsed.username or parsed.password or parsed.port:
            raise ValueError
        host = parsed.hostname
        if host == "youtu.be":
            video_id = parsed.path.strip("/")
        elif host in ("youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"):
            if parsed.path == "/watch":
                video_id = parse_qs(parsed.query).get("v", [""])[0]
            elif parsed.path.startswith("/shorts/"):
                video_id = parsed.path.removeprefix("/shorts/").strip("/")
            else:
                raise ValueError
        else:
            raise ValueError
        if not re.fullmatch(r"[A-Za-z0-9_-]{11}", video_id):
            raise ValueError
    except ValueError as exc:
        raise CommandError("invalid_url") from exc
    return f"https://www.youtube.com/watch?v={video_id}"


@dataclass(frozen=True)
class Command:
    action: str
    url: str = ""
    path: str = ""

    @classmethod
    def from_data(cls, data):
        if not isinstance(data, dict) or set(data) - {"action", "url", "path"}:
            raise CommandError("invalid_command")
        if not all(isinstance(value, str) for value in data.values()):
            raise CommandError("invalid_command")
        action, url, path = (data.get(key, "") for key in ("action", "url", "path"))
        if action not in ("play", "stop", "status", "update_tools", "toggle", "menu"):
            raise CommandError("invalid_command")
        if action == "play":
            if bool(url) == bool(path):
                raise CommandError("invalid_command")
            if url:
                url = youtube_url(url)
            elif not Path(path).is_absolute():
                raise CommandError("network_path_unsupported")
            elif not Path(path).is_file():
                raise CommandError("file_not_found")
        elif url or path:
            raise CommandError("invalid_command")
        return cls(action, url, path)


def parse_args(args):
    data = {}
    for argument in args:
        key, separator, value = argument.partition("=")
        if not separator or key in data:
            raise CommandError("invalid_command")
        data[key] = value
    return Command.from_data(data or {"action": "menu"})
