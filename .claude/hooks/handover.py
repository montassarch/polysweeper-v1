"""Automatic handover for the laptop CLI session (hooks in .claude/settings.local.json).

end   (SessionEnd): copy the owner's messages and Claude's last replies from the transcript to
      .claude/handover/last-session.md (local, git-ignored), so nothing is lost on /clear.
start (SessionStart): print that file plus the newest session-log lines; Claude Code adds the
      output to the new session's context with an instruction to file anything missing in the vault.
Standard library only; never fails loudly (a hook error must not block the session).
"""
import datetime, json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DIR = os.path.join(ROOT, ".claude", "handover")
LAST = os.path.join(DIR, "last-session.md")
LOG = os.path.join(ROOT, "PolySweeper-V1", "00-Session-Log.md")
SKIP = ("<system-reminder", "<local-command", "<command-name", "<command-message", "<task-notification",
        "<cross-session-message", "Caveat:", "[Request interrupted")


def texts(content):
    if isinstance(content, str):
        return [content]
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text", ""))
    return out


def end(payload):
    path = payload.get("transcript_path")
    if not path or not os.path.exists(path):
        return
    owner, replies = [], []
    for line in open(path, encoding="utf-8", errors="replace"):
        try:
            r = json.loads(line)
        except ValueError:
            continue
        msg = r.get("message") or {}
        if r.get("type") == "user" and not r.get("isMeta"):
            for t in texts(msg.get("content")):
                t = t.strip()
                if t and not t.startswith(SKIP):
                    owner.append(t[:1500])
        elif r.get("type") == "assistant":
            t = "\n".join(texts(msg.get("content"))).strip()
            if t:
                replies.append(t[:1200])
    if not owner:
        return                                   # nothing said: keep the previous handover
    os.makedirs(DIR, exist_ok=True)
    if os.path.exists(LAST):                     # keep one older copy
        os.replace(LAST, os.path.join(DIR, "previous-session.md"))
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    with open(LAST, "w", encoding="utf-8") as f:
        f.write(f"# Laptop session ended {now} ({payload.get('reason', '')})\n\n## Owner's messages\n\n")
        for i, t in enumerate(owner[-40:], 1):
            f.write(f"{i}. {t}\n\n")
        f.write("## Claude's last replies\n\n")
        for t in replies[-3:]:
            f.write(t + "\n\n---\n\n")


def start():
    parts = []
    if os.path.exists(LAST):
        body = open(LAST, encoding="utf-8").read()
        parts.append(body[-9000:])
    if os.path.exists(LOG):
        lines = open(LOG, encoding="utf-8").read().splitlines()
        parts.append("## Newest session-log lines\n\n" + "\n".join(lines[-12:]))
    if not parts:
        return
    print("AUTOMATIC HANDOVER from the previous laptop session (owner set this up 2026-10-05).\n"
          "Before or while answering the owner's first message: git pull --rebase, then check that every "
          "task, idea, decision and open question in the owner's messages below is already in the vault "
          "(PolySweeper-V1/24-Task-List.md, 00-Session-Log.md, 30-Research-Hub.md). Add anything missing, "
          "commit and push (notes only), and tell the owner in one line what you filed. Do not re-read whole "
          "files or the old conversation; this summary is the handover.\n")
    print("\n\n".join(parts))


if __name__ == "__main__":
    try:
        if sys.argv[1:] == ["end"]:
            end(json.loads(sys.stdin.read() or "{}"))
        elif sys.argv[1:] == ["start"]:
            start()
    except Exception:
        pass
