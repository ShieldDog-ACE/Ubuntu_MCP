"""System-level MCP tool handlers for Linux Desktop Automation.

Added by local tuning, modeled on the Windows-MCP open-source project
(https://github.com/CursorTouch/Windows-MCP) toolset:

- ``desktop_shell``     ~ Windows-MCP PowerShell-Tool  (bash execution with
  dangerous-command protection)
- ``desktop_clipboard`` ~ Windows-MCP Clipboard-Tool   (wl-clipboard / xclip)
- ``desktop_launch``    ~ Windows-MCP App/Launch-Tool  (.desktop app launcher)
- ``desktop_notify``    ~ Windows-MCP Notification-Tool (notify-send)
"""

import asyncio
import logging
import os
import re
import shutil
from pathlib import Path
from typing import Any, Optional

from mcp.types import TextContent

from .handlers import MAX_TEXT_LENGTH, ServerContext

logger = logging.getLogger(__name__)

MAX_OUTPUT_LENGTH = 10000
MAX_COMMAND_LENGTH = 5000
MAX_TIMEOUT = 300

# Dangerous-command protection (ported concept from Windows-MCP command security)
BLOCKED_COMMAND_PATTERNS: list[re.Pattern[str]] = [
    re.compile(p, re.IGNORECASE)
    for p in [
        r"\b(shutdown|reboot|poweroff|halt|init\s+0|init\s+6)\b",
        r"\bmkfs(\.\w+)?\b",
        r"\bdd\s+if=",  # raw disk overwrite
        r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*[fF]?[a-zA-Z]*\s+/(\s|$)",  # rm -rf /
        r"\brm\s+(-[a-zA-Z]*\s+)*-[a-zA-Z]*[rR][a-zA-Z]*[fF]?[a-zA-Z]*\s+~",  # rm -rf ~
        r":\(\)\s*\{.*\};\s*:",  # fork bomb
        r"\bchmod\s+(-[a-zA-Z]+\s+)*-?R?[a-zA-Z]*\s+777\s+/",  # chmod -R 777 /
        r">\s*/dev/sd[a-z]",  # overwrite block device
    ]
]


def _check_blocked_command(command: str) -> Optional[str]:
    """Return a rejection reason if the command matches a dangerous pattern."""
    for pattern in BLOCKED_COMMAND_PATTERNS:
        if pattern.search(command):
            return f"Blocked dangerous command matching pattern: {pattern.pattern}"
    return None


async def _run_subprocess(
    *argv: str, timeout: float = 30, cwd: Optional[str] = None
) -> tuple[int, str]:
    """Run a subprocess, return (returncode, combined output)."""
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=cwd,
        )
    except FileNotFoundError:
        return 127, f"Command not found: {argv[0]}"
    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        return 124, f"Command timed out after {timeout}s"
    output = stdout.decode("utf-8", errors="replace")
    if len(output) > MAX_OUTPUT_LENGTH:
        output = output[:MAX_OUTPUT_LENGTH] + f"\n... (truncated, {len(output)} chars total)"
    return proc.returncode or 0, output


# ---------------------------------------------------------------------------
# desktop_shell  (~ Windows-MCP PowerShell-Tool)
# ---------------------------------------------------------------------------


