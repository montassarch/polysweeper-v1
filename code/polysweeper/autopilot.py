"""Autopilot: keeps shadow mode running and up to date on the owner's PC, with no clicks.

  1. On start: pull the latest code from GitHub, then start shadow mode.
  2. Every minute: if GitHub has a newer version, stop shadow mode, pull, restart it.
     If the update changes only notes (nothing in code/), pull it and leave shadow mode running.
     Files edited on this PC never block an update: notes are kept as a commit, code edits are put
     aside (git stash), files in the way are renamed. If an update still fails, retry in 30 minutes.
  3. Every 3 hours: commit and push the shadow data files so they can be analysed.
  4. If shadow mode crashes, restart it after 30 seconds.

It only ever commits the shadow data files (trades, events, errors, and the daily folder with
score changes and live end-window detail). Notes are left alone.
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
DATA_FILES = ["code/data/shadow/trades.jsonl", "code/data/shadow/events.jsonl", "code/data/shadow/errors.jsonl",
              "code/data/shadow/daily"]           # a folder: one file per day (score changes, live detail)
BRANCH = "main"
CHECK_EVERY = 60                                   # check GitHub for updates every minute
RETRY_AFTER_FAIL = 30 * 60                         # an update that cannot be brought in: try again in 30 min
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


def incoming_files():
    """Files changed on GitHub that this PC does not have yet, or None if git cannot tell."""
    ok, out = git("-c", "core.quotePath=false", "diff", "--name-only", "-z", "--no-renames", f"HEAD...origin/{BRANCH}")
    return {f for f in out.split("\0") if f} if ok else None


def touches_code(files):
    """Shadow mode only needs a restart when something in code/ changed (notes need none)."""
    return files is None or any(f.startswith("code/") for f in files)


def pull_notes_only():
    """Bring in an update that touches no code WITHOUT stopping shadow mode.
    Fast-forward only: git then rewrites just the changed notes and leaves the data files that
    shadow mode is writing alone. If anything is in the way (an unpushed data commit, a note
    edited on this PC) git changes nothing and we return False: the caller uses the normal path."""
    before = head()
    ok, out = git("merge", "--ff-only", f"origin/{BRANCH}")
    if not ok:
        return False
    ok, changed = git("diff", "--name-only", before, "HEAD")
    n = len(changed.split()) if ok else "?"
    log(f"pulled {n} changed file(s), notes only: shadow mode keeps running")
    return True


def update_without_restart():
    """True when the waiting update touches no code and was pulled while shadow mode kept running.
    False means: stop shadow mode, pull, start it again (a code update, or notes that could not be
    pulled the safe way)."""
    return not touches_code(incoming_files()) and pull_notes_only()


def behind():
    """True if GitHub (as last fetched) has commits this PC does not have."""
    ok, out = git("rev-list", "--count", f"HEAD..origin/{BRANCH}")
    return ok and out.strip().isdigit() and int(out) > 0


def save_local_edits():
    """Edits made on this PC to tracked files (not the shadow data) block every update.
    Files outside code/ (notes, CLAUDE.md, ...): committed here, so they are kept and sent to GitHub
    with the next data sync. Files in code/: put aside in a git stash, so the PC always runs the code
    that is on GitHub. Nothing is deleted."""
    ok, out = git("-c", "core.quotePath=false", "diff", "--name-only", "-z", "--no-renames", "HEAD")
    if not ok:
        return
    files = [f for f in out.split("\0") if f and not f.startswith("code/data/shadow/")]
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    notes = [f for f in files if not f.startswith("code/")]
    code = [f for f in files if f.startswith("code/")]
    if notes:
        git("add", "--", *notes)
        ok, out = git("commit", "-m", f"Edits made on the PC (kept by autopilot) {stamp}", "--", *notes)
        log(f"kept {len(notes)} file(s) edited on this PC as a commit: {', '.join(notes)[:300]}"
            if ok else f"could not commit the files edited on this PC ({out[-300:]})")
    if code:
        ok, out = git("stash", "push", "-m", f"autopilot: code edits made on the PC {stamp}", "--", *code)
        log(f"put aside {len(code)} code file(s) edited on this PC (git stash): {', '.join(code)[:300]}"
            if ok else f"could not put aside the code edited on this PC ({out[-300:]})")


def move_aside_blocking(out):
    """Untracked files on this PC that sit where an update wants to put a file: renamed to
    '<name>.pc-copy-<time>' (nothing is deleted). Returns True if anything was moved."""
    files, grab = [], False
    for line in out.splitlines():
        if "untracked working tree files would be overwritten" in line:
            grab = True
        elif grab and line.startswith("\t"):
            files.append(line.strip())
        else:
            grab = False
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    moved = []
    for f in files:
        p = REPO / f
        if p.is_file() and not f.startswith("code/data/shadow/"):
            try:
                p.rename(p.with_name(f"{p.name}.pc-copy-{stamp}"))
                moved.append(f)
            except OSError as e:                     # e.g. the file is open in another program
                log(f"could not rename {f} ({e})")
    if moved:
        log(f"renamed {len(moved)} file(s) on this PC that were in the way of the update "
            f"(kept as .pc-copy-{stamp}): {', '.join(moved)[:300]}")
    return bool(moved)


def _gist(out):
    """The useful part of a git error (drops the 'From ...' and branch lines)."""
    lines = [l for l in out.splitlines() if l.strip() and not l.startswith(("From ", " * branch"))]
    return " / ".join(lines)[:400]


def pull():
    """Bring in the latest code. On any problem keep the current version and say why."""
    save_local_edits()
    before = head()
    ok, out = git("pull", "--rebase", "--autostash", "origin", BRANCH)
    if not ok:
        git("rebase", "--abort")
        if move_aside_blocking(out):                 # files in the way: renamed, try once more
            ok, out = git("pull", "--rebase", "--autostash", "origin", BRANCH)
            if not ok:
                git("rebase", "--abort")
    if not ok:
        first = out
        # data files only grow, so on a conflict the copy on this PC is the complete one
        ok, out = git("pull", "--no-rebase", "--no-edit", "-X", "ours", "origin", BRANCH)
        if not ok:
            git("merge", "--abort")
            log(f"pull FAILED, keeping the current version. Rebase: {_gist(first)} | Merge: {_gist(out)}")
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


def apply_update(shadow, me):
    """Stop shadow mode, send the data, pull, start it again. Returns "self" (the autopilot itself was
    updated: restart it), "ok", or "failed" (still behind GitHub: try again later)."""
    before = head()
    shadow.stop()
    sync_data()                                      # may already pull the update
    pull()
    ok, out = git("diff", "--name-only", before, "HEAD")
    if me in (set(out.split()) if ok else set()):
        log("autopilot itself was updated; restarting it")
        return "self"
    shadow.start()
    return "failed" if behind() else "ok"


AUTOPILOT_STOP = "autopilot update"                 # what the autopilot writes in the stop file


def owner_stop():
    """True if the owner asked to stop (stop_shadow.bat). The autopilot's own stop file for an update
    says AUTOPILOT_STOP; anything else is the owner's and must never be cleared by the autopilot."""
    try:
        return STOP.exists() and STOP.read_text(errors="ignore").strip() != AUTOPILOT_STOP
    except OSError:
        return STOP.exists()


