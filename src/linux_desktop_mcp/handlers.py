"""MCP tool handler functions for Linux Desktop Automation.

Extracted from server.py for maintainability. Contains all ``_handle_*``
functions as standalone async functions plus a ``ServerContext`` dataclass
that carries shared state and a ``HANDLER_MAP`` dispatcher.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Optional

from mcp.types import TextContent

from .atspi_bridge import ATSPIBridge
from .detection import PlatformCapabilities
from .input_backends import InputManager
from .overlay import OverlayManager
from .references import ElementReference
from .window_discovery import WindowDiscovery
from .window_manager import GroupColor, WindowGeometry, WindowGroupManager

logger = logging.getLogger(__name__)

# Input validation constants
MAX_TEXT_LENGTH = 10000
MAX_QUERY_LENGTH = 1000
MAX_COORDINATE = 65535
MIN_COORDINATE = 0


@dataclass
class ServerContext:
    """Shared state passed to every handler function."""

    capabilities: Optional[PlatformCapabilities] = None
    bridge: Optional[ATSPIBridge] = None
    input: Optional[InputManager] = None
    window_manager: Optional[WindowGroupManager] = None
    window_discovery: Optional[WindowDiscovery] = None
    overlay_manager: Optional[OverlayManager] = None

    # --- Validation helpers --------------------------------------------------

    def validate_coordinate(self, value: int) -> bool:
        """Validate a coordinate value is within bounds."""
        return MIN_COORDINATE <= value <= MAX_COORDINATE

    def validate_coordinates(self, x: int, y: int) -> tuple[bool, str]:
        """Validate x,y coordinates. Returns (is_valid, error_message)."""
        if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            return False, "Coordinates must be numbers"
        x, y = int(x), int(y)
        if not self.validate_coordinate(x):
            return False, f"X coordinate {x} out of range (0-{MAX_COORDINATE})"
        if not self.validate_coordinate(y):
            return False, f"Y coordinate {y} out of range (0-{MAX_COORDINATE})"
        return True, ""

    def validate_string(self, value: str, max_len: int, name: str = "value") -> tuple[bool, str]:
        """Validate a string value. Returns (is_valid, error_message)."""
        if not isinstance(value, str):
            return False, f"{name} must be a string"
        if len(value) > max_len:
            return False, f"{name} too long ({len(value)} > {max_len})"
        return True, ""


# ---------------------------------------------------------------------------
# Handler functions
# ---------------------------------------------------------------------------


async def handle_snapshot(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_snapshot tool."""
    if ctx.bridge is None:
        return [
            TextContent(
                type="text",
                text="Error: AT-SPI2 not available. Install: sudo apt install python3-pyatspi gir1.2-atspi-2.0 at-spi2-core",
            )
        ]

    app_name = args.get("app_name")
    max_depth = args.get("max_depth", 15)

    # Check if we have targeted windows - if so, only scan those
    group = ctx.window_manager.get_active_group() if ctx.window_manager else None
    targeted_mode = False

    if group and group.windows and not app_name:
        # Use targeted windows for reduced context
        targeted_mode = True
        # Validate windows first (remove closed ones)
        group.validate_windows()

        if not group.windows:
            return [
                TextContent(
                    type="text",
                    text="All targeted windows have been closed. Use desktop_target_window to target new windows.",
                )
            ]

        # Get active window or all windows in group
        active_window = group.get_active_window()
        if active_window and active_window.atspi_accessible:
            refs = await ctx.bridge.build_tree_for_window(
                active_window.atspi_accessible, max_depth=max_depth
            )
            window_info = f'Window: "{active_window.window_title}" ({active_window.app_name})'
        else:
            # Build tree for all windows in group
            window_accessibles = [
                t.atspi_accessible for t in group.windows.values() if t.atspi_accessible
            ]
            refs = await ctx.bridge.build_tree_for_windows(window_accessibles, max_depth=max_depth)
            window_info = f"All {len(group.windows)} targeted windows"
    else:
        # No targeting - use full desktop scan (original behavior)
        refs = await ctx.bridge.build_tree(app_name_filter=app_name, max_depth=max_depth)
        window_info = None

    if not refs:
        return [
            TextContent(
                type="text",
                text="No elements found. Ensure applications are running and accessibility is enabled.",
            )
        ]

    if targeted_mode:
        output_lines = ["# Accessibility Tree (Targeted)", f"# {window_info}", ""]
    else:
        output_lines = ["# Desktop Accessibility Tree", ""]
        if app_name:
            output_lines.insert(1, f"# Filtered by app: {app_name}")

    def build_tree_output(ref: ElementReference, indent: int = 0) -> list[str]:
        lines = [ref.format_for_display(indent)]
        for child_id in ref.child_refs:
            child = ctx.bridge.ref_manager.get(child_id)
            if child:
                lines.extend(build_tree_output(child, indent + 1))
        return lines

    root_refs = [r for r in refs if r.parent_ref is None]
    for root in root_refs:
        output_lines.extend(build_tree_output(root))
        output_lines.append("")

    output_lines.append(f"\nTotal elements: {len(refs)}")
    if targeted_mode:
        output_lines.append("(Context reduced via window targeting)")

    return [TextContent(type="text", text="\n".join(output_lines))]


