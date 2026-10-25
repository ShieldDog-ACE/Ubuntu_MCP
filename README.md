# Linux Desktop MCP Server

[![PyPI version](https://badge.fury.io/py/linux-desktop-mcp.svg)](https://pypi.org/project/linux-desktop-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

> **Built with [Claude Code](https://claude.ai/claude-code)** - This entire MCP server was developed using Claude Code, Anthropic's AI-powered coding assistant. We're proud to showcase what's possible with AI-assisted development!

An MCP server that provides Chrome-extension-level semantic element targeting for native Linux desktop applications using AT-SPI2 (Assistive Technology Service Provider Interface).

> ### ⚠️ 本仓库是衍生版本（Derivative Work）
>
> 本仓库并非原创项目，而是以下游开源项目的**适配版本**：
>
> - **上游项目**：[`BeckhamLabsLLC/linux-desktop-mcp`](https://github.com/BeckhamLabsLLC/linux-desktop-mcp)
> - **上游版本**：v0.2.0
> - **上游版权**：Copyright © 2025 Austin Beck，以 MIT License 发布
> - **本仓库维护者**：[ShieldDog-ACE](https://github.com/ShieldDog-ACE)
>
> 本仓库在上游代码基础上只做了**本地化适配**，未改动上游核心的 AT-SPI2 语义定位与输入后端逻辑。具体差异见下方 [本地适配改动](#本地适配改动)。
>
> 上游代码版权归原作者所有。本仓库沿用上游的 **MIT License**（见 [LICENSE](LICENSE)），上游版权声明完整保留。

## 本地适配改动

相对上游 v0.2.0，本仓库的改动如下：

| 类型 | 文件 | 说明 |
|---|---|---|
| 新增 | `src/linux_desktop_mcp/system_tools.py` | 4 个系统级桌面工具的实现，参考 [Windows-MCP](https://github.com/CursorTouch/Windows-MCP) 的工具集设计移植到 Linux |
| 修改 | `src/linux_desktop_mcp/tool_definitions.py` | 注册上述 4 个工具的定义 |
| 修改 | `src/linux_desktop_mcp/handlers.py` | 将 4 个工具接入 `HANDLER_MAP` 派发表 |
| 修改 | `pyproject.toml` | 依赖收敛为 `mcp>=1.0.0,<2`，避免 MCP SDK 2.x 的破坏性变更 |

目标很直接：**在 Ubuntu 上让 AI 直接操控桌面** —— 既能按语义引用点控件，也能执行命令、读写剪贴板、启动应用、发通知。

## Features

- **Semantic Element References**: Just like Chrome extension's `ref_1`, `ref_2` system
- **Role Detection**: Identifies buttons, text fields, links, menus, etc.
- **State Detection**: Tracks focused, enabled, checked, editable states
- **Natural Language Search**: Find elements by description ("save button", "search field")
- **Cross-Platform Input**: Works on X11, Wayland, and XWayland
- **GTK/Qt/Electron Support**: Works with any application that exposes accessibility

## Installation

### System Dependencies

```bash
# Ubuntu/Debian
sudo apt install python3-pyatspi gir1.2-atspi-2.0 at-spi2-core

# For X11 input simulation
sudo apt install xdotool

# For Wayland input simulation (recommended)
# Install ydotool from source or your package manager
# Then start the daemon:
sudo ydotoold &
```

### Python Package

```bash
# From PyPI
pip install linux-desktop-mcp

# Or from source (this adapted repository)
git clone https://github.com/ShieldDog-ACE/Ubuntu_MCP.git
cd Ubuntu_MCP
pip install -e .
```

### Enable Accessibility

Ensure accessibility is enabled in your desktop environment:

- **GNOME**: Settings → Accessibility → Enable accessibility features
- **KDE**: System Settings → Accessibility
- Most modern desktops have this enabled by default

## Configuration

Add to `~/.claude/settings.json`:

```json
{
  "mcpServers": {
    "linux-desktop": {
      "command": "linux-desktop-mcp"
    }
  }
}
```

Or if installed from source:

```json
{
  "mcpServers": {
    "linux-desktop": {
      "command": "python",
      "args": ["-m", "linux_desktop_mcp"]
    }
  }
}
```

## Available Tools

### `desktop_snapshot`

Capture the accessibility tree with semantic element references.

```
Parameters:
  app_name: str (optional) - Filter to specific application
  max_depth: int (default: 15) - Tree traversal depth

Returns:
  Tree of elements with ref_ids:
  - ref_1: [application] Firefox
    - ref_2: [frame] "GitHub - Mozilla Firefox"
      - ref_3: [button] "Back" (clickable)
      - ref_4: [entry] "Search or enter address" (editable, focused)
```

### `desktop_find`

Find elements by natural language query.

```
Parameters:
  query: str - "save button", "search field", "menu containing File"
  app_name: str (optional)

Returns:
  Matching elements with refs, states, and actions
```

### `desktop_click`

Click an element by reference or coordinates.

```
Parameters:
  ref: str - Element reference (e.g., "ref_5")
  element: str - Human description for logging
  coordinate: [x, y] - Fallback if no ref
  button: left|right|middle
  click_type: single|double
  modifiers: [ctrl, shift, alt, super]
```

### `desktop_type`

Type text into an element.

```
Parameters:
  text: str - Text to type
  ref: str - Element to focus first (optional)
  element: str - Human description
  clear_first: bool - Ctrl+A, Delete before typing
  submit: bool - Press Enter after
```

### `desktop_key`

Press keyboard keys/shortcuts.

```
Parameters:
  key: str - Key name (Return, Tab, Escape, a, etc.)
  modifiers: [ctrl, shift, alt, super]
```

### `desktop_capabilities`

Check available automation capabilities.

### 系统级工具（本地适配新增）

以下 4 个工具由本仓库新增，设计参考 Windows-MCP 的同名能力，移植到 Linux 桌面。

#### `desktop_shell`

在系统上执行 bash 命令（带危险命令拦截）。

```
Parameters:
  command: str - 要执行的 bash 命令（最长 5000 字符）
  timeout: int (default: 30, max: 300) - 超时秒数

Returns:
  exit code + 合并后的 stdout/stderr（截断至 10000 字符）
```

内置危险命令拦截（正则匹配即拒绝）：`shutdown`/`reboot`/`poweroff`、`mkfs`、
`dd if=`、`rm -rf /`、`rm -rf ~`、fork bomb、`chmod -R 777 /`、覆盖块设备等。

#### `desktop_clipboard`

读取或写入系统剪贴板文本（Wayland 用 `wl-clipboard`，X11 用 `xclip`）。

```
Parameters:
  action: get|set - 读取或写入
  text: str - action=set 时要写入的文本

Returns:
  action=get 时返回当前剪贴板文本；action=set 时返回确认信息
```

#### `desktop_launch`

按名称启动已安装的桌面应用（解析 `.desktop` 启动项）。

```
Parameters:
  app: str - 应用名或 .desktop 文件名（如 "firefox"、"code"）

Returns:
  启动结果与进程信息
```

#### `desktop_notify`

发送桌面通知（基于 `notify-send`）。

```
Parameters:
  title: str - 通知标题
  message: str - 通知正文
  urgency: low|normal|critical (optional) - 紧急程度

Returns:
  发送结果
```

## Example Usage

### Example 1: Navigating to a Website in Firefox

```
User: "Open GitHub in Firefox"

Claude uses:
1. desktop_snapshot(app_name="Firefox")
   → Returns UI tree with elements like:
     - ref_5: [entry] "Search or enter address" (editable, focused)
     - ref_12: [button] "Go" (clickable)

2. desktop_click(ref="ref_5", element="URL bar")
   → Clicks to focus the address bar

3. desktop_type(text="https://github.com", ref="ref_5", clear_first=True, submit=True)
   → Types the URL and presses Enter

Result: Firefox navigates to GitHub
```

### Example 2: Saving a File in LibreOffice

```
User: "Save this document as 'report.odt'"

Claude uses:
1. desktop_key(key="s", modifiers=["ctrl"])
   → Opens the Save dialog

2. desktop_snapshot(app_name="LibreOffice")
   → Returns dialog elements including:
     - ref_8: [entry] "File name:" (editable)
     - ref_15: [button] "Save" (clickable)

3. desktop_type(text="report.odt", ref="ref_8", clear_first=True)
   → Types the filename

4. desktop_click(ref="ref_15", element="Save button")
   → Clicks Save

Result: Document saved as report.odt
```

### Example 3: Searching in a Code Editor

```
User: "Search for 'TODO' comments in VS Code"

Claude uses:
1. desktop_find(query="search", app_name="Code")
   → Finds search-related elements

2. desktop_key(key="f", modifiers=["ctrl", "shift"])
   → Opens global search panel

3. desktop_snapshot(app_name="Code")
   → Returns search panel elements:
     - ref_22: [entry] "Search" (editable, focused)
     - ref_25: [checkbox] "Match Case"

4. desktop_type(text="TODO", ref="ref_22", submit=True)
   → Types search query and executes search

Result: VS Code shows all TODO comments across the project
```

### Example 4: Window Targeting for Multi-Window Automation

```
User: "Help me copy data from the spreadsheet to the email"

Claude uses:
1. desktop_context(list_available=True)
   → Lists all available windows

2. desktop_target_window(app_name="LibreOffice Calc", color="green")
   → Targets spreadsheet with green border

3. desktop_target_window(app_name="Thunderbird", color="blue")
   → Targets email client with blue border

4. desktop_snapshot()
   → Only shows elements from targeted windows (reduced context)

5. [Proceeds with copy/paste operations between windows]

Result: Claude can efficiently work across multiple applications
```

## Platform Support

| Feature | X11 | Wayland | XWayland |
|---------|-----|---------|----------|
| AT-SPI discovery | Full | Full | Full |
| Click by ref | Full | Full | Full |
| Type text | Full | Full | Full |
| ydotool input | Full | Full | Full |
| xdotool input | Full | No | Yes |

## Troubleshooting

### "AT-SPI2 not available"

```bash
sudo apt install python3-pyatspi gir1.2-atspi-2.0 at-spi2-core
```

### "AT-SPI2 registry not running"

Ensure accessibility is enabled in your desktop settings. You may need to log out and back in.

### "No input backend available" (Wayland)

```bash
# Install and start ydotool daemon
sudo ydotoold &
```

### Elements not showing up

Some applications may not expose accessibility information. Modern GTK3/4, Qt5/6, and Electron apps generally work well.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     MCP Protocol Layer                       │
│              (JSON-RPC over stdio, tool defs)                │
└─────────────────────────────────────────────────────────────┘
                              │
┌─────────────────────────────────────────────────────────────┐
│                  Reference Manager                           │
│          (ref_1, ref_2 mapping, lifecycle, GC)              │
└─────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┴───────────────────┐
          │                                       │
┌─────────────────────┐             ┌─────────────────────────┐
│   AT-SPI2 Backend   │             │   Input Backends        │
│     (pyatspi)       │             │ (ydotool/xdotool/wtype) │
└─────────────────────┘             └─────────────────────────┘
```

## Contributing

This project was created with Claude Code and we warmly welcome contributions! Whether you want to:

- Report bugs or request features
- Submit pull requests
- Fork and build your own version
- Improve documentation

We're very open to help and collaboration. See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## Privacy Policy

See [PRIVACY_POLICY.md](PRIVACY_POLICY.md) for our full privacy policy. In short: Linux Desktop MCP runs entirely on your local machine, collects no data, and requires no network connectivity.

## License

**MIT** - See [LICENSE](LICENSE) for details.

本仓库是 [`BeckhamLabsLLC/linux-desktop-mcp`](https://github.com/BeckhamLabsLLC/linux-desktop-mcp) 的衍生版本，
因此 `LICENSE` 中保留上游原始版权声明 `Copyright (c) 2025 Austin Beck`。MIT 协议允许修改、再分发与商用，
但要求保留该版权声明与本许可声明——本仓库遵守这一要求。本仓库新增部分的适配工作由 ShieldDog-ACE 完成。
