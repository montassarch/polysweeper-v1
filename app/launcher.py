"""PolySweeper.exe: starts the desktop app (app/polysweeper_app.py) from the project folder.

Built into a single Windows .exe by GitHub Actions (.github/workflows/build-app.yml) with PyInstaller.
The exe holds its own Python and Tk, so the PC's Python is not used. It loads the app's code from the
project folder at start, so app updates arrive with the normal git pull: the exe itself rarely changes.

Where is the project? The folder that has code/polysweeper in it: next to the exe or above it (the
autopilot installs the exe in <project>/app/bin/), else the folder remembered in
%APPDATA%/PolySweeper/project.txt, else the owner picks it once.

  PolySweeper.exe                  normal start
  PolySweeper.exe --selftest DIR   build check: show the window ~10 s, write DIR/selftest.json, exit
"""
from __future__ import annotations

# Everything the app (or a later version of it) may import must be bundled into the exe here.
import base64, collections, csv, ctypes, dataclasses, datetime, functools, hashlib, http.client, io  # noqa: F401,E401
import itertools, json, math, os, pathlib, platform, queue, random, re, shutil, socket, ssl  # noqa: F401,E401
import statistics, struct, subprocess, sys, textwrap, threading, time, traceback, typing  # noqa: F401,E401
import urllib.error, urllib.parse, urllib.request, webbrowser, zipfile  # noqa: F401,E401
import tkinter, tkinter.filedialog, tkinter.font, tkinter.messagebox, tkinter.ttk  # noqa: F401,E401
from pathlib import Path

CONFIG = Path(os.environ.get("APPDATA") or Path.home()) / "PolySweeper" / "project.txt"


def is_project(p):
    return p is not None and (Path(p) / "code" / "polysweeper").is_dir() and (Path(p) / "app" / "polysweeper_app.py").is_file()


def find_project():
    here = Path(sys.executable if getattr(sys, "frozen", False) else __file__).resolve().parent
    for p in [here, *here.parents][:5]:
        if is_project(p):
            return p
    try:
        p = Path(CONFIG.read_text(encoding="utf-8").strip())
        if is_project(p):
            return p
    except OSError:
        pass
    return None


def ask_project():
    from tkinter import filedialog, messagebox
    root = tkinter.Tk()
    root.withdraw()
    messagebox.showinfo("PolySweeper", "Please choose the PolySweeper project folder\n"
                        "(the folder that has CLAUDE.md, code and PolySweeper-V1 in it).")
    p = filedialog.askdirectory(title="Choose the PolySweeper project folder")
    root.destroy()
    if p and is_project(p):
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        CONFIG.write_text(str(Path(p)), encoding="utf-8")
        return Path(p)
    return None


def fail(msg, selftest_dir=None):
    if selftest_dir:
        Path(selftest_dir).mkdir(parents=True, exist_ok=True)
        (Path(selftest_dir) / "selftest.json").write_text(json.dumps({"ok": False, "problems": [msg]}, indent=2))
        return 1
    try:
        log = CONFIG.parent / "error.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text(msg, encoding="utf-8")
        root = tkinter.Tk()
        root.withdraw()
        tkinter.messagebox.showerror("PolySweeper", msg[-1500:] + f"\n\n(Saved in {log})")
        root.destroy()
    except Exception:
        pass
    return 1


def main():
    argv = sys.argv[1:]
    selftest = argv[argv.index("--selftest") + 1] if "--selftest" in argv and argv.index("--selftest") + 1 < len(argv) else None
    if os.name == "nt":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)      # sharp text on high-resolution screens
        except Exception:
            pass
    project = find_project() or (None if selftest else ask_project())
    if project is None:
        return fail("The PolySweeper project folder was not found.", selftest)
    sys.path[:0] = [str(project / "app"), str(project / "code")]
    try:
        import polysweeper_app
        return polysweeper_app.main(project, argv)
    except SystemExit as e:
        return int(e.code or 0)
    except Exception:
        return fail("PolySweeper could not start:\n\n" + traceback.format_exc(), selftest)


if __name__ == "__main__":
    sys.exit(main())
