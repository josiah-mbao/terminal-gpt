"""Built-in plugins for Terminal GPT.

This module contains the core plugins that ship with Terminal GPT.
"""

from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field

from ..domain.plugins import Plugin
from ..domain.exceptions import PluginError


class ReadFileInput(BaseModel):
    """Input schema for read_file plugin."""
    path: str = Field(..., description="Path to the file to read")


class ReadFileOutput(BaseModel):
    """Output schema for read_file plugin."""
    content: str = Field(..., description="Content of the file")
    encoding: Optional[str] = Field(None, description="File encoding detected")


class ReadFilePlugin(Plugin):
    """Plugin for reading text files from disk."""

    name = "read_file"
    description = "Reads a text file from disk and returns its content"
    input_model = ReadFileInput
    output_model = ReadFileOutput

    async def run(self, input_data: ReadFileInput) -> ReadFileOutput:
        """Read a file and return its content."""
        try:
            path = Path(input_data.path).resolve()

            # Security: Prevent directory traversal
            if ".." in str(path) or not path.exists():
                raise PluginError(f"Invalid or non-existent file path: {input_data.path}")

            if not path.is_file():
                raise PluginError(f"Path is not a file: {input_data.path}")

            # Check file size (limit to 1MB)
            file_size = path.stat().st_size
            if file_size > 1024 * 1024:
                raise PluginError(f"File too large (>1MB): {file_size} bytes")

            # Read file content
            content = path.read_text(encoding='utf-8', errors='replace')

            return ReadFileOutput(
                content=content,
                encoding="utf-8"
            )

        except UnicodeDecodeError:
            raise PluginError(f"File is not valid UTF-8 text: {input_data.path}")
        except PermissionError:
            raise PluginError(f"Permission denied reading file: {input_data.path}")
        except Exception as e:
            raise PluginError(f"Failed to read file {input_data.path}: {e}")


class WriteFileInput(BaseModel):
    """Input schema for write_file plugin."""
    path: str = Field(..., description="Path where to write the file")
    content: str = Field(..., description="Content to write to the file")
    create_directories: bool = Field(False, description="Create parent directories if they don't exist")


class WriteFileOutput(BaseModel):
    """Output schema for write_file plugin."""
    success: bool = Field(..., description="Whether the write operation succeeded")
    bytes_written: int = Field(..., description="Number of bytes written")


class WriteFilePlugin(Plugin):
    """Plugin for writing text files to disk."""

    name = "write_file"
    description = "Writes text content to a file on disk"
    input_model = WriteFileInput
    output_model = WriteFileOutput

    async def run(self, input_data: WriteFileInput) -> WriteFileOutput:
        """Write content to a file."""
        try:
            path = Path(input_data.path).resolve()

            # Security: Prevent directory traversal
            if ".." in str(path):
                raise PluginError(f"Invalid file path: {input_data.path}")

            # Create directories if requested
            if input_data.create_directories:
                path.parent.mkdir(parents=True, exist_ok=True)

            # Write file content
            path.write_text(input_data.content, encoding='utf-8')

            bytes_written = len(input_data.content.encode('utf-8'))

            return WriteFileOutput(
                success=True,
                bytes_written=bytes_written
            )

        except PermissionError:
            raise PluginError(f"Permission denied writing to file: {input_data.path}")
        except Exception as e:
            raise PluginError(f"Failed to write file {input_data.path}: {e}")


class ListDirectoryInput(BaseModel):
    """Input schema for list_directory plugin."""
    path: str = Field(".", description="Directory path to list")
    show_hidden: bool = Field(False, description="Include hidden files/directories")


class DirectoryEntry(BaseModel):
    """Schema for directory entry information."""
    name: str = Field(..., description="Name of the file/directory")
    type: str = Field(..., description="Type: 'file' or 'directory'")
    size: Optional[int] = Field(None, description="File size in bytes (files only)")


class ListDirectoryOutput(BaseModel):
    """Output schema for list_directory plugin."""
    entries: List[DirectoryEntry] = Field(..., description="List of directory entries")
    total_count: int = Field(..., description="Total number of entries")


