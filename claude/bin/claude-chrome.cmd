@echo off
rem claude-chrome -- start Claude Code with the browser bridge connected (PowerShell/cmd).
rem Twin of the bash script beside this file; see it for the full rationale and
rem the one-time per-profile setup. Short version: the browser is the universal
rem fallback for dashboard-only work (Cloud Console OAuth clients, Play Console
rem SHA-1, RevenueCat uploads). Without it those become the user's homework.
rem Extensions are per-profile: install the extension in the "Claude Agent"
rem profile, sign it in, disable it in the personal profile so binding is
rem deterministic, then fully restart Chrome.
claude --chrome %*
