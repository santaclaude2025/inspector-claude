"""Module-level cache for session data to reduce state serialization"""

from typing import Dict, Set, Optional
from datetime import datetime
from inspector_claude.indexer import Session

# Module-level cache (shared across all state instances)
# These variables are NOT part of State, so they don't get serialized to frontend
_session_cache: Dict[str, Session] = {}
_loaded_sessions: Set[str] = set()
_session_load_times: Dict[str, datetime] = {}
_file_mtimes: Dict[str, float] = {}


def get_session(session_id: str) -> Optional[Session]:
    """Get session from cache"""
    return _session_cache.get(session_id)


def store_session_metadata(session_id: str, session: Session) -> None:
    """Store session in cache WITHOUT messages (metadata only)"""
    _session_cache[session_id] = session
    # Do NOT add to _loaded_sessions - messages not loaded yet!


def cache_session(session_id: str, session: Session, load_time: datetime) -> None:
    """Store session in cache with messages loaded"""
    _session_cache[session_id] = session
    _loaded_sessions.add(session_id)
    _session_load_times[session_id] = load_time


def is_session_loaded(session_id: str) -> bool:
    """Check if session messages are loaded in cache"""
    return session_id in _loaded_sessions


def get_load_time(session_id: str) -> Optional[datetime]:
    """Get when session messages were loaded"""
    return _session_load_times.get(session_id)


def cache_file_mtime(session_id: str, mtime: float) -> None:
    """Cache file modification time to avoid repeated stat() calls"""
    _file_mtimes[session_id] = mtime


def get_cached_mtime(session_id: str) -> Optional[float]:
    """Get cached file modification time"""
    return _file_mtimes.get(session_id)


def clear_cache() -> None:
    """Clear all cached data"""
    _session_cache.clear()
    _loaded_sessions.clear()
    _session_load_times.clear()
    _file_mtimes.clear()


def get_cache_stats() -> dict:
    """Get cache statistics for debugging"""
    total_messages = sum(
        len(s.messages) if s.messages else 0
        for s in _session_cache.values()
    )

    return {
        'sessions_cached': len(_session_cache),
        'sessions_with_messages': len(_loaded_sessions),
        'total_messages_in_cache': total_messages,
        'memory_estimate_mb': total_messages * 2 / 1024  # Rough: 2KB per message
    }
