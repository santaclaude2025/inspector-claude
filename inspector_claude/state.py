"""Application state management for Inspector Claude"""

import reflex as rx
from typing import List, Dict, Optional, Set
from datetime import datetime
from pathlib import Path
from inspector_claude.indexer import load_sessions, load_session_messages, Session, SessionMessage
from inspector_claude.config import FILTER_DEFAULTS
import rxconfig


class SessionSummary(rx.Base):
    """Summary of a session for display"""
    session_id: str
    description: str
    project_path: str
    git_branch: str
    message_count: int
    total_tokens: int
    input_tokens: int
    output_tokens: int
    start_time: str


class State(rx.State):
    """Application state"""

    # All sessions loaded at startup
    all_sessions: Dict[str, Session] = {}

    # Track which sessions have had messages loaded
    loaded_message_sessions: Set[str] = set()

    # Track when each session's messages were loaded
    session_load_times: Dict[str, datetime] = {}

    # Filtered sessions for display
    filtered_sessions: List[SessionSummary] = []

    # Filter values
    min_messages: int = FILTER_DEFAULTS['min_messages']
    max_messages: int = FILTER_DEFAULTS['max_messages']
    min_tokens: int = FILTER_DEFAULTS['min_tokens']
    max_tokens: int = FILTER_DEFAULTS['max_tokens']
    min_input_tokens: int = FILTER_DEFAULTS['min_input_tokens']
    max_input_tokens: int = FILTER_DEFAULTS['max_input_tokens']
    min_output_tokens: int = FILTER_DEFAULTS['min_output_tokens']
    max_output_tokens: int = FILTER_DEFAULTS['max_output_tokens']
    branch_filter: str = ""
    start_date_filter: str = ""  # ISO date string (YYYY-MM-DD)
    end_date_filter: str = ""    # ISO date string (YYYY-MM-DD)

    # Selected session for detail view
    selected_session_id: Optional[str] = None

    # Pagination state
    current_page: int = 1
    page_size: int = 20

    # Filter panel state
    filters_expanded: bool = False

    # Tool result expansion state (tracks which tool results are expanded by tool_use_id)
    expanded_tool_results: Set[str] = set()

    def toggle_tool_result_expansion(self, tool_use_id: str):
        """Toggle expansion of a tool result"""
        if tool_use_id in self.expanded_tool_results:
            self.expanded_tool_results.discard(tool_use_id)
        else:
            self.expanded_tool_results.add(tool_use_id)

    def toggle_filters(self):
        """Toggle filter panel visibility"""
        self.filters_expanded = not self.filters_expanded

    def reset_filters(self):
        """Reset all filters to their default values"""
        # Reset numeric filters using FILTER_DEFAULTS dictionary
        for attr_name, default_value in FILTER_DEFAULTS.items():
            setattr(self, attr_name, default_value)
        # Reset string filters
        self.branch_filter = ""
        self.start_date_filter = ""
        self.end_date_filter = ""
        self.apply_filters()

    @rx.var
    def active_filter_count(self) -> int:
        """Count how many filters are currently active (different from defaults)"""
        count = 0

        # Check range filter pairs (each pair counts as 1 filter if either value differs from default)
        filter_pairs = [
            ('min_messages', 'max_messages'),
            ('min_tokens', 'max_tokens'),
            ('min_input_tokens', 'max_input_tokens'),
            ('min_output_tokens', 'max_output_tokens'),
        ]

        for min_name, max_name in filter_pairs:
            if (getattr(self, min_name) != FILTER_DEFAULTS[min_name] or
                getattr(self, max_name) != FILTER_DEFAULTS[max_name]):
                count += 1

        # Branch filter
        if self.branch_filter:
            count += 1

        # Time Range filter (count as 1 if either start or end date is set)
        if self.start_date_filter or self.end_date_filter:
            count += 1

        return count

    def load_data(self):
        """Load all sessions from configured claude_dir (metadata only, not messages)"""
        print(f"Loading session metadata from {rxconfig.claude_dir}...")
        self.all_sessions = load_sessions(claude_dir=rxconfig.claude_dir, load_messages=False)
        print(f"Loaded {len(self.all_sessions)} sessions")
        self.apply_filters()

    def apply_filters(self):
        """Apply current filters to sessions"""
        filtered = []

        for session_id, session in self.all_sessions.items():
            # Apply message count filter
            if session.message_count < self.min_messages or session.message_count > self.max_messages:
                continue

            # Apply token count filter
            if session.total_tokens < self.min_tokens or session.total_tokens > self.max_tokens:
                continue

            # Apply input token filter
            if session.total_input_tokens < self.min_input_tokens or session.total_input_tokens > self.max_input_tokens:
                continue

            # Apply output token filter
            if session.total_output_tokens < self.min_output_tokens or session.total_output_tokens > self.max_output_tokens:
                continue

            # Apply branch filter
            if self.branch_filter and self.branch_filter.lower() not in (session.git_branch or "").lower():
                continue

            # Apply date range filter (based on start_time)
            if session.start_time:
                session_date = session.start_time.date().isoformat()

                # Check start date
                if self.start_date_filter and session_date < self.start_date_filter:
                    continue

                # Check end date
                if self.end_date_filter and session_date > self.end_date_filter:
                    continue

            summary = SessionSummary(
                session_id=session_id,
                description=session.description,
                project_path=session.project_path,
                git_branch=session.git_branch or "unknown",
                message_count=session.message_count,
                total_tokens=session.total_tokens,
                input_tokens=session.total_input_tokens,
                output_tokens=session.total_output_tokens,
                start_time=session.start_time.isoformat() if session.start_time else "N/A"
            )
            filtered.append(summary)

        # Sort by start time, most recent first
        filtered.sort(key=lambda s: s.start_time, reverse=True)
        self.filtered_sessions = filtered

    def set_numeric_filter(self, filter_name: str, value: str):
        """Generic method to update any numeric filter

        Args:
            filter_name: Name of the filter attribute (e.g., 'min_messages', 'max_tokens')
            value: String value from input field
        """
        try:
            # Get default value for this filter
            default_value = FILTER_DEFAULTS.get(filter_name, 0)
            # Parse and set the value, using default if empty
            numeric_value = int(value) if value else default_value
            setattr(self, filter_name, numeric_value)
            self.apply_filters()
        except ValueError:
            # Invalid input, ignore
            pass

    def set_branch_filter(self, value: str):
        """Update branch name filter"""
        self.branch_filter = value
        self.apply_filters()

    def set_start_date_filter(self, value: str):
        """Update start date filter"""
        self.start_date_filter = value
        self.apply_filters()

    def set_end_date_filter(self, value: str):
        """Update end date filter"""
        self.end_date_filter = value
        self.apply_filters()

    def select_session(self, session_id: str):
        """Select a session for detail view and load its messages if needed"""
        self.selected_session_id = session_id
        self.current_page = 1  # Reset to first page when selecting a new session
        self.expanded_tool_results = set()  # Clear expanded tool results

        # Load messages for this session if not already loaded
        if session_id not in self.loaded_message_sessions:
            session = self.all_sessions.get(session_id)
            if session:
                print(f"Loading messages for session {session_id}...")
                messages = load_session_messages(session_id, session.project_dir, claude_dir=rxconfig.claude_dir)
                session.messages = messages
                self.loaded_message_sessions.add(session_id)
                self.session_load_times[session_id] = datetime.now()
                print(f"Loaded {len(messages)} messages")

    def next_page(self):
        """Go to next page of messages"""
        if self.current_page < self.total_pages:
            self.current_page += 1

    def prev_page(self):
        """Go to previous page of messages"""
        if self.current_page > 1:
            self.current_page -= 1

    def first_page(self):
        """Go to first page of messages"""
        self.current_page = 1

    def last_page(self):
        """Go to last page of messages"""
        self.current_page = self.total_pages

    def clear_selection(self):
        """Clear selected session"""
        self.selected_session_id = None

    def refresh_session(self):
        """Refresh the current session by re-reading messages from disk"""
        if self.selected_session_id:
            session = self.all_sessions.get(self.selected_session_id)
            if session:
                print(f"Refreshing messages for session {self.selected_session_id}...")
                messages = load_session_messages(self.selected_session_id, session.project_dir, claude_dir=rxconfig.claude_dir)
                session.messages = messages
                # Ensure session is marked as loaded
                self.loaded_message_sessions.add(self.selected_session_id)
                self.session_load_times[self.selected_session_id] = datetime.now()
                print(f"Refreshed {len(messages)} messages")
                # Reset to first page
                self.current_page = 1
                # Clear expanded tool results
                self.expanded_tool_results = set()

    @rx.var
    def selected_session(self) -> Optional[Session]:
        """Get the currently selected session"""
        if self.selected_session_id:
            return self.all_sessions.get(self.selected_session_id)
        return None

    @rx.var
    def session_file_updated(self) -> bool:
        """Check if the current session file has been modified since last load"""
        if not self.selected_session_id:
            return False

        # Check if we have a load time for this session
        load_time = self.session_load_times.get(self.selected_session_id)
        if not load_time:
            return False

        # Get the session file path
        session = self.all_sessions.get(self.selected_session_id)
        if not session:
            return False

        session_file = rxconfig.claude_dir / "projects" / session.project_dir / f"{self.selected_session_id}.jsonl"

        # Check if file exists and get its modification time
        if session_file.exists():
            file_mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
            return file_mtime > load_time

        return False

    @rx.var
    def total_pages(self) -> int:
        """Get total number of pages for current session"""
        session = self.selected_session
        if session and session.messages:
            return (len(session.messages) + self.page_size - 1) // self.page_size
        return 1

    @rx.var
    def paginated_messages(self) -> List[SessionMessage]:
        """Get messages for the current page"""
        session = self.selected_session
        if session and session.messages:
            start_idx = (self.current_page - 1) * self.page_size
            end_idx = start_idx + self.page_size
            return session.messages[start_idx:end_idx]
        return []
