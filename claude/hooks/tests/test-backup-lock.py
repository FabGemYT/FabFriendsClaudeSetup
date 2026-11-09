"""The backup lock: FabGemYT/FabClaudeWorkflow never goes public, never gains a
reader, and is never pushed anywhere but its own repo.

The friends' copy (FabGemYT/FabClaudeWorkflow's scrubbed twin,
FabGemYT/FabFriendsClaudeSetup) is public and gets flipped between public and
private, so the two names sit side by side in every session. One confused
command would expose the backup with no undo. The lock lives in
block-guard-tamper.sh (mode guard-tamper of command-guard.py).

BLOCK cases are every route to that mistake; ALLOW cases are the ordinary work
that must keep running, including everything on the friends' repo. The
approval token is checked too: the owner's yes in chat still lets Claude do it.

Run:  py -3 test-backup-lock.py      (about 15 seconds)
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

HOOKS = os.path.expanduser("~/.claude/hooks")
SHELL_GUARD = os.path.join(HOOKS, "block-guard-tamper.sh")
APPROVAL = os.path.expanduser("~/.claude/.approved-action")
BACKUP = "https://github.com/FabGemYT/FabClaudeWorkflow.git"
FRIENDS = "git@github.com:FabGemYT/FabFriendsClaudeSetup.git"
OTHER = "https://github.com/FabGemYT/store-app.git"


def git(cwd, *args):
    subprocess.run(["git", "-C", cwd] + list(args), check=True,
                   capture_output=True, text=True)


def make_repo(root, name, origin, backup_content=False, extra_remote=None):
    path = os.path.join(root, name).replace("\\", "/")
    os.makedirs(path)
    git(path, "init", "-q")
    git(path, "remote", "add", "origin", origin)
    if extra_remote:
        git(path, "remote", "add", extra_remote[0], extra_remote[1])
    if backup_content:
        for rel in ("hq/WORKFLOW_HQ_LOG.md", "rules/secrets-map.md"):
            os.makedirs(os.path.dirname(os.path.join(path, rel)), exist_ok=True)
            open(os.path.join(path, rel), "w").close()
    return path


def run(cmd, cwd):
    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd},
                          "cwd": cwd})
    p = subprocess.run(["bash", SHELL_GUARD], input=payload,
                       capture_output=True, text=True)
    return p.returncode, (p.stderr or "").strip()


def main():
    root = tempfile.mkdtemp(prefix="backup-lock-")
    # A real pending approval (The owner's yes, written moments ago) must survive this
    # suite: set it aside and put it back afterwards.
    pending = None
    if os.path.exists(APPROVAL):
        with open(APPROVAL, encoding="utf-8") as fh:
            pending = fh.read()
        os.remove(APPROVAL)
    try:
        bk = make_repo(root, "backup", BACKUP,
                       extra_remote=("friends", FRIENDS))
        moved = make_repo(root, "backup-repointed", FRIENDS, backup_content=True)
        fr = make_repo(root, "friends-export", FRIENDS)
        proj = make_repo(root, "project", OTHER)
        tmp = root.replace("\\", "/")
        vis = "--accept-visibility-change-consequences"

        block = [
            ("edit-public", "gh repo edit FabGemYT/FabClaudeWorkflow --visibility public %s" % vis, tmp),
            ("edit-public-eq", "gh repo edit FabGemYT/FabClaudeWorkflow --visibility=public %s" % vis, tmp),
            ("edit-internal-url", "gh repo edit https://github.com/FabGemYT/FabClaudeWorkflow --visibility internal %s" % vis, tmp),
            ("edit-lowercase", "gh repo edit fabgemyt/fabclaudeworkflow --visibility public %s" % vis, tmp),
            ("edit-inferred", "gh repo edit --visibility public %s" % vis, bk),
            ("edit-cd-chain", "cd %s && gh repo edit --visibility public %s" % (bk, vis), tmp),
            ("edit-nested-bash", "bash -c \"gh repo edit FabGemYT/FabClaudeWorkflow --visibility public %s\"" % vis, tmp),
            ("api-private-false", "gh api -X PATCH repos/FabGemYT/FabClaudeWorkflow -F private=false", tmp),
            ("api-visibility", "gh api --method PATCH /repos/fabgemyt/fabclaudeworkflow -f visibility=public", tmp),
            ("api-placeholder", "gh api -X PATCH repos/{owner}/{repo} -F private=false", bk),
            ("api-input-body", "gh api -X PATCH repos/FabGemYT/FabClaudeWorkflow --input body.json", tmp),
            ("api-collaborator", "gh api -X PUT repos/FabGemYT/FabClaudeWorkflow/collaborators/someone -f permission=pull", tmp),
            ("api-collab-x-last", "gh api repos/FabGemYT/FabClaudeWorkflow/collaborators/someone -X PUT", tmp),
            ("api-deploy-key", "gh api -X POST repos/FabGemYT/FabClaudeWorkflow/keys -f key=ssh-ed25519", tmp),
            ("api-transfer", "gh api repos/FabGemYT/FabClaudeWorkflow/transfer -f new_owner=someone", tmp),
            ("deploy-key-add", "gh repo deploy-key add key.pub -R FabGemYT/FabClaudeWorkflow --allow-write", tmp),
            ("deploy-key-inferred", "gh repo deploy-key add key.pub", bk),
            ("curl-private", "curl -X PATCH https://api.github.com/repos/FabGemYT/FabClaudeWorkflow -d '{\"private\":false}'", tmp),
            ("curl-collaborator", "curl -X PUT https://api.github.com/repos/FabGemYT/FabClaudeWorkflow/collaborators/someone", tmp),
            ("push-friends-url", "git push %s HEAD:refs/heads/export" % FRIENDS, bk),
            ("push-friends-https", "git push https://github.com/FabGemYT/FabFriendsClaudeSetup feat/x", bk),
            ("push-friends-remote", "git -C %s push friends feat/x" % bk, tmp),
            ("push-repointed-bare", "git push", moved),
            ("push-repointed-origin", "git push origin feat/x", moved),
            ("create-from-backup", "gh repo create FabGemYT/copy --public --source=%s --push" % bk, tmp),
        ]
        allow = [
            ("friends-public", "gh repo edit FabGemYT/FabFriendsClaudeSetup --visibility public %s" % vis, tmp),
            ("friends-private", "gh repo edit FabGemYT/FabFriendsClaudeSetup --visibility private %s" % vis, tmp),
            ("backup-stays-private", "gh repo edit FabGemYT/FabClaudeWorkflow --visibility private %s" % vis, tmp),
            ("backup-description", "gh repo edit FabGemYT/FabClaudeWorkflow --description \"PRIVATE BACKUP. Never share.\"", tmp),
            ("api-description", "gh api -X PATCH repos/FabGemYT/FabClaudeWorkflow -f description='PRIVATE BACKUP'", tmp),
            ("api-read", "gh api repos/FabGemYT/FabClaudeWorkflow --jq .private", tmp),
            ("api-list-collabs", "gh api repos/FabGemYT/FabClaudeWorkflow/collaborators", tmp),
            ("secret-set", "gh secret set FRIENDS_DEPLOY_KEY -R FabGemYT/FabClaudeWorkflow < key", tmp),
            ("friends-deploy-key", "gh repo deploy-key add key.pub -R FabGemYT/FabFriendsClaudeSetup --allow-write", tmp),
            ("friends-collaborator", "gh api -X PUT repos/FabGemYT/FabFriendsClaudeSetup/collaborators/someone", tmp),
            ("rename-empty-repo", "gh repo rename FabFriendsClaudeSetup -R FabGemYT/FabGemClaudeWorkflow --yes", tmp),
            ("curl-read", "curl -s https://api.github.com/repos/FabGemYT/FabClaudeWorkflow", tmp),
            ("push-feature", "git push origin feat/x", bk),
            ("push-upstream", "git push -u origin HEAD", bk),
            ("push-bare", "git push", bk),
            ("push-local-path", "git push /tmp/scratch-copy feat/x", bk),
            ("export-pushes-friends", "git push %s HEAD:refs/heads/export" % FRIENDS, fr),
            ("project-push", "git push origin feat/y", proj),
            ("create-from-project", "gh repo create FabGemYT/newthing --private --source=%s --push" % proj, tmp),
            ("pr-create", "gh pr create --base main --title x --body y", bk),
            ("git-status", "git status", bk),
        ]

        fails = []
        print("=" * 74)
        print("BACKUP LOCK -- MUST BLOCK (exit 2)")
        print("=" * 74)
        for c, cmd, cwd in block:
            rc, _ = run(cmd, cwd)
            ok = rc == 2
            if not ok:
                fails.append(("LEAK", c, cmd))
            print("   %-5s %-24s %s" % ("ok" if ok else "LEAK", c, cmd[:44]))
        print("\nBACKUP LOCK -- MUST ALLOW (exit 0)")
        print("=" * 74)
        for c, cmd, cwd in allow:
            rc, err = run(cmd, cwd)
            ok = rc == 0
            if not ok:
                fails.append(("FALSE+", c, cmd + "  -> " + err[:80]))
            print("   %-5s %-24s %s" % ("ok" if ok else "FALSE+", c, cmd[:44]))

        # The owner's yes in chat still lets Claude do it, exactly once.
        print("\nAPPROVAL TOKEN")
        print("=" * 74)
        cmd = "gh repo edit FabGemYT/FabClaudeWorkflow --visibility public %s" % vis
        os.makedirs(os.path.dirname(APPROVAL), exist_ok=True)
        with open(APPROVAL, "w", encoding="utf-8") as fh:
            fh.write(cmd)
        rc1, _ = run(cmd, tmp)
        rc2, _ = run(cmd, tmp)
        token_ok = rc1 == 0 and rc2 == 2 and not os.path.exists(APPROVAL)
        if not token_ok:
            fails.append(("TOKEN", "approval", "first=%s second=%s" % (rc1, rc2)))
        print("   %-5s approved once, then blocked again" % ("ok" if token_ok else "FAIL"))

        total = len(block) + len(allow) + 1
        print("\n" + "=" * 74)
        print("SUMMARY: %d/%d cases correct" % (total - len(fails), total))
        if fails:
            print("\nFAILURES -- %d" % len(fails))
            for kind, c, x in fails:
                print("   [%s] %s  %s" % (kind, c, x[:110]))
            print("\nNOT CLEAN")
        else:
            print("\nALL CLEAN")
        return 1 if fails else 0
    finally:
        try:
            os.remove(APPROVAL)
        except OSError:
            pass
        if pending is not None:
            with open(APPROVAL, "w", encoding="utf-8") as fh:
                fh.write(pending)
        shutil.rmtree(root, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
