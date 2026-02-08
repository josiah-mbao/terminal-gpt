"""Enhanced UI module for Terminal GPT with professional polish and accessibility."""

import asyncio
import time
from datetime import datetime
from typing import Optional, Dict, Any, List
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.spinner import Spinner
from rich.theme import Theme
from rich.markdown import Markdown
from rich.live import Live
from rich.columns import Columns
from rich.align import Align

# Professional color theme
PROFESSIONAL_THEME = Theme({
    # Status colors
    "status.success": "bold green",
    "status.warning": "bold yellow",
    "status.error": "bold red",
    "status.info": "bold cyan",
    "status.debug": "bold magenta",
    
    # UI elements
    "ui.header": "bold white on blue",
    "ui.border": "dim cyan",
    "ui.highlight": "bold yellow",
    "ui.muted": "dim white",
    
    # Roles
    "role.user": "bold blue",
    "role.assistant": "bold magenta",
    "role.system": "dim cyan",
    "role.tool": "bold yellow",
    
    # Interactive elements
    "input.prompt": "bold cyan",
    "input.placeholder": "dim cyan",
    
    # Plugin colors (extendable)
    "plugin.file": "bold blue",
    "plugin.web": "bold green", 
    "plugin.calc": "bold yellow",
    "plugin.sports": "bold cyan",
    
    # Jengo theme colors (green theme)
    "jengo.header": "bold green",
    "jengo.accent": "bold bright_green",
    "jengo.subtitle": "bold green3",
})

console = Console(theme=PROFESSIONAL_THEME, force_terminal=True)


class StatusLevel:
    """Status message levels with associated colors and icons."""
    SUCCESS = ("✅", "status.success", "Success")
    WARNING = ("⚠️", "status.warning", "Warning") 
    ERROR = ("❌", "status.error", "Error")
    INFO = ("ℹ️", "status.info", "Info")
    DEBUG = ("🐛", "status.debug", "Debug")
    
    @classmethod
    def get_all(cls):
        """Get all status levels."""
        return [cls.SUCCESS, cls.WARNING, cls.ERROR, cls.INFO, cls.DEBUG]


class ThinkingSpinner:
    """Enhanced thinking spinner with different modes and messages."""
    
    def __init__(self):
        self.spinner_types = {
            "thinking": ("dots", "Analyzing your request"),
            "processing": ("bouncingBall", "Processing data"),
            "loading": ("line", "Loading resources"),
            "searching": ("star", "Searching for information"),
            "computing": ("growVertical", "Performing calculations"),
            "waiting": ("simpleDotsScrolling", "Waiting for response")
        }
    
    def get_spinner(self, mode: str = "thinking"):
        """Get spinner configuration for different modes."""
        if mode not in self.spinner_types:
            mode = "thinking"
        
        spinner_type, message = self.spinner_types[mode]
        return Spinner(spinner_type, text=message, style="status.info")