class ListDirectoryPlugin(Plugin):
    """Plugin for listing directory contents."""

    name = "list_directory"
    description = "Lists files and directories in a given directory"
    input_model = ListDirectoryInput
    output_model = ListDirectoryOutput

    async def run(self, input_data: ListDirectoryInput) -> ListDirectoryOutput:
        """List directory contents."""
        try:
            path = Path(input_data.path).resolve()

            # Security: Prevent directory traversal
            if ".." in str(path) or not path.exists():
                raise PluginError(f"Invalid or non-existent directory: {input_data.path}")

            if not path.is_dir():
                raise PluginError(f"Path is not a directory: {input_data.path}")

            entries = []
            for item in path.iterdir():
                # Skip hidden files unless requested
                if not input_data.show_hidden and item.name.startswith('.'):
                    continue

                entry_type = "directory" if item.is_dir() else "file"
                size = item.stat().st_size if item.is_file() else None

                entries.append(DirectoryEntry(
                    name=item.name,
                    type=entry_type,
                    size=size
                ))

            # Sort entries by name
            entries.sort(key=lambda e: e.name.lower())

            return ListDirectoryOutput(
                entries=entries,
                total_count=len(entries)
            )

        except PermissionError:
            raise PluginError(f"Permission denied accessing directory: {input_data.path}")
        except Exception as e:
            raise PluginError(f"Failed to list directory {input_data.path}: {e}")


class CalculatorInput(BaseModel):
    """Input schema for calculator plugin."""
    expression: str = Field(..., description="Mathematical expression to evaluate")


class CalculatorOutput(BaseModel):
    """Output schema for calculator plugin."""
    result: float = Field(..., description="Result of the calculation")
    expression: str = Field(..., description="Original expression evaluated")


class CalculatorPlugin(Plugin):
    """Plugin for performing mathematical calculations."""

    name = "calculator"
    description = "Evaluates mathematical expressions safely"
    input_model = CalculatorInput
    output_model = CalculatorOutput

    async def run(self, input_data: CalculatorInput) -> CalculatorOutput:
        """Evaluate a mathematical expression safely."""
        try:
            # Basic security: only allow safe mathematical operations
            allowed_chars = set("0123456789+-*/(). ")
            if not all(c in allowed_chars for c in input_data.expression):
                raise PluginError("Expression contains invalid characters")

            # Use eval with restricted globals/locals for safety
            result = eval(input_data.expression, {"__builtins__": {}}, {})

            if not isinstance(result, (int, float)):
                raise PluginError("Expression did not evaluate to a number")

            return CalculatorOutput(
                result=float(result),
                expression=input_data.expression
            )

        except ZeroDivisionError:
            raise PluginError("Division by zero in expression")
        except (SyntaxError, NameError, TypeError) as e:
            raise PluginError(f"Invalid mathematical expression: {e}")
        except Exception as e:
            raise PluginError(f"Failed to evaluate expression: {e}")


class SportsScoresInput(BaseModel):
    """Input schema for sports_scores plugin."""
    league: str = Field(..., description="Sports league: 'EPL' or 'NBA'")


class SportsScoresOutput(BaseModel):
    """Output schema for sports_scores plugin."""
    scores: List[Dict[str, Any]] = Field(..., description="List of game scores")
    count: int = Field(..., description="Number of games found")


class SportsScoresPlugin(Plugin):
    """Plugin for getting live sports scores."""

    name = "sports_scores"
    description = "Get live scores for EPL and NBA games"
    input_model = SportsScoresInput
    output_model = SportsScoresOutput

    async def run(self, input_data: SportsScoresInput) -> SportsScoresOutput:
        """Get sports scores for the specified league."""
        try:
            league = input_data.league.upper()
            if league not in ["EPL", "NBA"]:
                raise PluginError(f"Unsupported league: {input_data.league}. Use 'EPL' or 'NBA'")

            scores = await sports_data_manager.get_scores(league)

            # Convert to dict format for LLM
            scores_dict = []
            for score in scores:
                scores_dict.append({
                    "home_team": score.home_team,
                    "away_team": score.away_team,
                    "home_score": score.home_score,
                    "away_score": score.away_score,
                    "status": score.status,
                    "league": score.league,
                    "venue": score.venue,
                    "source": score.api_source
                })

            return SportsScoresOutput(
                scores=scores_dict,
                count=len(scores_dict)
            )

        except Exception as e:
            raise PluginError(f"Failed to get sports scores: {e}")


