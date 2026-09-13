"""Alle Zustandsänderungen im Service-Thread; Worker melden nur Ergebnisse."""

import queue
import shutil
import tempfile
import threading
import time
from dataclasses import asdict
from pathlib import Path

from .commands import Command
from .statefile import read_json, revision, write_json
from .tools import Cancelled
from .youtube import download


class Controller:
    def __init__(self, profile, temporary, adapter, tools, downloader=download, clock=time.monotonic):
        self.profile, self.temporary = Path(profile), Path(temporary)
        self.adapter, self.tools, self.downloader, self.clock = adapter, tools, downloader, clock
        self.events = queue.Queue()
        self.worker = None
        self.cancel = threading.Event()
        self.pending = None
        self.generation = 0
        self.job_directory = None
        self.last_progress = -float("inf")
        self.active = {"source": "", "kind": "", "title": ""}
        self.status = dict(self.active, state="idle", progress=None, error="", warning="", revision=0)

    def start(self):
        self.profile.mkdir(parents=True, exist_ok=True)
        self.temporary.mkdir(parents=True, exist_ok=True)
        old = read_json(self.profile / "state.json")
        if old.get("kind") == "file" and old.get("source"):
            write_json(self.profile / "last_selection.json", {"action": "play", "path": old["source"]})
        self.status["revision"] = max(
            revision(old.get("revision")), revision(read_json(self.profile / "renderer.json").get("revision"))
        )
        self._write_source("", "", "")  # Überholt auch alte Renderer-Meldungen nach Kodi-Neustart.
        self._restore()
        for path in self.temporary.iterdir():
            self._remove(path)
        self.tools.recover()
        self.publish("idle")

    def publish(self, state=None, **fields):
        if state:
            self.status["state"] = state
        self.status.update(fields)
        self.adapter.publish(dict(self.status))

    def fail(self, code):
        self.publish("error", error=str(code), progress=None)
        self.adapter.error(str(code))

    def _write_source(self, source, kind, title):
        rev = self.status["revision"] + 1
        write_json(self.profile / "state.json", dict(revision=rev, source=source, kind=kind, title=title))
        self.active = dict(source=source, kind=kind, title=title)
        self.status.update(self.active, revision=rev)

    def _remove(self, path):
        path = Path(path)
        # Niemals lokale Nutzervideos oder Ziele von Symlinks entfernen.
        if path.parent.resolve() == self.temporary.resolve():
            if path.is_symlink() or path.is_file():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path)

    def _remove_video(self, source):
        if source:
            path = Path(source)
            if path.parent.resolve() == self.temporary.resolve():
                self._remove(path)
            elif path.parent.parent.resolve() == self.temporary.resolve():
                self._remove(path.parent)

    def _activate(self):
        current = self.adapter.selected()
        previous = self.profile / "prev_visualisation.json"
        if current != self.adapter.addon_id:
            if not previous.exists():
                write_json(previous, {"previous": current})
            self.adapter.select(self.adapter.addon_id)
        self.adapter.open_visualisation()

    def _restore(self):
        path = self.profile / "prev_visualisation.json"
        previous = read_json(path).get("previous", "")
        if not isinstance(previous, str) or previous == self.adapter.addon_id:
            previous = ""
        if self.adapter.selected() == self.adapter.addon_id:
            self.adapter.select(previous)
        path.unlink(missing_ok=True)

    def _play(self, source, kind, title, selection):
        old = dict(self.active)
        self._activate()
        self._write_source(source, kind, title)
        write_json(self.profile / "last_selection.json", selection)
        if old["kind"] == "youtube" and old["source"] != source:
            self._remove_video(old["source"])
        self.publish("playing", progress=None, error="", warning="")

    def stop(self):
        self.generation += 1
        self.cancel.set()
        self.pending = None
        old = dict(self.active)
        self._write_source("", "", "")
        self._restore()
        if old["kind"] == "youtube":
            self._remove_video(old["source"])
        self.adapter.close_visualisation()
        self.publish("idle", progress=None, error="", warning="")

    def command(self, command):
        if command.action == "status":
            self.publish()
            return
        if command.action == "toggle":
            if self.active["source"] or self.status["state"] in ("installing_tools", "downloading"):
                self.stop()
                return
            selection = read_json(self.profile / "last_selection.json")
            command = Command.from_data(selection)
        if command.action == "stop":
            self.stop()
            return
        if command.action not in ("play", "update_tools"):
            raise ValueError("invalid_command")
        self.generation += 1
        self.cancel.set()
        self.pending = None
        if command.path:
            self._play(command.path, "file", Path(command.path).name, asdict(command))
        else:
            self.pending = command
            self.publish(
                "installing_tools"
                if command.action == "update_tools" or not self.tools.ready()
                else "downloading",
                progress=0,
                error="",
                warning="",
            )
            self._launch()

    def _launch(self):
        if self.worker is not None or self.pending is None:
            return
        command, self.pending = self.pending, None
        generation = self.generation
        cancel = self.cancel = threading.Event()
        job = Path(tempfile.mkdtemp(prefix="download-", dir=self.temporary))
        self.job_directory = job
        height = self.adapter.max_height()

        def send(event, payload):
            self.events.put((generation, event, payload))

        def work():
            try:
                if command.action == "update_tools" or not self.tools.ready():
                    try:
                        self.tools.install(cancel, lambda n: send("progress", n))
                    except Cancelled:
                        raise
                    except Exception as exc:
                        send("log", str(exc))
                        raise RuntimeError("tools_install_failed") from exc
                if cancel.is_set():
                    raise Cancelled
                if command.url:
                    send("downloading", None)
                    source, title = self.downloader(
                        command.url,
                        job,
                        self.tools.directory,
                        height,
                        cancel,
                        lambda n: send("progress", n),
                        lambda msg: send("log", msg),
                    )
                    send("done", (source, title, asdict(command)))
                else:
                    send("updated", None)
            except Cancelled:
                pass
            except Exception as exc:
                send("failed", str(exc))
            finally:
                send("finished", None)

        self.worker = threading.Thread(target=work, name="partyvideo-download", daemon=True)
        self.worker.start()

    def tick(self):
        # Alle Ereignisse werden vom Kodi-Service-Thread verarbeitet, niemals vom Worker.
        while True:
            try:
                generation, event, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if event == "finished":
                self.worker.join()
                self.worker = None
                if not self.active["source"] or Path(self.active["source"]).parent != self.job_directory:
                    self._remove(self.job_directory)
                self.job_directory = None
                self._launch()
            elif generation != self.generation:
                continue  # Ein abgebrochener Download darf niemals später wieder aktivieren.
            elif event == "progress":
                if self.clock() - self.last_progress >= 2:
                    self.last_progress = self.clock()
                    self.publish(progress=max(0, min(100, int(payload))))
            elif event == "downloading":
                self.publish("downloading", progress=0)
            elif event == "done":
                source, title, selection = payload
                try:
                    self._play(source, "youtube", title, selection)
                except Exception as exc:
                    self.fail(str(exc))
            elif event == "updated":
                self.publish("playing" if self.active["source"] else "idle", progress=None, error="")
            elif event == "failed":
                self.fail(payload)
            elif event == "log":
                self.adapter.log(payload)
        renderer = read_json(self.profile / "renderer.json")
        if self.active["source"] and renderer.get("revision") == self.status["revision"]:
            error, warning = renderer.get("error", ""), renderer.get("warning", "")
            if renderer.get("state") == "error" and error and self.status["error"] != error:
                self.fail(error)
            elif warning != self.status["warning"]:
                self.publish(warning=warning)

    def shutdown(self):
        self.cancel.set()
        # Passt zu Socket-Timeout und begrenzten Retries; auf dem Kodi-Thread nicht blockieren.
        if self.worker:
            self.worker.join(timeout=2)