class ShadowProcess:
    def __init__(self, cmd=None):
        self.cmd = cmd or [sys.executable, "-u", "-m", "polysweeper.shadow", "--forever"]
        self.proc = None

    def start(self):
        if STOP.exists() and not owner_stop():
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
        if not owner_stop():                         # never overwrite the owner's stop request
            STOP.parent.mkdir(parents=True, exist_ok=True)
            STOP.write_text(AUTOPILOT_STOP)
        end = time.time() + wait
        while self.running() and time.time() < end:
            time.sleep(1)
        if self.running():
            self.proc.terminate()
            self.proc.wait(30)
        if STOP.exists() and not owner_stop():
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
    retry_at = 0.0
    loops = 0
    while max_loops is None or loops < max_loops:
        loops += 1
        time.sleep(tick)
        if owner_stop():                             # the owner used stop_shadow.bat
            shadow.stop(why="(stop file from the owner)")
            log("stop file found: shadow mode and autopilot stopped by the owner")
            sync_data()
            return 0
        if not shadow.running():
            log(f"shadow mode exited unexpectedly; restarting in {RESTART_DELAY} s")
            time.sleep(RESTART_DELAY)
            shadow.start()
        now = time.time()
        if now - last_check >= CHECK_EVERY and now >= retry_at:
            last_check = now
            if update_available() and not update_without_restart():
                result = apply_update(shadow, me)
                if result == "self":
                    return SELF_UPDATE
                if result == "failed":               # don't restart shadow mode every minute for nothing
                    retry_at = now + RETRY_AFTER_FAIL
                    log(f"the update could not be brought in; shadow mode keeps running; "
                        f"next try in {RETRY_AFTER_FAIL // 60} minutes")
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
