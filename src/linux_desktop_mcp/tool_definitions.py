"""MCP tool definitions for Linux Desktop Automation.

Extracted from server.py for maintainability. Contains all Tool objects
with their JSON schemas and annotations.
"""

from mcp.types import Tool, ToolAnnotations


def get_tool_definitions() -> list[Tool]:
    """Return the list of all MCP tool definitions."""
    return [
        Tool(
            name="desktop_snapshot",
            description="Capture accessibility tree with semantic element references. "
            "Returns a tree of UI elements with ref IDs that can be used for interaction.",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Filter to specific application name (optional)",
                    },
                    "max_depth": {
                        "type": "integer",
                        "description": "Maximum tree traversal depth (default: 15)",
                        "default": 15,
                    },
                },
            },
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        Tool(
            name="desktop_find",
            description="Find elements by natural language query. "
            "Search for buttons, text fields, links, etc. by name or role.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Natural language query (e.g., 'save button', 'search field')",
                    },
                    "app_name": {
                        "type": "string",
                        "description": "Filter to specific application (optional)",
                    },
                },
                "required": ["query"],
            },
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        Tool(
            name="desktop_click",
            description="Click on an element by reference or coordinates.",
            inputSchema={
                "type": "object",
                "properties": {
                    "ref": {
                        "type": "string",
                        "description": "Element reference ID (e.g., 'ref_5')",
                    },
                    "element": {
                        "type": "string",
                        "description": "Human-readable element description for logging",
                    },
                    "coordinate": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "minItems": 2,
                        "maxItems": 2,
                        "description": "Fallback [x, y] coordinates if no ref",
                    },
                    "button": {
                        "type": "string",
                        "enum": ["left", "right", "middle"],
                        "default": "left",
                    },
                    "click_type": {
                        "type": "string",
                        "enum": ["single", "double"],
                        "default": "single",
                    },
                    "modifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Modifier keys like ['ctrl', 'shift']",
                    },
                },
            },
            annotations=ToolAnnotations(destructiveHint=True),
        ),
        Tool(
            name="desktop_type",
            description="Type text into an element. Clicks to focus first if ref provided.",
            inputSchema={
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Text to type"},
                    "ref": {
                        "type": "string",
                        "description": "Element reference to type into (optional)",
                    },
                    "element": {
                        "type": "string",
                        "description": "Human-readable element description",
                    },
                    "clear_first": {
                        "type": "boolean",
                        "description": "Clear existing text before typing (Ctrl+A, Delete)",
                        "default": False,
                    },
                    "submit": {
                        "type": "boolean",
                        "description": "Press Enter after typing",
                        "default": False,
                    },
                },
                "required": ["text"],
            },
            annotations=ToolAnnotations(destructiveHint=True),
        ),
        Tool(
            name="desktop_key",
            description="Press a keyboard key or shortcut.",
            inputSchema={
                "type": "object",
                "properties": {
                    "key": {
                        "type": "string",
                        "description": "Key name (e.g., 'Return', 'Tab', 'Escape', 'a')",
                    },
                    "modifiers": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Modifier keys like ['ctrl', 'shift', 'alt', 'super']",
                    },
                },
                "required": ["key"],
            },
            annotations=ToolAnnotations(destructiveHint=True),
        ),
        Tool(
            name="desktop_capabilities",
            description="Get information about available desktop automation capabilities.",
            inputSchema={"type": "object", "properties": {}},
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        Tool(
            name="desktop_context",
            description="Get information about the current window group context and available windows. "
            "Similar to Chrome extension's tabs_context. Call this to understand which windows "
            "Claude is currently working with.",
            inputSchema={
                "type": "object",
                "properties": {
                    "list_available": {
                        "type": "boolean",
                        "description": "Also list all available windows on desktop (default: false)",
                        "default": False,
                    }
                },
            },
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        Tool(
            name="desktop_target_window",
            description="Target a specific window for automation. Draws a colored border around "
            "the window to indicate it's being controlled by Claude. The targeted window "
            "will be added to the current window group. Use desktop_context first to see "
            "available windows.",
            inputSchema={
                "type": "object",
                "properties": {
                    "window_title": {
                        "type": "string",
                        "description": "Window title to match (partial match supported)",
                    },
                    "app_name": {
                        "type": "string",
                        "description": "Application name to filter by",
                    },
                    "window_id": {
                        "type": "string",
                        "description": "Direct window ID from desktop_context (win_N)",
                    },
                    "color": {
                        "type": "string",
                        "enum": ["blue", "purple", "green", "orange", "red", "cyan"],
                        "description": "Border color for the window (default: blue)",
                        "default": "blue",
                    },
                },
            },
            annotations=ToolAnnotations(idempotentHint=True),
        ),
        Tool(
            name="desktop_create_window_group",
            description="Create a new window group for organizing targeted windows. "
            "Similar to Chrome's tab groups. If a window group already exists, "
            "this creates a new one and makes it active.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Optional name for the group",
                    },
                    "color": {
                        "type": "string",
                        "enum": ["blue", "purple", "green", "orange", "red", "cyan"],
                        "description": "Color for the group (default: blue)",
                        "default": "blue",
                    },
                },
            },
            annotations=ToolAnnotations(idempotentHint=True),
        ),
        Tool(
            name="desktop_release_window",
            description="Release a window from the current group. Removes the border overlay "
            "and stops tracking the window.",
            inputSchema={
                "type": "object",
                "properties": {
                    "window_id": {
                        "type": "string",
                        "description": "Window ID to release (win_N from desktop_context)",
                    },
                    "release_all": {
                        "type": "boolean",
                        "description": "Release all windows in current group",
                        "default": False,
                    },
                },
            },
            annotations=ToolAnnotations(idempotentHint=True),
        ),
        # --- System tools added by local tuning (modeled on Windows-MCP toolset) ---
        Tool(
            name="desktop_shell",
            description="Execute a bash command on the system (modeled on Windows-MCP's "
            "PowerShell tool). Use it to navigate the file system, manage files and "
            "processes, and run system-level operations. Dangerous commands "
            "(shutdown/reboot, mkfs, dd, rm -rf /, fork bombs, etc.) are blocked.",
            inputSchema={
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The bash command to execute"},
                    "timeout": {
                        "type": "integer",
                        "description": "Timeout in seconds (default: 30, max: 300)",
                        "default": 30,
                    },
                    "cwd": {
                        "type": "string",
                        "description": "Working directory for the command (optional)",
                    },
                },
                "required": ["command"],
            },
            annotations=ToolAnnotations(destructiveHint=True),
        ),
        Tool(
            name="desktop_clipboard",
            description="Read or write the system clipboard text (modeled on Windows-MCP's "
            "Clipboard tool). Uses wl-clipboard on Wayland, xclip on X11.",
            inputSchema={
                "type": "object",
                "properties": {
                    "mode": {
                        "type": "string",
                        "enum": ["get", "set"],
                        "description": "'get' to read clipboard, 'set' to write it",
                        "default": "get",
                    },
                    "text": {
                        "type": "string",
                        "description": "Text to put on the clipboard (required for set mode)",
                    },
                },
            },
            annotations=ToolAnnotations(destructiveHint=True),
        ),
        Tool(
            name="desktop_launch",
            description="Launch an installed desktop application by name (modeled on "
            "Windows-MCP's App/Launch tool). Matches against .desktop entries "
            "(partial, case-insensitive match supported).",
            inputSchema={
                "type": "object",
                "properties": {
                    "app_name": {
                        "type": "string",
                        "description": "Application name or .desktop ID (e.g., 'firefox', 'files')",
                    },
                },
                "required": ["app_name"],
            },
            annotations=ToolAnnotations(destructiveHint=True),
        ),
        Tool(
            name="desktop_notify",
            description="Send a desktop notification (modeled on Windows-MCP's "
            "Notification tool, implemented with notify-send).",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Notification title"},
                    "body": {
                        "type": "string",
                        "description": "Notification body text (optional)",
                    },
                    "urgency": {
                        "type": "string",
                        "enum": ["low", "normal", "critical"],
                        "description": "Notification urgency (default: normal)",
                        "default": "normal",
                    },
                },
            },
            annotations=ToolAnnotations(idempotentHint=True),
        ),
    ]
