---
name: safe-deploy
description: Checklist for sending changes to main in PolySweeper without breaking the owner's PC (main is live on it within a minute). Use before every commit or push, and whenever code/ changes.
---

# Sending changes to main safely

`main` **is live**: the autopilot on the owner's Windows PC checks GitHub every minute. A change inside
`code/` stops shadow mode, pulls and restarts it. The owner cannot debug, so a broken push means downtime
until someone notices.

## 1. Which kind of change is it?

| Changed files | Effect on the PC | Rule |
|---|---|---|
| Notes, `lab/`, `.claude/`, `CLAUDE.md` | Fast-forwarded, **no restart** | Push freely |
| Anything in `code/` | **Restart** of shadow mode; end-window watches in progress are cut short | Owner's OK first (unless it is an urgent fix of something already broken); prefer quiet hours |
| `code/polysweeper/autopilot.py` | The autopilot restarts **itself** | Extra care: a bug here can stop all updates. Test in a scratch copy first |

Never touch `code/data/shadow/` (trades, events, errors, daily): the autopilot owns those files.

## 2. Before pushing code

1. `git pull --rebase origin main`.
2. Tests: `cd code && python3 -m unittest discover -s tests` (Linux/cloud), or `py -3 -m unittest ...` on the PC.
   On Windows, ~11 shadow tests fail with `PermissionError [WinError 32]` on temp files: known, test-only;
   compare against the same run without your change, the error count must not grow.
3. For shadow or livefeed changes: a 2-minute scratch run (`--no-live` if the feed is not involved) with 0 errors.
4. Standard library only; `code/config.json` keys are strict (an unknown key raises at start).
5. Re-read the diff: what would crash shadow mode at start?

## 3. Waiting for the owner's OK

Do not leave code edits uncommitted in the PC's working folder: on its next update the autopilot puts them
aside (git stash) and they can be lost. Save them on a separate branch instead, without switching the PC's checkout:

```
export GIT_INDEX_FILE=$(mktemp -u)      # temp index, the real one is untouched
git read-tree HEAD && git add <files> && tree=$(git write-tree)
unset GIT_INDEX_FILE
git branch <name> $(git commit-tree $tree -p HEAD -m "<message>")
git push -u origin <name> && git checkout -- <files>
```

Note the branch in `PolySweeper-V1/24-Task-List.md` so it is not forgotten.

## 4. After pushing

- Small commits, clear messages. Retry a failed push after 2, 4, 8, 16 s.
- Within ~2 minutes check that shadow mode came back (PC: a python process running `polysweeper.shadow`;
  cloud: the next autopilot data commit and no new lines in `errors.jsonl`).
- `.bat` files keep CRLF (`.gitattributes` handles it). Never place real orders or touch keys.
