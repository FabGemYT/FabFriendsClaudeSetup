@echo off
rem claude-cleanup -- reclaim RAM left behind by finished Claude Code sessions.
rem Dry-run by default; pass -Force to actually stop the orphans.
rem   claude-cleanup            report only
rem   claude-cleanup -Force     reclaim
rem Safe by construction: never blanket-kills node.exe (dev servers are node
rem too). A process must BOTH match a known Claude MCP server AND have no live
rem claude.exe anywhere in its parent chain. See the .ps1 for the full rationale.
powershell -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.claude\bin\claude-cleanup.ps1" %*
