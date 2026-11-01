"""Safe desktop update and installed-commit verification for GTA Radar.

Runs BEFORE any collection or paid stage. It never touches databases, results,
dossiers or ledgers: it only reads git state, optionally fast-forwards the CODE
folder, and appends a record of which commit actually ran.

Rules
  * The code folder must be a git clone of the official repository.
  * The working tree must be clean (tracked files); local edits are never overwritten.
  * Updates are fast-forward only from origin/main. Diverged history or local
    commits that are not on origin/main are refused, never merged or reset.
  * After an update every .py file must compile. If not, the code folder is put
    back on the previous commit (safe: the tree was verified clean first).
  * If GitHub cannot be reached the run may continue, but the record says
    UPDATE_CHECK_FAILED so nobody mistakes it for a verified-current install.
Environment overrides: GTA_RADAR_SKIP_UPDATE=1 (verify only, do not fetch/update),
GTA_RADAR_ALLOW_UNVERIFIED=1 (continue after a refusal; recorded as overridden).
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
import os
import subprocess
import sys
from pathlib import Path

OFFICIAL_REPO = "sandeep89shaily-coder/gta-commercial-radar"
RECORD_FILE = "INSTALLED_COMMIT.json"
LOG_FILE = "INSTALLED_COMMIT_LOG.jsonl"

MESSAGES = {
    "OK_UP_TO_DATE": "Installed code matches GitHub main.",
    "OK_FAST_FORWARDED": "Code was updated to the latest GitHub main and verified.",
    "OK_BEHIND_NOT_APPLIED": "A newer version exists but automatic update is switched off.",
    "OK_UPDATE_CHECK_FAILED": "Could not reach GitHub; running the installed commit, which is NOT verified as current.",
    "REFUSED_GIT_MISSING": "Git is not installed or not on PATH, so the installed version cannot be verified.",
    "REFUSED_NOT_A_GIT_REPO": "The code folder is not a git clone, so the installed version cannot be verified.",
    "REFUSED_WRONG_ORIGIN": "The code folder points at a repository other than the official GTA Radar one.",
    "REFUSED_DIRTY_TREE": "Code files were edited locally. Nothing was changed; ask for help before running.",
    "REFUSED_DIVERGED": "Local history and GitHub main have diverged. Nothing was changed.",
    "REFUSED_AHEAD_OF_MAIN": "This install has commits that are not on GitHub main, so it is not a verified release.",
    "REFUSED_NO_REMOTE_MAIN": "GitHub main could not be resolved after fetching.",
    "REFUSED_UPDATE_CHECK_FAILED": "Could not verify the current GitHub main; run is blocked to prevent using an unverified release.",
    "REFUSED_OUTDATED_RELEASE": "A newer GitHub main exists. Run desktop_update.py separately before starting the pipeline.",
    "REFUSED_SYNTAX_ERROR": "Some code files do not compile; the previous commit was restored if an update caused it.",
}


def _git(args, cwd, timeout=90):
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        done = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                              timeout=timeout, env=env)
    except FileNotFoundError:
        return 127, "git not found"
    except subprocess.TimeoutExpired:
        return 124, "git timed out"
    return done.returncode, (done.stdout or done.stderr or "").strip()


def installed_commit(code_dir):
    code, out = _git(["rev-parse", "HEAD"], code_dir)
    return out if code == 0 else ""


def compile_errors(code_dir):
    """Compile every top-level .py in memory (nothing written). Returns [(file, error)]."""
    problems = []
    for path in sorted(Path(code_dir).glob("*.py")):
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
            problems.append((path.name, f"{type(exc).__name__}: {str(exc)[:120]}"))
    return problems


def _origin_ok(url, expected):
    return expected.casefold().replace("\\", "/") in url.casefold().replace("\\", "/")


def preflight(code_dir, results_dir=None, *, apply_update=True, fetch=True,
              expected_origin=OFFICIAL_REPO, remote="origin", branch="main"):
    code_dir = Path(code_dir)
    skip = os.environ.get("GTA_RADAR_SKIP_UPDATE") == "1"
    if skip:
        fetch = apply_update = False
    info = {"checked_at": dt.datetime.now(dt.timezone.utc).isoformat(), "code_dir": str(code_dir),
            "installed_commit": "", "remote_commit": "", "updated_from": "", "status": "",
            "compile_errors": [], "overridden": False}

    def finish(status):
        info["status"] = status
        info["ok"] = status.startswith("OK_")
        info["message"] = MESSAGES.get(status, status)
        if not info["ok"] and os.environ.get("GTA_RADAR_ALLOW_UNVERIFIED") == "1":
            info["overridden"] = True
            info["ok"] = True
        info["installed_commit"] = installed_commit(code_dir) or info["installed_commit"]
        _record(results_dir, info)
        return info

    code, out = _git(["rev-parse", "--is-inside-work-tree"], code_dir)
    if code == 127:
        return finish("REFUSED_GIT_MISSING")
    if code != 0 or out != "true":
        return finish("REFUSED_NOT_A_GIT_REPO")
    code, url = _git(["remote", "get-url", remote], code_dir)
    if code != 0 or not _origin_ok(url, expected_origin):
        return finish("REFUSED_WRONG_ORIGIN")
    head = installed_commit(code_dir)
    info["installed_commit"] = head
    code, dirty = _git(["status", "--porcelain", "--untracked-files=no"], code_dir)
    if code != 0 or dirty.strip():
        return finish("REFUSED_DIRTY_TREE")

    reached = True
    if fetch:
        code, _ = _git(["fetch", "--quiet", remote, branch], code_dir)
        reached = code == 0
    code, remote_head = _git(["rev-parse", f"{remote}/{branch}"], code_dir)
    remote_head = remote_head if code == 0 else ""
    info["remote_commit"] = remote_head
    if fetch and not reached:
        return finish("REFUSED_UPDATE_CHECK_FAILED")
    elif not remote_head:
        return finish("REFUSED_NO_REMOTE_MAIN")
    elif head == remote_head:
        status = "OK_UP_TO_DATE"
    else:
        behind = _git(["merge-base", "--is-ancestor", head, remote_head], code_dir)[0] == 0
        ahead = _git(["merge-base", "--is-ancestor", remote_head, head], code_dir)[0] == 0
        if behind:
            if not apply_update:
                return finish("REFUSED_OUTDATED_RELEASE")
            else:
                code, _ = _git(["merge", "--ff-only", f"{remote}/{branch}"], code_dir)
                if code != 0 or installed_commit(code_dir) != remote_head:
                    return finish("REFUSED_DIVERGED")
                info["updated_from"] = head
                status = "OK_FAST_FORWARDED"
        elif ahead:
            return finish("REFUSED_AHEAD_OF_MAIN")
        else:
            return finish("REFUSED_DIVERGED")

    problems = compile_errors(code_dir)
    if problems:
        info["compile_errors"] = [f"{name}: {why}" for name, why in problems][:10]
        if info["updated_from"]:
            # The tree was clean before we updated, so restoring the previous commit loses nothing.
            _git(["reset", "--hard", info["updated_from"]], code_dir)
            info["rolled_back_to"] = info["updated_from"]
        return finish("REFUSED_SYNTAX_ERROR")
    return finish(status)


def _record(results_dir, info):
    if not results_dir:
        return
    folder = Path(results_dir)
    try:
        folder.mkdir(parents=True, exist_ok=True)
        (folder / RECORD_FILE).write_text(json.dumps(info, indent=2), encoding="utf-8")
        with (folder / LOG_FILE).open("a", encoding="utf-8") as log:
            log.write(json.dumps({k: info.get(k) for k in (
                "checked_at", "status", "installed_commit", "remote_commit", "updated_from", "overridden")}) + "\n")
    except OSError:
        pass            # recording must never block or corrupt a run


def main(argv=None):
    p = argparse.ArgumentParser(description="Verify (and safely update) the installed GTA Radar code.")
    p.add_argument("--code-dir", default=str(Path(__file__).resolve().parent))
    p.add_argument("--results-dir")
    p.add_argument("--no-update", action="store_true", help="verify only; do not fetch or update")
    a = p.parse_args(argv)
    info = preflight(a.code_dir, a.results_dir, apply_update=not a.no_update, fetch=not a.no_update)
    print(f"{info['status']}: {info['message']}")
    print("Installed commit:", info["installed_commit"] or "unknown")
    for line in info["compile_errors"]:
        print("  compile error:", line)
    return 0 if info["ok"] else 3


if __name__ == "__main__":
    sys.exit(main())