async def handle_find(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_find tool."""
    if ctx.bridge is None:
        return [TextContent(type="text", text="Error: AT-SPI2 not available")]

    query = args.get("query", "")
    app_name = args.get("app_name")

    # Validate query
    valid, error = ctx.validate_string(query, MAX_QUERY_LENGTH, "query")
    if not valid:
        return [TextContent(type="text", text=f"Error: {error}")]
    if not query.strip():
        return [TextContent(type="text", text="Error: Query cannot be empty")]

    # Check if we have targeted windows - if so, only search those
    group = ctx.window_manager.get_active_group() if ctx.window_manager else None
    targeted_mode = False

    if group and group.windows and not app_name:
        # Use targeted windows for reduced context
        targeted_mode = True
        group.validate_windows()

        if not group.windows:
            return [
                TextContent(
                    type="text",
                    text="All targeted windows have been closed. Use desktop_target_window to target new windows.",
                )
            ]

        # Get active window or all windows in group
        active_window = group.get_active_window()
        if active_window and active_window.atspi_accessible:
            await ctx.bridge.build_tree_for_window(active_window.atspi_accessible)
        else:
            window_accessibles = [
                t.atspi_accessible for t in group.windows.values() if t.atspi_accessible
            ]
            await ctx.bridge.build_tree_for_windows(window_accessibles)
    else:
        await ctx.bridge.build_tree(app_name_filter=app_name)

    matches = ctx.bridge.ref_manager.find_by_query(query)

    if not matches:
        scope_note = " (in targeted windows)" if targeted_mode else ""
        return [TextContent(type="text", text=f"No elements found matching: {query}{scope_note}")]

    scope_note = " (in targeted windows)" if targeted_mode else ""
    output_lines = [f"# Found {len(matches)} elements matching '{query}'{scope_note}", ""]

    for ref in matches[:20]:
        state_str = ", ".join(ref.state.to_list()) if ref.state.to_list() else "normal"
        bounds = f"({ref.bounds.x}, {ref.bounds.y}, {ref.bounds.width}x{ref.bounds.height})"
        output_lines.append(
            f'- {ref.ref_id}: [{ref.role.value}] "{ref.name}" ({state_str}) at {bounds}'
        )
        if ref.app_name:
            output_lines.append(f"  App: {ref.app_name}")
        if ref.available_actions:
            output_lines.append(f"  Actions: {', '.join(ref.available_actions)}")
        output_lines.append("")

    if len(matches) > 20:
        output_lines.append(f"... and {len(matches) - 20} more")

    return [TextContent(type="text", text="\n".join(output_lines))]


async def handle_click(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_click tool."""
    if ctx.bridge is None:
        return [TextContent(type="text", text="Error: AT-SPI2 not available")]

    ref_id = args.get("ref")
    coordinate = args.get("coordinate")
    button = args.get("button", "left")
    click_type = args.get("click_type", "single")
    modifiers = args.get("modifiers")
    element_desc = args.get("element", "element")

    if ref_id:
        ref = ctx.bridge.ref_manager.get(ref_id)
        if not ref:
            return [
                TextContent(
                    type="text",
                    text=f"Error: Reference {ref_id} not found or expired. Run desktop_snapshot first.",
                )
            ]

        if ref.atspi_accessible and "click" in ref.available_actions:
            success = await ctx.bridge.click_element(ref, button)
            if success:
                return [
                    TextContent(
                        type="text", text=f"Clicked {element_desc} ({ref_id}) via AT-SPI action"
                    )
                ]

        if ctx.input and ctx.input.can_click:
            success = await ctx.input.click_element(ref, button, click_type, modifiers)
            if success:
                x, y = ref.bounds.center
                return [
                    TextContent(
                        type="text", text=f"Clicked {element_desc} ({ref_id}) at ({x}, {y})"
                    )
                ]

        return [TextContent(type="text", text=f"Failed to click {element_desc}")]

    elif coordinate:
        if not ctx.input or not ctx.input.can_click:
            return [TextContent(type="text", text="Error: No input backend available")]

        if len(coordinate) != 2:
            return [TextContent(type="text", text="Error: Coordinate must be [x, y]")]

        x, y = coordinate
        valid, error = ctx.validate_coordinates(x, y)
        if not valid:
            return [TextContent(type="text", text=f"Error: {error}")]

        x, y = int(x), int(y)
        success = await ctx.input.click(x, y, button, click_type, modifiers)
        if success:
            return [TextContent(type="text", text=f"Clicked at ({x}, {y})")]
        return [TextContent(type="text", text=f"Failed to click at ({x}, {y})")]

    return [TextContent(type="text", text="Error: Provide either ref or coordinate")]


async def handle_type(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_type tool."""
    if not ctx.input or not ctx.input.can_type:
        return [TextContent(type="text", text="Error: No keyboard input available")]

    text = args.get("text", "")
    ref_id = args.get("ref")

    # Validate text length
    valid, error = ctx.validate_string(text, MAX_TEXT_LENGTH, "text")
    if not valid:
        return [TextContent(type="text", text=f"Error: {error}")]
    clear_first = args.get("clear_first", False)
    submit = args.get("submit", False)
    element_desc = args.get("element", "element")

    if ref_id:
        if ctx.bridge is None:
            return [TextContent(type="text", text="Error: AT-SPI2 not available")]

        ref = ctx.bridge.ref_manager.get(ref_id)
        if not ref:
            return [
                TextContent(type="text", text=f"Error: Reference {ref_id} not found or expired")
            ]

        if ref.atspi_accessible and ref.state.editable:
            success = await ctx.bridge.set_text(ref, text, clear_first)
            if success:
                msg = f"Set text in {element_desc} ({ref_id}) via AT-SPI"
                if submit:
                    await ctx.input.key("Return")
                    msg += " and pressed Enter"
                return [TextContent(type="text", text=msg)]

        if ctx.input.can_click:
            success = await ctx.input.click_element(ref)
            if not success:
                return [TextContent(type="text", text=f"Failed to focus {element_desc}")]
            await asyncio.sleep(0.1)

    if clear_first:
        await ctx.input.key("a", ["ctrl"])
        await asyncio.sleep(0.05)
        await ctx.input.key("Delete")
        await asyncio.sleep(0.05)

    success = await ctx.input.type_text(text)
    if not success:
        return [TextContent(type="text", text="Failed to type text")]

    msg = "Typed text"
    if ref_id:
        msg = f"Typed text in {element_desc} ({ref_id})"

    if submit:
        await asyncio.sleep(0.05)
        await ctx.input.key("Return")
        msg += " and pressed Enter"

    return [TextContent(type="text", text=msg)]


async def handle_key(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_key tool."""
    if not ctx.input or not ctx.input.can_type:
        return [TextContent(type="text", text="Error: No keyboard input available")]

    key = args.get("key", "")
    modifiers = args.get("modifiers")

    # Validate key name
    if not key or not isinstance(key, str):
        return [TextContent(type="text", text="Error: Key name is required")]
    if len(key) > 50:
        return [TextContent(type="text", text="Error: Key name too long")]

    success = await ctx.input.key(key, modifiers)
    if success:
        mod_str = "+".join(modifiers) + "+" if modifiers else ""
        return [TextContent(type="text", text=f"Pressed {mod_str}{key}")]

    return [TextContent(type="text", text="Failed to press key")]


async def handle_capabilities(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_capabilities tool."""
    caps = ctx.capabilities
    lines = [
        "# Linux Desktop Automation Capabilities",
        "",
        f"Display Server: {caps.display_server.value}",
    ]
    if caps.compositor_name:
        lines.append(f"Compositor: {caps.compositor_name}")
    lines.extend(
        [
            f"AT-SPI2 Available: {caps.has_atspi}",
            f"AT-SPI2 Registry Running: {caps.atspi_registry_available}",
            "",
            "## Input Tools",
            f"- ydotool: {'Available' if caps.has_ydotool else 'Not found'}",
            f"- xdotool: {'Available' if caps.has_xdotool else 'Not found'}",
            f"- wtype: {'Available' if caps.has_wtype else 'Not found'}",
            "",
            f"Active Input Backend: {ctx.input.backend_name if ctx.input else 'None'}",
            f"Can Click: {ctx.input.can_click if ctx.input else False}",
            f"Can Type: {ctx.input.can_type if ctx.input else False}",
            "",
            "## Screenshot Tools",
            f"- scrot: {'Available' if caps.has_scrot else 'Not found'}",
            f"- grim: {'Available' if caps.has_grim else 'Not found'}",
            "",
            "## OCR Tools",
            f"- tesseract: {'Available' if caps.has_tesseract else 'Not found'}",
            "",
            "## Window Targeting",
            f"- Window Discovery: {'Available' if ctx.window_discovery else 'Not available'}",
        ]
    )
    if ctx.overlay_manager:
        lines.append(
            f"- Visual Overlays: {'Available' if ctx.overlay_manager.has_visual_support else 'Not supported'}"
        )
        if caps.display_server.value == "wayland" and caps.compositor_name == "gnome":
            lines.append("  (GNOME Wayland does not support window overlays)")
    else:
        lines.append("- Visual Overlays: Not initialized")
    if caps.has_layer_shell:
        lines.append("- Layer Shell: Available")

    if caps.errors:
        lines.append("")
        lines.append("## Errors/Warnings")
        for error in caps.errors:
            lines.append(f"- {error}")

    return [TextContent(type="text", text="\n".join(lines))]


async def handle_context(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_context tool - get window group context."""
    list_available = args.get("list_available", False)
    output_lines = ["# Desktop Context", ""]

    # Show current window group info
    group = ctx.window_manager.get_active_group() if ctx.window_manager else None
    if group:
        output_lines.append("## Active Window Group")
        output_lines.append(f"- Group ID: {group.group_id}")
        if group.name:
            output_lines.append(f"- Name: {group.name}")
        output_lines.append(f"- Color: {group.color.name.lower()} ({group.color.value})")
        output_lines.append(f"- Windows: {len(group.windows)}")
        output_lines.append("")

        if group.windows:
            output_lines.append("### Targeted Windows")
            # Validate windows first (remove closed ones)
            removed = group.validate_windows()
            if removed:
                output_lines.append(f"(Removed {len(removed)} closed windows)")

            for target in group.windows.values():
                active_marker = " [ACTIVE]" if target.is_active else ""
                geom_str = ""
                if target.geometry:
                    geom_str = f" at ({target.geometry.x}, {target.geometry.y}, {target.geometry.width}x{target.geometry.height})"
                output_lines.append(
                    f'- {target.window_id}: "{target.window_title}" ({target.app_name}){geom_str}{active_marker}'
                )
            output_lines.append("")
    else:
        output_lines.append("No active window group. Use desktop_target_window to target a window.")
        output_lines.append("")

    # List available windows if requested
    if list_available:
        output_lines.append("## Available Windows")
        if ctx.window_discovery:
            try:
                windows = await ctx.window_discovery.enumerate_windows()
                if windows:
                    for win in windows:
                        active_marker = " [FOCUSED]" if win.is_focused else ""
                        geom_str = ""
                        if win.geometry:
                            geom_str = f" at ({win.geometry.x}, {win.geometry.y}, {win.geometry.width}x{win.geometry.height})"
                        output_lines.append(
                            f'- "{win.window_title}" ({win.app_name}){geom_str}{active_marker}'
                        )
                else:
                    output_lines.append("No windows found")
            except Exception as e:
                output_lines.append(f"Error enumerating windows: {e}")
        else:
            output_lines.append("Window discovery not available")

    return [TextContent(type="text", text="\n".join(output_lines))]


async def handle_target_window(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_target_window tool - target a window for automation."""
    if not ctx.window_discovery:
        return [TextContent(type="text", text="Error: Window discovery not available")]

    window_title = args.get("window_title")
    app_name = args.get("app_name")
    window_id = args.get("window_id")
    color_str = args.get("color", "blue")
    color = GroupColor.from_string(color_str)

    # If window_id provided, find in existing targeted windows
    if window_id:
        result = ctx.window_manager.find_window_by_id(window_id)
        if result:
            group, target = result
            group.set_active_window(window_id)
            return [
                TextContent(
                    type="text", text=f"Switched to window: {target.window_title} ({window_id})"
                )
            ]
        else:
            return [
                TextContent(
                    type="text", text=f"Window ID {window_id} not found in targeted windows"
                )
            ]

    # Find window by title/app name
    if not window_title and not app_name:
        return [
            TextContent(
                type="text", text="Error: Provide either window_title, app_name, or window_id"
            )
        ]

    try:
        if window_title:
            windows = await ctx.window_discovery.find_window_by_title(window_title, app_name)
        else:
            windows = await ctx.window_discovery.find_windows_by_app(app_name)

        if not windows:
            search_desc = f"title='{window_title}'" if window_title else f"app='{app_name}'"
            return [TextContent(type="text", text=f"No windows found matching {search_desc}")]

        # Use first match
        win = windows[0]
        geometry = (
            WindowGeometry(
                x=win.geometry.x,
                y=win.geometry.y,
                width=win.geometry.width,
                height=win.geometry.height,
            )
            if win.geometry
            else None
        )

        group, target = ctx.window_manager.add_window_to_active_group(
            app_name=win.app_name,
            window_title=win.window_title,
            atspi_accessible=win.atspi_accessible,
            geometry=geometry,
            color=color,
        )

        # Show border overlay (if overlay manager available)
        if ctx.overlay_manager and geometry:
            try:
                ctx.overlay_manager.show_border(target.window_id, geometry, color)
            except Exception as e:
                logger.warning(f"Failed to show border overlay: {e}")

        output_lines = [
            "# Window Targeted",
            "",
            f"- Window ID: {target.window_id}",
            f'- Title: "{target.window_title}"',
            f"- Application: {target.app_name}",
            f"- Group: {group.group_id}",
            f"- Color: {color.name.lower()}",
        ]
        if geometry:
            output_lines.append(f"- Position: ({geometry.x}, {geometry.y})")
            output_lines.append(f"- Size: {geometry.width}x{geometry.height}")

        if len(windows) > 1:
            output_lines.append("")
            output_lines.append(f"Note: {len(windows)} windows matched. Targeted first match.")

        return [TextContent(type="text", text="\n".join(output_lines))]

    except Exception as e:
        return [TextContent(type="text", text=f"Error targeting window: {e}")]


async def handle_create_window_group(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_create_window_group tool."""
    name = args.get("name")
    color_str = args.get("color", "blue")
    color = GroupColor.from_string(color_str)

    group = ctx.window_manager.create_group(name=name, color=color)
    ctx.window_manager.set_active_group(group.group_id)

    output_lines = [
        "# Window Group Created",
        "",
        f"- Group ID: {group.group_id}",
    ]
    if name:
        output_lines.append(f"- Name: {name}")
    output_lines.append(f"- Color: {color.name.lower()} ({color.value})")
    output_lines.append("")
    output_lines.append("Use desktop_target_window to add windows to this group.")

    return [TextContent(type="text", text="\n".join(output_lines))]


async def handle_release_window(ctx: ServerContext, args: dict[str, Any]) -> list[TextContent]:
    """Handle desktop_release_window tool."""
    window_id = args.get("window_id")
    release_all = args.get("release_all", False)

    if release_all:
        count = ctx.window_manager.release_all_windows()
        # Hide all overlays
        if ctx.overlay_manager:
            try:
                ctx.overlay_manager.hide_all_borders()
            except Exception as e:
                logger.warning(f"Failed to hide overlays: {e}")
        return [TextContent(type="text", text=f"Released {count} windows from all groups")]

    if not window_id:
        return [TextContent(type="text", text="Error: Provide window_id or set release_all=true")]

    target = ctx.window_manager.release_window(window_id)
    if target:
        # Hide overlay for this window
        if ctx.overlay_manager:
            try:
                ctx.overlay_manager.hide_border(window_id)
            except Exception as e:
                logger.warning(f"Failed to hide overlay: {e}")
        return [
            TextContent(type="text", text=f'Released window: "{target.window_title}" ({window_id})')
        ]
    else:
        return [TextContent(type="text", text=f"Window ID {window_id} not found")]


# ---------------------------------------------------------------------------
# Handler dispatch map
# ---------------------------------------------------------------------------

# System tools added by local tuning (modeled on Windows-MCP toolset).
# Imported here (after this module's constants/classes are defined) to avoid a
# circular import, since system_tools imports MAX_TEXT_LENGTH / ServerContext.
from .system_tools import (  # noqa: E402
    handle_clipboard,
    handle_launch,
    handle_notify,
    handle_shell,
)

HANDLER_MAP: dict[str, Any] = {
    "desktop_snapshot": handle_snapshot,
    "desktop_find": handle_find,
    "desktop_click": handle_click,
    "desktop_type": handle_type,
    "desktop_key": handle_key,
    "desktop_capabilities": handle_capabilities,
    "desktop_context": handle_context,
    "desktop_target_window": handle_target_window,
    "desktop_create_window_group": handle_create_window_group,
    "desktop_release_window": handle_release_window,
    # System tools added by local tuning (modeled on Windows-MCP toolset)
    "desktop_shell": handle_shell,
    "desktop_clipboard": handle_clipboard,
    "desktop_launch": handle_launch,
    "desktop_notify": handle_notify,
}
