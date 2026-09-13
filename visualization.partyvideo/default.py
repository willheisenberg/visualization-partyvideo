"""Quellenmenü mit An-/Aus-Schalter und JSON-RPC-Befehlseinstieg."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "resources" / "lib"))
sys.dont_write_bytecode = True

from partyvideo import ui  # noqa: E402
from partyvideo.commands import parse_args  # noqa: E402


def main():
    try:
        command = parse_args(sys.argv[1:])
        if command.action == "menu":
            ui.menu()
        elif command.action == "toggle":
            ui.toggle()
        else:
            from dataclasses import asdict

            ui.dispatch(asdict(command))
    except (OSError, ValueError, RuntimeError) as exc:
        ui.error(str(exc))


if __name__ == "__main__":
    main()