async def handle_shell(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_shell tool: execute a bash command with protection."""
    command = args.get("command")
    timeout = min(max(int(args.get("timeout", 30)), 1), MAX_TIMEOUT)
    cwd = args.get("cwd")

    is_valid, err = ctx.validate_string(command or "", MAX_COMMAND_LENGTH, "command")
    if not is_valid:
        return [TextContent(type="text", text=f"Error: {err}")]
    assert command is not None

    blocked = _check_blocked_command(command)
    if blocked:
        return [TextContent(type="text", text=f"Error: {blocked}")]

    if cwd is not None:
        cwd = os.path.expanduser(str(cwd))
        if not os.path.isdir(cwd):
            return [TextContent(type="text", text=f"Error: cwd does not exist: {cwd}")]

    returncode, output = await _run_subprocess(
        "/bin/bash", "-lc", command, timeout=timeout, cwd=cwd
    )
    return [
        TextContent(
            type="text",
            text=f"Exit code: {returncode}\nOutput:\n{output if output.strip() else '(empty)'}",
        )
    ]


# ---------------------------------------------------------------------------
# desktop_clipboard  (~ Windows-MCP Clipboard-Tool)
# ---------------------------------------------------------------------------

_CLIPBOARD_GET = [
    ("wl-paste", ["wl-paste"]),
    ("xclip", ["xclip", "-selection", "clipboard", "-o"]),
]
_CLIPBOARD_SET = [
    ("wl-copy", ["wl-copy"]),
    ("xclip", ["xclip", "-selection", "clipboard"]),
]


async def handle_clipboard(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_clipboard tool: get or set the system clipboard text."""
    mode = args.get("mode", "get")
    if mode not in ("get", "set"):
        return [TextContent(type="text", text="Error: mode must be 'get' or 'set'")]

    if mode == "get":
        for name, argv in _CLIPBOARD_GET:
            if shutil.which(name):
                returncode, output = await _run_subprocess(*argv, timeout=10)
                if returncode == 0:
                    return [TextContent(type="text", text=f"Clipboard content:\n{output}")]
        return [
            TextContent(
                type="text",
                text="Error: no clipboard tool available. Install: sudo apt install wl-clipboard (Wayland) or xclip (X11)",
            )
        ]

    text = args.get("text")
    is_valid, err = ctx.validate_string(text if isinstance(text, str) else "", MAX_TEXT_LENGTH, "text")
    if not is_valid:
        return [TextContent(type="text", text=f"Error: {err}")]
    assert isinstance(text, str)

    for name, argv in _CLIPBOARD_SET:
        if shutil.which(name):
            try:
                proc = await asyncio.create_subprocess_exec(
                    *argv,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.PIPE,
                )
                _, stderr = await asyncio.wait_for(proc.communicate(text.encode("utf-8")), timeout=10)
                if proc.returncode == 0:
                    return [TextContent(type="text", text="Clipboard set successfully")]
                return [
                    TextContent(
                        type="text",
                        text=f"Error: {name} failed: {stderr.decode('utf-8', errors='replace').strip()}",
                    )
                ]
            except (FileNotFoundError, asyncio.TimeoutError) as e:
                logger.warning(f"Clipboard set via {name} failed: {e}")
    return [
        TextContent(
            type="text",
            text="Error: no clipboard tool available. Install: sudo apt install wl-clipboard (Wayland) or xclip (X11)",
        )
    ]


# ---------------------------------------------------------------------------
# desktop_launch  (~ Windows-MCP App/Launch-Tool)
# ---------------------------------------------------------------------------

_DESKTOP_DIRS = [
    Path.home() / ".local/share/applications",
    Path("/usr/share/applications"),
    Path("/var/lib/flatpak/exports/share/applications"),
    Path.home() / ".local/share/flatpak/exports/share/applications",
]


async def handle_launch(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_launch tool: launch an installed application by name."""
    app_name = args.get("app_name")
    is_valid, err = ctx.validate_string(app_name if isinstance(app_name, str) else "", 200, "app_name")
    if not is_valid:
        return [TextContent(type="text", text=f"Error: {err}")]
    assert isinstance(app_name, str)

    query = app_name.strip().lower()

    # Preferred: GIO application registry — supports localized display names
    # (e.g. "终端" for Terminal) via installed language packs
    try:
        from gi.repository import Gio  # type: ignore[import-not-found]

        matches: list[tuple[bool, int, Any, str]] = []
        for info in Gio.AppInfo.get_all():
            if not info.should_show():
                continue
            did = (info.get_id() or "").removesuffix(".desktop")
            fields = [
                f.lower()
                for f in [
                    info.get_display_name() or "",
                    info.get_name() or "",
                    info.get_executable() or "",
                    did,
                ]
                if f
            ]
            if query in fields or any(query in f for f in fields):
                matches.append((query not in fields, len(fields[0]), info, did))
        if matches:
            matches.sort(key=lambda m: (m[0], m[1]))
            _, _, info, did = matches[0]
            if info.launch():
                return [TextContent(type="text", text=f"Launched application: {did}")]
            return [TextContent(type="text", text=f"Error: failed to launch {did}")]
    except Exception as e:
        logger.debug(f"GIO launch unavailable, falling back to .desktop scan: {e}")

    # Fallback: scan .desktop files directly
    candidates: list[tuple[str, Path]] = []
    for directory in _DESKTOP_DIRS:
        if not directory.is_dir():
            continue
        for entry in directory.glob("*.desktop"):
            stem = entry.stem.lower()
            if query == stem or query in stem:
                candidates.append((entry.stem, entry))
                continue
            # Also match the display name (Name= / Name[zh*]=) like Windows-MCP
            # matches Start-Menu entries
            try:
                for line in entry.read_text(encoding="utf-8", errors="replace").splitlines():
                    if line.lower().startswith("name") and "=" in line:
                        display_name = line.split("=", 1)[1].strip().lower()
                        if query == display_name or query in display_name:
                            candidates.append((entry.stem, entry))
                            break
            except OSError:
                continue
    if not candidates:
        return [
            TextContent(
                type="text",
                text=f"Error: no installed application matches '{app_name}'. "
                f"Use desktop_shell to list apps: ls /usr/share/applications/*.desktop",
            )
        ]

    # Prefer exact stem match, then shortest name (closest to query)
    candidates.sort(key=lambda c: (c[0].lower() != query, len(c[0])))
    desktop_id, desktop_file = candidates[0]

    returncode, output = await _run_subprocess(
        "gio", "launch", str(desktop_file), timeout=15
    )
    if returncode == 0:
        return [TextContent(type="text", text=f"Launched application: {desktop_id}")]
    return [
        TextContent(type="text", text=f"Error launching {desktop_id}: exit {returncode}\n{output}")
    ]


# ---------------------------------------------------------------------------
# desktop_notify  (~ Windows-MCP Notification-Tool)
# ---------------------------------------------------------------------------


async def handle_notify(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_notify tool: send a desktop notification."""
    if not shutil.which("notify-send"):
        return [
            TextContent(type="text", text="Error: notify-send not available. Install: sudo apt install libnotify-bin")
        ]

    title = args.get("title", "Notification")
    body = args.get("body", "")
    urgency = args.get("urgency", "normal")
    if urgency not in ("low", "normal", "critical"):
        urgency = "normal"

    is_valid, err = ctx.validate_string(title if isinstance(title, str) else "", 200, "title")
    if not is_valid:
        return [TextContent(type="text", text=f"Error: {err}")]
    is_valid, err = ctx.validate_string(body if isinstance(body, str) else "", 2000, "body")
    if not is_valid:
        return [TextContent(type="text", text=f"Error: {err}")]

    returncode, output = await _run_subprocess(
        "notify-send", "-u", urgency, str(title), str(body), timeout=10
    )
    if returncode == 0:
        return [TextContent(type="text", text="Notification sent")]
    return [TextContent(type="text", text=f"Error sending notification: {output}")]
