"""Autopilot: keeps shadow mode running and up to date on the owner's PC, with no clicks.

  1. On start: pull the latest code from GitHub, then start shadow mode.
  2. Every 10 minutes: if GitHub has a newer version, stop shadow mode, pull, restart it.
  3. Every 3 hours: commit and push the shadow data files so they can be analysed.
  4. If shadow mode crashes, restart it after 30 seconds.

It only ever commits the shadow data files (trades, events, errors). Notes are left alone.
stop_shadow.bat stops shadow mode AND the autopilot. Everything is logged to data/shadow/autopilot.log.
Nothing here can place a real order.

Exit code 3 means "I updated myself, start me again" (autopilot.bat does that).
"""
from __future__ import annotations

import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

CODE = Path(__file__).resolve().parent.parent      # .../code
REPO = CODE.parent
SHADOW_DIR = CODE / "data" / "shadow"
STOP = SHADOW_DIR / "STOP"
LOG = SHADOW_DIR / "autopilot.log"
DATA_FILES = ["code/data/shadow/trades.jsonl", "code/data/shadow/events.jsonl", "code/data/shadow/errors.jsonl"]
BRANCH = "main"
CHECK_EVERY = 10 * 60
SYNC_EVERY = 3 * 60 * 60
RESTART_DELAY = 30
SELF_UPDATE = 3


def log(msg):
    line = f"[{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')} UTC] autopilot: {msg}"
    print(line, flush=True)
    try:
        SHADOW_DIR.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def git(*args, timeout=120):
    """Run git in the repo. Returns (ok, output)."""
    try:
        r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, str(e)


def head():
    return git("rev-parse", "HEAD")[1]


def update_available():
    ok, out = git("fetch", "origin", BRANCH)
    if not ok:
        log(f"could not check GitHub for updates ({out[:200]})")
        return False
    ok, out = git("rev-list", "--count", f"HEAD..origin/{BRANCH}")
    return ok and out.strip().isdigit() and int(out) > 0


def pull():
    """Bring in the latest code. On any problem keep the current version and say why."""
    before = head()
    ok, out = git("pull", "--rebase", "--autostash", "origin", BRANCH)
    if not ok:
        git("rebase", "--abort")
        # data files only grow, so on a conflict the copy on this PC is the complete one
        ok, out = git("pull", "--no-rebase", "--no-edit", "-X", "ours", "origin", BRANCH)
        if not ok:
            git("merge", "--abort")
            log(f"pull FAILED, keeping the current version ({out[:300]})")
            return set()
    ok, changed = git("diff", "--name-only", before, "HEAD")
    files = set(changed.split()) if ok else set()
    log(f"pulled {len(files)} changed file(s)" if files else "already up to date")
    return files


def sync_data():
    """Commit the shadow data files (only those) and push them."""
    present = [f for f in DATA_FILES if (REPO / f).exists()]
    if not present:
        return
    git("add", "--", *present)
    ok, _ = git("diff", "--cached", "--quiet", "--", *present)
    if ok:
        log("no new shadow data to sync")
        return
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    ok, out = git("commit", "-m", f"shadow data (autopilot) {stamp}", "--", *present)
    if not ok:
        log(f"commit FAILED ({out[:300]})")
        return
    pull()
    ok, out = git("push", "origin", f"HEAD:{BRANCH}")
    log("shadow data pushed to GitHub" if ok else f"push FAILED, will retry next time ({out[:300]})")


class ShadowProcess:
    def __init__(self, cmd=None):
        self.cmd = cmd or [sys.executable, "-u", "-m", "polysweeper.shadow", "--forever"]
        self.proc = None

    def start(self):
        if STOP.exists():
            STOP.unlink()
        log("starting shadow mode")
        self.proc = subprocess.Popen(self.cmd, cwd=str(CODE))

    def running(self):
        return self.proc is not None and self.proc.poll() is None

    def stop(self, wait=90, why="for an update"):
        """Ask shadow mode to stop through its own kill switch, so it saves cleanly."""
        if not self.running():
            return
        log(f"stopping shadow mode {why}")
        STOP.parent.mkdir(parents=True, exist_ok=True)
        STOP.write_text("autopilot update")
        end = time.time() + wait
        while self.running() and time.time() < end:
            time.sleep(1)
        if self.running():
            self.proc.terminate()
            self.proc.wait(30)
        if STOP.exists():
            STOP.unlink()


def main(cmd=None, max_loops=None, tick=5):
    ok, out = git("--version")
    if not ok:
        log("git was not found. Install Git for Windows (git-scm.com) and run this again.")
        return 1
    log(f"started in {REPO}")
    if STOP.exists():
        STOP.unlink()
    me = Path(__file__).resolve().relative_to(REPO).as_posix()
    if me in pull():
        return SELF_UPDATE
    shadow = ShadowProcess(cmd)
    shadow.start()
    last_check = last_sync = time.time()
    loops = 0
    while max_loops is None or loops < max_loops:
        loops += 1
        time.sleep(tick)
        if not shadow.running():
            if STOP.exists():                       # the owner used stop_shadow.bat
                log("stop file found: shadow mode and autopilot stopped by the owner")
                sync_data()
                return 0
            log(f"shadow mode exited unexpectedly; restarting in {RESTART_DELAY} s")
            time.sleep(RESTART_DELAY)
            shadow.start()
        now = time.time()
        if now - last_check >= CHECK_EVERY:
            last_check = now
            if update_available():
                shadow.stop()
                sync_data()                          # also pulls
                changed = pull()
                if me in changed:
                    log("autopilot itself was updated; restarting it")
                    return SELF_UPDATE
                shadow.start()
        if now - last_sync >= SYNC_EVERY:
            last_sync = now
            sync_data()
    shadow.stop(why="(test run finished)")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("stopped with Ctrl+C")
        sys.exit(0)
