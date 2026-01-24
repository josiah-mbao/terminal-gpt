"""Sports data providers with unified APIs and caching."""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, Field

from ..infrastructure.logging import get_logger

logger = get_logger("terminal_gpt.sports")


# Unified Data Models
class UnifiedGameScore(BaseModel):
    """Normalized game score across all sports."""
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: str  # "scheduled", "live", "finished", "postponed"
    league: str  # "EPL", "NBA"
    start_time: Optional[str] = None
    venue: Optional[str] = None
    api_source: str  # Track which API provided this data
    last_updated: float = Field(default_factory=time.time)


class UnifiedPlayerStats(BaseModel):
    """Normalized player statistics across leagues."""
    name: str
    team: str
    position: Optional[str] = None
    league: str

    # Scoring stats (normalized across sports)
    points: Optional[Union[int, float]] = None
    goals: Optional[int] = None
    assists: Optional[Union[int, float]] = None

    # Additional stats
    rebounds: Optional[float] = None  # NBA
    steals: Optional[float] = None    # NBA
    blocks: Optional[float] = None    # NBA

    # Game stats
    games_played: Optional[int] = None
    minutes_played: Optional[Union[int, float]] = None

    api_source: str
    last_updated: float = Field(default_factory=time.time)


class UnifiedGameDetails(BaseModel):
    """Normalized game details and box score."""
    home_team: str
    away_team: str
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    status: str
    league: str

    # Game metadata
    start_time: Optional[str] = None
    venue: Optional[str] = None
    referee: Optional[str] = None

    # Detailed stats (when available)
    home_stats: Optional[Dict[str, Any]] = None
    away_stats: Optional[Dict[str, Any]] = None

    api_source: str
    last_updated: float = Field(default_factory=time.time)


# Simple Memory Cache
@dataclass
class CacheEntry:
    """Cache entry with TTL."""
    data: Any
    timestamp: float
    ttl_seconds: int

    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl_seconds


class MemoryCache:
    """Simple in-memory cache with TTL."""

    def __init__(self):
        self._cache: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        """Get cached data if not expired."""
        if key in self._cache:
            entry = self._cache[key]
            if not entry.is_expired():
                return entry.data
            else:
                # Remove expired entry
                del self._cache[key]
        return None

    def set(self, key: str, data: Any, ttl_seconds: int = 300) -> None:
        """Cache data with TTL."""
        self._cache[key] = CacheEntry(data, time.time(), ttl_seconds)

    def clear_expired(self) -> None:
        """Remove all expired entries."""
        expired_keys = [
            key for key, entry in self._cache.items()
            if entry.is_expired()
        ]
        for key in expired_keys:
            del self._cache[key]


# Global cache instance
sports_cache = MemoryCache()