class PlayerStatsInput(BaseModel):
    """Input schema for player_stats plugin."""
    player_name: str = Field(..., description="Name of the player")
    league: str = Field(..., description="Sports league: 'EPL' or 'NBA'")


class PlayerStatsOutput(BaseModel):
    """Output schema for player_stats plugin."""
    player_info: Optional[Dict[str, Any]] = Field(None, description="Player statistics")
    found: bool = Field(..., description="Whether player was found")


class PlayerStatsPlugin(Plugin):
    """Plugin for getting player statistics."""

    name = "player_stats"
    description = "Get statistics for EPL or NBA players"
    input_model = PlayerStatsInput
    output_model = PlayerStatsOutput

    async def run(self, input_data: PlayerStatsInput) -> PlayerStatsOutput:
        """Get player statistics."""
        try:
            league = input_data.league.upper()
            if league not in ["EPL", "NBA"]:
                raise PluginError(f"Unsupported league: {input_data.league}. Use 'EPL' or 'NBA'")

            stats = await sports_data_manager.get_player_stats(
                input_data.player_name, league
            )

            if stats:
                player_dict = {
                    "name": stats.name,
                    "team": stats.team,
                    "position": stats.position,
                    "league": stats.league,
                    "points": stats.points,
                    "goals": stats.goals,
                    "assists": stats.assists,
                    "rebounds": stats.rebounds,
                    "steals": stats.steals,
                    "blocks": stats.blocks,
                    "games_played": stats.games_played,
                    "minutes_played": stats.minutes_played,
                    "source": stats.api_source
                }
                return PlayerStatsOutput(
                    player_info=player_dict,
                    found=True
                )
            else:
                return PlayerStatsOutput(
                    player_info=None,
                    found=False
                )

        except Exception as e:
            raise PluginError(f"Failed to get player stats: {e}")


class GameDetailsInput(BaseModel):
    """Input schema for game_details plugin."""
    game_id: str = Field(..., description="Unique game identifier")


class GameDetailsOutput(BaseModel):
    """Output schema for game_details plugin."""
    game_info: Optional[Dict[str, Any]] = Field(None, description="Detailed game information")
    found: bool = Field(..., description="Whether game was found")


class GameDetailsPlugin(Plugin):
    """Plugin for getting detailed game information."""

    name = "game_details"
    description = "Get detailed information about a specific game"
    input_model = GameDetailsInput
    output_model = GameDetailsOutput

    async def run(self, input_data: GameDetailsInput) -> GameDetailsOutput:
        """Get detailed game information."""
        try:
            details = await sports_data_manager.get_game_details(input_data.game_id)

            if details:
                game_dict = {
                    "home_team": details.home_team,
                    "away_team": details.away_team,
                    "home_score": details.home_score,
                    "away_score": details.away_score,
                    "status": details.status,
                    "league": details.league,
                    "start_time": details.start_time,
                    "venue": details.venue,
                    "referee": details.referee,
                    "home_stats": details.home_stats,
                    "away_stats": details.away_stats,
                    "source": details.api_source
                }
                return GameDetailsOutput(
                    game_info=game_dict,
                    found=True
                )
            else:
                return GameDetailsOutput(
                    game_info=None,
                    found=False
                )

        except Exception as e:
            raise PluginError(f"Failed to get game details: {e}")


# Export all built-in plugins
__all__ = [
    'ReadFilePlugin',
    'WriteFilePlugin',
    'ListDirectoryPlugin',
    'CalculatorPlugin',
    'SportsScoresPlugin',
    'PlayerStatsPlugin',
    'GameDetailsPlugin',
]