class EnhancedUI:
    """Enhanced UI with professional polish and accessibility features."""
    
    def __init__(self):
        self.console = console
        self.thinking_spinner = ThinkingSpinner()
        self.last_status_time = 0
    
    def print_jengo_ascii_art(self):
        """Print ASCII art heading for Jengo with green theme."""
        # ASCII art for "Faya" with green gradient
        ascii_art = [
                "     ██╗███████╗███╗   ██╗ ██████╗  ██████╗ ",
                "     ██║██╔════╝████╗  ██║██╔════╝ ██╔═══██╗ ",
                "     ██║█████╗  ██╔██╗ ██║██║  ███╗██║   ██║ ",
                "     ██║██╔══╝  ██║╚██╗██║██║   ██║██║   ██║ ",
                "██   ██║██╔══╝  ██║╚██╗██║██║   ██║██║   ██║ ",
                "╚█████╔╝███████╗██║ ╚████║╚██████╔╝╚██████╔╝",
                "╚════╝ ╚══════╝╚═╝  ╚═══╝ ╚═════╝  ╚═════╝ ",
        ]
        
        # Print each line with green gradient
        for i, line in enumerate(ascii_art):
            # Create gradient effect from light to dark green
            if i < 2:
                style = "jengo.header"
            elif i < 4:
                style = "jengo.accent"
            else:
                style = "jengo.header"
            
            self.console.print(Text(line, style=style))
        
    def print_status(self, level: tuple, message: str, details: Optional[str] = None, 
                    persistent: bool = False):
        """Print color-coded status message with optional details."""
        icon, style, level_name = level
        
        # Create status text
        status_text = Text(f"{icon} {message}", style=style)
        
        # Add details if provided
        if details:
            details_text = Text(f"  {details}", style="ui.muted")
            status_text.append("\n")
            status_text.append(details_text)
        
        # Add timestamp for debugging
        if level == StatusLevel.DEBUG:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
            status_text.append(f" [{timestamp}]", style="ui.muted")
        
        # Print with appropriate spacing
        if persistent:
            # For persistent status that shouldn't be cleared
            self.console.print(status_text)
        else:
            # For temporary status that can be overwritten
            self.console.print(status_text, end="\r" if not details else "\n")
    
    def print_warning(self, message: str, details: Optional[str] = None, persistent: bool = False):
        """Print a warning message."""
        self.print_status(StatusLevel.WARNING, message, details, persistent)
    
    def print_error(self, message: str, details: Optional[str] = None, persistent: bool = False):
        """Print an error message."""
        self.print_status(StatusLevel.ERROR, message, details, persistent)
    
    def print_success(self, message: str, details: Optional[str] = None, persistent: bool = False):
        """Print a success message."""
        self.print_status(StatusLevel.SUCCESS, message, details, persistent)
    
    def print_info(self, message: str, details: Optional[str] = None, persistent: bool = False):
        """Print an info message."""
        self.print_status(StatusLevel.INFO, message, details, persistent)
    
    def print_welcome(self):
        """Print enhanced welcome message with Jengo ASCII art."""
        # Print ASCII art header
        self.print_jengo_ascii_art()
        
        # Print subtitle
        subtitle = Text("AI-Powered Terminal Assistant", 
                       style="jengo.subtitle")
        self.console.print(Align(subtitle, align="center"))
        self.console.print()  # Empty line for spacing 
        
        # Create features list
        features = Panel(
            "[bold]✨ Features:[/bold]\n"
            "• Real-time AI conversations\n"
            "• Plugin ecosystem (files, web search, calculations)\n"
            "• Context-aware responses\n"
            "• Streaming responses\n"
            "• Multi-session support\n\n"
            "[dim]Type /help for commands or start chatting![/dim]",
            title="Welcome",
            border_style="status.info",
            padding=(1, 2)
        )
        
        # Create tips
        tips = Panel(
            "[bold]💡 Tips:[/bold]\n"
            "• Use /clear to clear the screen\n"
            "• Use /sessions to manage conversations\n"
            "• Use /stats to check system status\n"
            "• Type /help for all commands",
            title="Quick Tips",
            border_style="status.info",
            padding=(1, 2)
        )
        
        # Display welcome
        self.console.print(Columns([features, tips], equal=True, expand=True))
    
    def print_message(self, role: str, content: str, session_id: Optional[str] = None, 
                     metadata: Optional[Dict[str, Any]] = None):
        """Print chat message with enhanced formatting."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Determine role styling
        if role == "user":
            header_style = "role.user"
            border_style = "role.user"
            header_icon = "👤"
        elif role == "assistant":
            header_style = "role.assistant"
            border_style = "role.assistant"
            header_icon = "🤖"
            # Render as markdown for better formatting
            content = Markdown(content)
        elif role == "system":
            header_style = "role.system"
            border_style = "role.system"
            header_icon = "⚙️"
        elif role == "tool":
            header_style = "role.tool"
            border_style = "role.tool"
            header_icon = "🔧"
        else:
            header_style = "ui.muted"
            border_style = "ui.border"
            header_icon = "💬"
        
        # Create header with session info
        header_text = f"{header_icon} {role.title()}"
        if session_id:
            header_text += f" [dim]• {session_id}[/dim]"
        header_text += f" [dim]• {timestamp}[/dim]"
        
        # Add metadata if provided
        if metadata:
            meta_text = self._format_metadata(metadata)
            if meta_text:
                content = f"{content}\n\n{meta_text}"
        
        # Create panel
        panel = Panel(
            content,
            title=header_text,
            border_style=border_style,
            title_align="left",
            padding=(1, 2)
        )
        
        self.console.print(panel)
    
    def _format_metadata(self, metadata: Dict[str, Any]) -> str:
        """Format metadata for display."""
        if not metadata:
            return ""
        
        meta_lines = []
        for key, value in metadata.items():
            if key == "tokens_used" and value:
                meta_lines.append(f"📝 Tokens: {value}")
            elif key == "processing_time_ms" and value:
                meta_lines.append(f"⏱️ Time: {value}ms")
            elif key == "status" and value != "ok":
                meta_lines.append(f"🔧 Status: {value}")
        
        return " | ".join(meta_lines) if meta_lines else ""
    
    def thinking_indicator(self, mode: str = "thinking", duration: Optional[float] = None):
        """Create a thinking indicator context manager."""
        return ThinkingIndicator(self, mode, duration)
    
    def print_plugin_output(self, plugin_name: str, output_type: str, data: Any, 
                           title: Optional[str] = None):
        """Print standardized plugin output."""
        # Determine plugin color
        plugin_colors = {
            "read_file": "plugin.file",
            "write_file": "plugin.file", 
            "search_web": "plugin.web",
            "calculate": "plugin.calc",
            "sports": "plugin.sports"
        }
        
        color = plugin_colors.get(plugin_name, "plugin.file")
        
        # Format output based on type
        if output_type == "table":
            self._print_plugin_table(data, title or plugin_name.title(), color)
        elif output_type == "list":
            self._print_plugin_list(data, title or plugin_name.title(), color)
        elif output_type == "tree":
            self._print_plugin_tree(data, title or plugin_name.title(), color)
        else:
            self._print_plugin_text(data, title or plugin_name.title(), color)
    
    def _print_plugin_table(self, data: List[Dict], title: str, color: str):
        """Print plugin output as a table."""
        if not data:
            self.print_status(StatusLevel.INFO, f"No data from {title}")
            return
        
        table = Table(title=f"📊 {title}", border_style=color, show_header=True)
        
        # Add columns based on first row
        if data:
            for key in data[0].keys():
                table.add_column(key.title(), style=color)
            
            # Add rows
            for row in data:
                table.add_row(*[str(row[key]) for key in row.keys()])
        
        self.console.print(table)
    
    def _print_plugin_list(self, data: List[str], title: str, color: str):
        """Print plugin output as a list."""
        if not data:
            self.print_status(StatusLevel.INFO, f"No results from {title}")
            return
        
        list_text = Text(f"📋 {title}:\n", style=color)
        for i, item in enumerate(data, 1):
            list_text.append(f"  {i}. {item}\n", style="ui.muted")
        
        self.console.print(Panel(list_text, border_style=color))
    
    def _print_plugin_tree(self, data: Dict, title: str, color: str):
        """Print plugin output as a tree."""
        # Simple tree implementation
        tree_text = Text(f"🌳 {title}:\n", style=color)
        
        def add_tree_item(item, prefix="", is_last=True):
            if isinstance(item, dict):
                for i, (key, value) in enumerate(item.items()):
                    is_last_item = i == len(item) - 1
                    connector = "└── " if is_last_item else "├── "
                    tree_text.append(f"{prefix}{connector}{key}\n", style=color)
                    
                    if isinstance(value, (dict, list)):
                        new_prefix = prefix + ("    " if is_last_item else "│   ")
                        add_tree_item(value, new_prefix, is_last_item)
                    else:
                        current_prefix = prefix + ("    " if is_last_item else "│   ")
                        tree_text.append(f"{current_prefix}    {value}\n", style="ui.muted")
            elif isinstance(item, list):
                for i, value in enumerate(item):
                    is_last_item = i == len(item) - 1
                    connector = "└── " if is_last_item else "├── "
                    tree_text.append(f"{prefix}{connector}[item {i+1}]\n", style=color)
                    add_tree_item(value, prefix + ("    " if is_last_item else "│   "), is_last_item)
        
        add_tree_item(data)
        self.console.print(Panel(tree_text, border_style=color))
    
    def _print_plugin_text(self, data: str, title: str, color: str):
        """Print plugin output as text."""
        if not data:
            self.print_status(StatusLevel.INFO, f"No output from {title}")
            return
        
        # Try to parse as JSON for better formatting
        try:
            import json
            parsed = json.loads(data)
            formatted = json.dumps(parsed, indent=2)
            data = formatted
        except:
            pass  # Keep original data
        
        panel = Panel(
            data,
            title=f"📄 {title}",
            border_style=color,
            padding=(1, 2)
        )
        self.console.print(panel)
    
    def create_status_table(self, stats: Dict[str, Any]) -> Table:
        """Create an enhanced status table."""
        table = Table(
            title="📊 System Status", 
            border_style="status.info",
            show_header=True,
            header_style="bold cyan"
        )
        table.add_column("Metric", style="cyan", width=25)
        table.add_column("Value", style="magenta", width=35)
        table.add_column("Status", style="status.info", width=15)
        
        for key, value in stats.items():
            # Determine status indicator
            if isinstance(value, (int, float)):
                if value > 1000:
                    status = "⚠️ High"
                elif value > 100:
                    status = "ℹ️ Medium"
                else:
                    status = "✅ Low"
            else:
                status = "✅ OK"
            
            table.add_row(
                key.replace("_", " ").title(),
                str(value),
                status
            )
        
        return table
    
    def print_command_result(self, command: str, success: bool, message: str, 
                           duration: Optional[float] = None):
        """Print command execution result."""
        level = StatusLevel.SUCCESS if success else StatusLevel.ERROR
        icon = "✅" if success else "❌"
        
        result_text = f"{icon} {command}: {message}"
        if duration:
            result_text += f" [dim](took {duration:.2f}s)[/dim]"
        
        self.print_status(level, result_text, persistent=True)
    
    def validate_terminal_size(self) -> Dict[str, Any]:
        """Validate and report terminal size compatibility."""
        size = self.console.size
        width, height = size.width, size.height
        
        issues = []
        recommendations = []
        
        # Check minimum size
        if width < 80:
            issues.append(f"Terminal width ({width}) is below recommended 80 characters")
            recommendations.append("Consider increasing terminal width for better experience")
        
        if height < 24:
            issues.append(f"Terminal height ({height}) is below recommended 24 lines")
            recommendations.append("Consider increasing terminal height for better experience")
        
        # Check for accessibility
        if not self.console.color_system:
            issues.append("Color support not detected")
            recommendations.append("Enable color support in your terminal for better experience")
        
        return {
            "width": width,
            "height": height,
            "issues": issues,
            "recommendations": recommendations,
            "is_compatible": len(issues) == 0
        }
    
    def print_accessibility_report(self):
        """Print accessibility and terminal compatibility report."""
        validation = self.validate_terminal_size()
        
        if validation["is_compatible"]:
            self.print_status(
                StatusLevel.SUCCESS, 
                "✅ Terminal is compatible", 
                f"Size: {validation['width']}x{validation['height']}"
            )
        else:
            self.print_status(
                StatusLevel.WARNING,
                "⚠️ Terminal compatibility issues detected",
                f"Size: {validation['width']}x{validation['height']}"
            )
            
            for issue in validation["issues"]:
                self.print_status(StatusLevel.WARNING, issue, persistent=True)
            
            for rec in validation["recommendations"]:
                self.print_status(StatusLevel.INFO, rec, persistent=True)


class ThinkingIndicator:
    """Context manager for thinking indicators."""
    
    def __init__(self, ui: EnhancedUI, mode: str, duration: Optional[float] = None):
        self.ui = ui
        self.mode = mode
        self.duration = duration
        self.spinner = ui.thinking_spinner.get_spinner(mode)
        self.start_time = None
        self.task = None
    
    async def __aenter__(self):
        """Start the thinking indicator."""
        self.start_time = time.time()
        
        # Create a live display for the spinner
        self.live = Live(self.spinner, console=self.ui.console, refresh_per_second=10)
        self.live.start()
        
        # If duration is specified, schedule auto-stop
        if self.duration:
            self.task = asyncio.create_task(self._auto_stop())
        
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Stop the thinking indicator."""
        if self.task and not self.task.done():
            self.task.cancel()
        
        self.live.stop()
        
        # Print completion status
        elapsed = time.time() - self.start_time
        if elapsed > 5:  # Only show if it took significant time
            self.ui.print_status(
                StatusLevel.INFO,
                f"Completed in {elapsed:.2f}s",
                persistent=True
            )
    
    async def _auto_stop(self):
        """Auto-stop the spinner after specified duration."""
        await asyncio.sleep(self.duration)
        self.live.stop()


# Global enhanced UI instance
enhanced_ui = EnhancedUI()