class SportsDataProvider(ABC):
    """Abstract base class for sports data providers."""

    def __init__(self, base_url: str, api_key: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.api_key = api_key
        self._client: Optional[httpx.AsyncClient] = None
        self.name = self.__class__.__name__

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(10.0, read=30.0),
            headers=self._get_headers()
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {
            "User-Agent": "TerminalGPT-Sports/1.0",
            "Accept": "application/json"
        }
        if self.api_key:
            headers["X-Auth-Token"] = self.api_key
        return headers

    @abstractmethod
    async def get_scores(self, league: str) -> List[UnifiedGameScore]:
        """Get current scores for a league."""
        pass

    @abstractmethod
    async def get_player_stats(self, player_name: str, league: str) -> Optional[UnifiedPlayerStats]:
        """Get stats for a specific player."""
        pass

    @abstractmethod
    async def get_game_details(self, game_id: str) -> Optional[UnifiedGameDetails]:
        """Get detailed information for a specific game."""
        pass


class TheSportsDBProvider(SportsDataProvider):
    """TheSportsDB - Free comprehensive sports database."""

    def __init__(self):
        super().__init__("https://www.thesportsdb.com/api/v1/json/3")

    async def get_scores(self, league: str) -> List[UnifiedGameScore]:
        """Get scores from TheSportsDB."""
        if not self._client:
            raise RuntimeError("Provider not initialized")

        try:
            # Map league names to TheSportsDB format
            league_map = {
                "EPL": "English Premier League",
                "NBA": "NBA"
            }

            league_name = league_map.get(league, league)

            # Get live scores
            response = await self._client.get("/events/last.json?l=1")  # Last event per league

            if response.status_code != 200:
                logger.warning(f"TheSportsDB API error: {response.status_code}")
                return []

            data = response.json()
            events = data.get("events", [])

            scores = []
            for event in events:
                if league_name.lower() in event.get("strLeague", "").lower():
                    score = UnifiedGameScore(
                        home_team=event.get("strHomeTeam", ""),
                        away_team=event.get("strAwayTeam", ""),
                        home_score=int(event.get("intHomeScore", 0)) if event.get("intHomeScore") else None,
                        away_score=int(event.get("intAwayScore", 0)) if event.get("intAwayScore") else None,
                        status="finished" if event.get("intHomeScore") is not None else "scheduled",
                        league=league,
                        start_time=event.get("dateEvent"),
                        venue=event.get("strVenue"),
                        api_source="thesportsdb"
                    )
                    scores.append(score)

            return scores

        except Exception as e:
            logger.error(f"TheSportsDB get_scores error: {e}")
            return []

    async def get_player_stats(self, player_name: str, league: str) -> Optional[UnifiedPlayerStats]:
        """Get player stats from TheSportsDB."""
        if not self._client:
            raise RuntimeError("Provider not initialized")

        try:
            # Search for player
            response = await self._client.get(f"https://www.thesportsdb.com/api/v1/json/3/searchplayers.php?p={player_name}")

            if response.status_code != 200:
                return None

            data = response.json()
            players = data.get("player", [])

            if not players:
                return None

            # Take first match (could be improved with better matching)
            player = players[0]

            # Create unified stats (TheSportsDB has limited stats)
            stats = UnifiedPlayerStats(
                name=player.get("strPlayer", ""),
                team=player.get("strTeam", ""),
                position=player.get("strPosition", ""),
                league=league,
                api_source="thesportsdb"
            )

            return stats

        except Exception as e:
            logger.error(f"TheSportsDB get_player_stats error: {e}")
            return None

    async def get_game_details(self, game_id: str) -> Optional[UnifiedGameDetails]:
        """Get game details from TheSportsDB."""
        if not self._client:
            raise RuntimeError("Provider not initialized")

        try:
            response = await self._client.get(f"/lookupevent.php?id={game_id}")

            if response.status_code != 200:
                return None

            data = response.json()
            events = data.get("events", [])

            if not events:
                return None

            event = events[0]

            details = UnifiedGameDetails(
                home_team=event.get("strHomeTeam", ""),
                away_team=event.get("strAwayTeam", ""),
                home_score=int(event.get("intHomeScore", 0)) if event.get("intHomeScore") else None,
                away_score=int(event.get("intAwayScore", 0)) if event.get("intAwayScore") else None,
                status="finished" if event.get("intHomeScore") is not None else "scheduled",
                league=event.get("strLeague", ""),
                start_time=event.get("dateEvent"),
                venue=event.get("strVenue"),
                api_source="thesportsdb"
            )

            return details

        except Exception as e:
            logger.error(f"TheSportsDB get_game_details error: {e}")
            return None


class FootballDataProvider(SportsDataProvider):
    """Football-Data.org - Premier League specialist."""

    def __init__(self, api_key: Optional[str] = None):
        super().__init__("https://api.football-data.org/v4", api_key)

    async def get_scores(self, league: str) -> List[UnifiedGameScore]:
        """Get EPL scores from Football-Data.org."""
        if league != "EPL":
            return []

        if not self._client:
            raise RuntimeError("Provider not initialized")

        try:
            # Get current matchday matches
            response = await self._client.get("/competitions/PL/matches")

            if response.status_code != 200:
                logger.warning(f"Football-Data API error: {response.status_code}")
                return []

            data = response.json()
            matches = data.get("matches", [])

            scores = []
            for match in matches:
                score = UnifiedGameScore(
                    home_team=match["homeTeam"]["name"],
                    away_team=match["awayTeam"]["name"],
                    home_score=match["score"]["fullTime"]["home"] if match["score"]["fullTime"]["home"] is not None else None,
                    away_score=match["score"]["fullTime"]["away"] if match["score"]["fullTime"]["away"] is not None else None,
                    status=match["status"].lower(),
                    league="EPL",
                    start_time=match["utcDate"],
                    venue=match.get("venue"),
                    api_source="football-data"
                )
                scores.append(score)

            return scores

        except Exception as e:
            logger.error(f"Football-Data get_scores error: {e}")
            return []

    async def get_player_stats(self, player_name: str, league: str) -> Optional[UnifiedPlayerStats]:
        """Football-Data player stats - limited free tier."""
        # Free tier has limited player data, so we'll use TheSportsDB as primary
        return None

    async def get_game_details(self, game_id: str) -> Optional[UnifiedGameDetails]:
        """Get game details from Football-Data.org."""
        if not self._client:
            raise RuntimeError("Provider not initialized")

        try:
            response = await self._client.get(f"https://api.football-data.org/v4/matches/{game_id}")

            if response.status_code != 200:
                return None

            match = response.json()

            details = UnifiedGameDetails(
                home_team=match["homeTeam"]["name"],
                away_team=match["awayTeam"]["name"],
                home_score=match["score"]["fullTime"]["home"],
                away_score=match["score"]["fullTime"]["away"],
                status=match["status"].lower(),
                league="EPL",
                start_time=match["utcDate"],
                venue=match.get("venue"),
                api_source="football-data"
            )

            return details

        except Exception as e:
            logger.error(f"Football-Data get_game_details error: {e}")
            return None


class NBAApiProvider(SportsDataProvider):
    """NBA Official API - Free comprehensive NBA data."""

    def __init__(self):
        super().__init__("https://data.nba.net/10s/prod/v1")

    async def get_scores(self, league: str) -> List[UnifiedGameScore]:
        """Get NBA scores from official API."""
        if league != "NBA":
            return []

        if not self._client:
            raise RuntimeError("Provider not initialized")

        try:
            # Get today's scoreboard
            response = await self._client.get("/today.json")

            if response.status_code != 200:
                return []

            today_data = response.json()
            scoreboard_url = today_data.get("links", {}).get("currentScoreboard")

            if not scoreboard_url:
                return []

            # Get actual scores
            response = await self._client.get(scoreboard_url)

            if response.status_code != 200:
                return []

            data = response.json()
            games = data.get("games", [])

            scores = []
            for game in games:
                score = UnifiedGameScore(
                    home_team=game["hTeam"]["fullName"],
                    away_team=game["vTeam"]["fullName"],
                    home_score=int(game["hTeam"]["score"]) if game["hTeam"]["score"] else None,
                    away_score=int(game["vTeam"]["score"]) if game["vTeam"]["score"] else None,
                    status="finished" if game.get("isGameActivated") == False and game["hTeam"]["score"] else "live" if game.get("isGameActivated") else "scheduled",
                    league="NBA",
                    start_time=game.get("startTimeUTC"),
                    venue=game.get("arena", {}).get("name"),
                    api_source="nba-api"
                )
                scores.append(score)

            return scores

        except Exception as e:
            logger.error(f"NBA API get_scores error: {e}")
            return []

    async def get_player_stats(self, player_name: str, league: str) -> Optional[UnifiedPlayerStats]:
        """Get NBA player stats from official API."""
        if league != "NBA":
            return None

        if not self._client:
            raise RuntimeError("Provider not initialized")

        try:
            # Search players
            response = await self._client.get("/players.json")

            if response.status_code != 200:
                return None

            data = response.json()
            players = data.get("league", {}).get("standard", [])

            # Find matching player (simple name matching)
            matching_player = None
            for player in players:
                full_name = f"{player['firstName']} {player['lastName']}".lower()
                if player_name.lower() in full_name:
                    matching_player = player
                    break

            if not matching_player:
                return None

            # Get player stats (would need additional API calls for full stats)
            # For now, return basic player info
            stats = UnifiedPlayerStats(
                name=f"{matching_player['firstName']} {matching_player['lastName']}",
                team=matching_player.get("teamId", "Unknown"),
                position=matching_player.get("pos"),
                league="NBA",
                api_source="nba-api"
            )

            return stats

        except Exception as e:
            logger.error(f"NBA API get_player_stats error: {e}")
            return None

    async def get_game_details(self, game_id: str) -> Optional[UnifiedGameDetails]:
        """Get NBA game details."""
        if not self._client:
            raise RuntimeError("Provider not initialized")

        try:
            # NBA API game details would require additional endpoints
            # For now, return basic info
            return None

        except Exception as e:
            logger.error(f"NBA API get_game_details error: {e}")
            return None


# Provider instances
thesportsdb_provider = TheSportsDBProvider()
football_data_provider = FootballDataProvider()  # No API key needed for basic usage
nba_api_provider = NBAApiProvider()


class SportsDataManager:
    """Unified sports data manager with caching and fallbacks."""

    def __init__(self):
        self.providers = {
            "thesportsdb": thesportsdb_provider,
            "football-data": football_data_provider,
            "nba-api": nba_api_provider
        }

    async def get_scores(self, league: str) -> List[UnifiedGameScore]:
        """Get scores with caching and fallback."""
        cache_key = f"scores_{league}"

        # Try cache first
        cached = sports_cache.get(cache_key)
        if cached:
            return cached

        # Try primary providers
        scores = []

        if league == "EPL":
            async with football_data_provider as provider:
                scores = await provider.get_scores(league)
            if not scores:  # Fallback
                async with thesportsdb_provider as provider:
                    scores = await provider.get_scores(league)
        elif league == "NBA":
            async with nba_api_provider as provider:
                scores = await provider.get_scores(league)
            if not scores:  # Fallback
                async with thesportsdb_provider as provider:
                    scores = await provider.get_scores(league)
        else:
            # Generic fallback
            async with thesportsdb_provider as provider:
                scores = await provider.get_scores(league)

        # Cache results for 5 minutes
        if scores:
            sports_cache.set(cache_key, scores, ttl_seconds=300)

        return scores

    async def get_player_stats(self, player_name: str, league: str) -> Optional[UnifiedPlayerStats]:
        """Get player stats with caching and fallback."""
        cache_key = f"player_{player_name}_{league}"

        # Try cache first
        cached = sports_cache.get(cache_key)
        if cached:
            return cached

        # Try providers in order
        providers_to_try = []

        if league == "NBA":
            providers_to_try = [nba_api_provider, thesportsdb_provider]
        elif league == "EPL":
            providers_to_try = [football_data_provider, thesportsdb_provider]
        else:
            providers_to_try = [thesportsdb_provider]

        for provider in providers_to_try:
            try:
                async with provider:
                    stats = await provider.get_player_stats(player_name, league)
                    if stats:
                        # Cache for 1 hour
                        sports_cache.set(cache_key, stats, ttl_seconds=3600)
                        return stats
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed for player stats: {e}")
                continue

        return None

    async def get_game_details(self, game_id: str) -> Optional[UnifiedGameDetails]:
        """Get game details with caching and fallback."""
        cache_key = f"game_{game_id}"

        # Try cache first
        cached = sports_cache.get(cache_key)
        if cached:
            return cached

        # Try all providers
        for provider in [football_data_provider, nba_api_provider, thesportsdb_provider]:
            try:
                async with provider:
                    details = await provider.get_game_details(game_id)
                    if details:
                        # Cache for 30 minutes
                        sports_cache.set(cache_key, details, ttl_seconds=1800)
                        return details
            except Exception as e:
                logger.warning(f"Provider {provider.name} failed for game details: {e}")
                continue

        return None


# Global instance
sports_data_manager = SportsDataManager()


__all__ = [
    "UnifiedGameScore",
    "UnifiedPlayerStats",
    "UnifiedGameDetails",
    "sports_data_manager",
    "TheSportsDBProvider",
    "FootballDataProvider",
    "NBAApiProvider"
]