"""Inspector Claude - Web UI for exploring Claude Code session data"""

import reflex as rx
from typing import List, Dict, Optional, Set
from datetime import datetime
from pathlib import Path
from inspector_claude.indexer import load_sessions, get_session_summary, Session, load_session_messages, SessionMessage
import rxconfig


# Filter default values - single source of truth
DEFAULT_MIN_MESSAGES = 1
DEFAULT_MAX_MESSAGES = 10000
DEFAULT_MIN_TOKENS = 0
DEFAULT_MAX_TOKENS = 1000000
DEFAULT_MIN_INPUT_TOKENS = 0
DEFAULT_MAX_INPUT_TOKENS = 1000000
DEFAULT_MIN_OUTPUT_TOKENS = 0
DEFAULT_MAX_OUTPUT_TOKENS = 1000000

# Mapping of filter attribute names to their default values
FILTER_DEFAULTS = {
    'min_messages': DEFAULT_MIN_MESSAGES,
    'max_messages': DEFAULT_MAX_MESSAGES,
    'min_tokens': DEFAULT_MIN_TOKENS,
    'max_tokens': DEFAULT_MAX_TOKENS,
    'min_input_tokens': DEFAULT_MIN_INPUT_TOKENS,
    'max_input_tokens': DEFAULT_MAX_INPUT_TOKENS,
    'min_output_tokens': DEFAULT_MIN_OUTPUT_TOKENS,
    'max_output_tokens': DEFAULT_MAX_OUTPUT_TOKENS,
}

# Color scheme constants
COLORS = {
    # Selected session highlighting
    'selected_session_bg': '#d4e3ff',
    'selected_session_border': '#5b8def',
    # Content block colors
    'thinking_bg': '#f5f3ff',
    'thinking_border': '#e9d5ff',
    'tool_use_bg': '#f0fdf4',
    'tool_use_border': '#bbf7d0',
    'tool_result_bg': '#ecfeff',
    'tool_result_border': '#a5f3fc',
    'file_history_bg': '#fff7ed',
    'file_history_border': '#fdba74',
    'unknown_bg': '#f9fafb',
    'unknown_border': '#d1d5db',
    'session_summary_bg': '#eff6ff',
    'session_summary_border': '#bfdbfe',
    'user_message_bg': '#fef08a',
}


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
    min_messages: int = DEFAULT_MIN_MESSAGES
    max_messages: int = DEFAULT_MAX_MESSAGES
    min_tokens: int = DEFAULT_MIN_TOKENS
    max_tokens: int = DEFAULT_MAX_TOKENS
    min_input_tokens: int = DEFAULT_MIN_INPUT_TOKENS
    max_input_tokens: int = DEFAULT_MAX_INPUT_TOKENS
    min_output_tokens: int = DEFAULT_MIN_OUTPUT_TOKENS
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS
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


def session_card(session: SessionSummary) -> rx.Component:
    """Render a session summary card"""
    return rx.card(
        rx.vstack(
            rx.heading(
                session.description,
                size="4"
            ),
            rx.text(f"ID: {session.session_id}", size="1", color="gray"),
            rx.text(f"Project: {session.project_path}", size="2"),
            rx.text(f"Branch: {session.git_branch}", size="2"),
            rx.hstack(
                rx.badge(f"{session.message_count} messages", color_scheme="blue"),
                rx.badge(f"{session.total_tokens} total tokens", color_scheme="green"),
            ),
            rx.hstack(
                rx.badge(f"{session.input_tokens} in", color_scheme="cyan"),
                rx.badge(f"{session.output_tokens} out", color_scheme="orange"),
            ),
            rx.text(
                f"Started: {session.start_time}",
                size="1",
                color="gray"
            ),
            align_items="start",
            spacing="2",
            width="100%"
        ),
        width="100%",
        on_click=lambda: State.select_session(session.session_id),
        style=rx.cond(
            State.selected_session_id == session.session_id,
            {"background_color": COLORS['selected_session_bg'], "cursor": "pointer", "border": f"2px solid {COLORS['selected_session_border']}"},
            {"cursor": "pointer", "border": "2px solid transparent"}
        )
    )


def styled_content_block(
    badge_text: str,
    badge_color: str,
    content: rx.Component,
    background_color: str,
    border_color: str,
    header_extras: Optional[rx.Component] = None
) -> rx.Component:
    """Create a styled content block with consistent styling

    Args:
        badge_text: Text to display in the badge
        badge_color: Color scheme for the badge
        content: The content component to display
        background_color: Background color for the block
        border_color: Border color for the block
        header_extras: Optional additional components for the header (e.g., buttons)
    """
    return rx.box(
        rx.vstack(
            rx.hstack(
                rx.badge(badge_text, color_scheme=badge_color, size="1"),
                header_extras if header_extras else rx.box(),
                width="100%",
                align_items="center"
            ),
            rx.box(
                content,
                width="100%",
                max_width="100%",
                overflow_x="auto"
            ),
            spacing="2",
            align_items="start",
            width="100%"
        ),
        padding="12px",
        border_radius="6px",
        background_color=background_color,
        border=f"1px solid {border_color}",
        width="100%",
        max_width="100%"
    )


def render_text_block(block: Dict) -> rx.Component:
    """Render a text content block"""
    return rx.box(
        rx.text(block["text"], size="2", white_space="pre-wrap"),
        padding="8px",
        border_radius="4px"
    )


def render_thinking_block(block: Dict) -> rx.Component:
    """Render a thinking content block"""
    content = rx.text(
        block["thinking"],
        size="2",
        white_space="pre-wrap",
        color="#666"
    )
    return styled_content_block(
        badge_text="Thinking",
        badge_color="purple",
        content=content,
        background_color=COLORS['thinking_bg'],
        border_color=COLORS['thinking_border']
    )


def render_tool_use_block(block: Dict) -> rx.Component:
    """Render a tool_use content block"""
    header_extras = rx.text("ID: ", block["id_short"], "...", size="1", color="gray")
    content = rx.text(
        block["input"],
        size="2",
        white_space="pre-wrap",
        word_break="break-word",
        font_family="monospace"
    )
    return styled_content_block(
        badge_text=f"Tool: {block['name']}",
        badge_color="green",
        content=content,
        background_color=COLORS['tool_use_bg'],
        border_color=COLORS['tool_use_border'],
        header_extras=header_extras
    )


def render_tool_result_block(block: Dict) -> rx.Component:
    """Render a tool_result content block with expand/collapse functionality"""
    tool_use_id = block["tool_use_id"]
    content = block["content"]
    content_preview = block["content_preview"]
    is_long = block["is_long"]
    is_expanded = State.expanded_tool_results.contains(tool_use_id)

    # Build header with ID and optional expand/collapse button
    header_extras = rx.hstack(
        rx.text("For: ", block["tool_use_id_short"], "...", size="1", color="gray"),
        rx.spacer(),
        rx.cond(
            is_long,
            rx.button(
                rx.cond(is_expanded, "Show less", "Show more"),
                on_click=lambda: State.toggle_tool_result_expansion(tool_use_id),
                size="1",
                variant="soft",
                color_scheme="cyan"
            ),
            rx.box()
        )
    )

    # Content with conditional display
    content_component = rx.cond(
        is_expanded | ~is_long,
        rx.text(
            content,
            size="2",
            white_space="pre-wrap",
            word_break="break-word",
            font_family="monospace"
        ),
        rx.text(
            content_preview,
            size="2",
            white_space="pre-wrap",
            word_break="break-word",
            font_family="monospace",
            color="#555"
        )
    )

    return styled_content_block(
        badge_text="Tool Result",
        badge_color="cyan",
        content=content_component,
        background_color=COLORS['tool_result_bg'],
        border_color=COLORS['tool_result_border'],
        header_extras=header_extras
    )


def render_file_history_block(block: Dict) -> rx.Component:
    """Render a file-history-snapshot content block"""
    # File history blocks typically contain file content or file metadata
    raw_content = block.get("content", "")
    content = rx.text(
        raw_content if isinstance(raw_content, str) else str(raw_content),
        size="2",
        white_space="pre-wrap",
        word_break="break-word",
        font_family="monospace"
    )
    return styled_content_block(
        badge_text="File History Snapshot",
        badge_color="orange",
        content=content,
        background_color=COLORS['file_history_bg'],
        border_color=COLORS['file_history_border']
    )


def render_image_block(block: Dict) -> rx.Component:
    """Render an image content block"""
    # Image source data is flattened by the indexer into top-level fields:
    # - source_type: "base64" or "url"
    # - source_media_type: MIME type (e.g., "image/png")
    # - source_data: base64 encoded data
    # - source_url: URL for url-type images

    # Use conditional rendering based on source type
    content = rx.cond(
        block["source_type"] == "base64",
        # Base64 image
        rx.image(
            src=f"data:{block['source_media_type']};base64,{block['source_data']}",
            alt="Content image",
            max_width="100%",
            max_height="600px",
            object_fit="contain",
            border_radius="4px"
        ),
        rx.cond(
            block["source_type"] == "url",
            # URL image
            rx.image(
                src=block["source_url"],
                alt="Content image",
                max_width="100%",
                max_height="600px",
                object_fit="contain",
                border_radius="4px"
            ),
            # Fallback for unknown source type
            rx.text(
                f"[Image - unsupported source type]",
                size="2",
                color="#999",
                font_style="italic"
            )
        )
    )

    return styled_content_block(
        badge_text="Image",
        badge_color="violet",
        content=content,
        background_color="#faf5ff",
        border_color="#e9d5ff"
    )


def render_unknown_block(block: Dict) -> rx.Component:
    """Render an unknown content block type with generic styling"""
    block_type = block.get("type", "unknown")
    raw_content = block.get("content", "")

    # Convert content to string if it's not already
    if not isinstance(raw_content, str):
        raw_content = str(raw_content)

    content = rx.text(
        raw_content,
        size="2",
        white_space="pre-wrap",
        word_break="break-word"
    )

    return styled_content_block(
        badge_text=f"Unknown Type: {block_type}",
        badge_color="gray",
        content=content,
        background_color=COLORS['unknown_bg'],
        border_color=COLORS['unknown_border']
    )


def render_content_block(block: Dict) -> rx.Component:
    """Render a single content block based on its type"""
    # Check each type and render accordingly
    return rx.cond(
        block["type"] == "text",
        render_text_block(block),
        rx.cond(
            block["type"] == "thinking",
            render_thinking_block(block),
            rx.cond(
                block["type"] == "tool_use",
                render_tool_use_block(block),
                rx.cond(
                    block["type"] == "tool_result",
                    render_tool_result_block(block),
                    rx.cond(
                        block["type"] == "file-history-snapshot",
                        render_file_history_block(block),
                        rx.cond(
                            block["type"] == "image",
                            render_image_block(block),
                            # Unknown block type
                            rx.box()
                        )
                    )
                )
            )
        )
    )


def render_message_content(msg) -> rx.Component:
    """Render message content - either structured blocks or legacy text"""
    # Use rx.cond to handle conditional rendering (Reflex doesn't allow if statements on Vars)
    return rx.cond(
        msg.content_blocks.length() > 0,
        # If we have content_blocks, render them
        rx.vstack(
            rx.foreach(
                msg.content_blocks,
                render_content_block
            ),
            spacing="3",
            width="100%",
            align_items="start"
        ),
        # Otherwise fall back to plain content or show "(no content)"
        rx.cond(
            msg.content,
            rx.text(msg.content, size="2", white_space="pre-wrap"),
            rx.text("(no content)", size="2", color="gray", font_style="italic")
        )
    )


def session_detail() -> rx.Component:
    """Render detailed view of selected session"""
    return rx.cond(
        State.selected_session_id,
        # Show session details when selected
        rx.vstack(
            # Show summary if available
            rx.cond(
                State.selected_session.summary,
                rx.box(
                    rx.vstack(
                        rx.badge("Session Summary", color_scheme="blue", size="2"),
                        rx.text(State.selected_session.summary, size="2", color="#555"),
                        spacing="2",
                        align_items="start"
                    ),
                    padding="12px",
                    border_radius="6px",
                    background_color=COLORS['session_summary_bg'],
                    border=f"1px solid {COLORS['session_summary_border']}",
                    width="100%",
                    margin_top="10px",
                    margin_bottom="10px"
                ),
                rx.box()
            ),
            rx.divider(),
            rx.hstack(
                rx.heading("Messages", size="4"),
                rx.spacer(),
                rx.button(
                    "Refresh",
                    on_click=State.refresh_session,
                    size="2",
                    variant="soft",
                    color_scheme="green",
                    disabled=~State.session_file_updated
                ),
                rx.button(
                    "First",
                    on_click=State.first_page,
                    size="2",
                    disabled=State.current_page == 1
                ),
                rx.button(
                    "Previous",
                    on_click=State.prev_page,
                    size="2",
                    disabled=State.current_page == 1
                ),
                rx.text(
                    f"Page {State.current_page} of {State.total_pages}",
                    size="2",
                    color="gray"
                ),
                rx.button(
                    "Next",
                    on_click=State.next_page,
                    size="2",
                    disabled=State.current_page >= State.total_pages
                ),
                rx.button(
                    "Last",
                    on_click=State.last_page,
                    size="2",
                    disabled=State.current_page >= State.total_pages
                ),
                width="100%",
                align_items="center"
            ),
            rx.box(
                rx.foreach(
                    State.paginated_messages,
                    lambda msg: rx.card(
                        rx.vstack(
                            rx.hstack(
                                rx.badge(
                                    rx.cond(
                                        msg.type == "user",
                                        "👤 user",
                                        msg.type
                                    ),
                                    color_scheme="blue"
                                ),
                                rx.text(msg.timestamp, size="1", color="gray"),
                            ),
                            render_message_content(msg),
                            rx.cond(
                                msg.tokens_output > 0,
                                rx.text(
                                    f"Tokens: {msg.tokens_input} in, {msg.tokens_output} out",
                                    size="1",
                                    color="green"
                                ),
                                rx.box()
                            ),
                            spacing="2",
                            align_items="start"
                        ),
                        width="100%",
                        background_color=rx.cond(
                            msg.type == "user",
                            COLORS['user_message_bg'],
                            "white"  # Default white for other messages
                        )
                    )
                ),
                width="100%",
                max_height="calc(100vh - 200px)",
                overflow_y="auto"
            ),
            spacing="3",
            align_items="start",
            width="100%",
            height="100%"
        ),
        # Show placeholder when no session is selected
        rx.vstack(
            rx.heading("No Session Selected", size="6", color="gray"),
            rx.text(
                "Select a session from the list to view details",
                size="3",
                color="gray"
            ),
            spacing="3",
            align_items="center",
            justify_content="center",
            height="400px"
        )
    )


def range_filter_input(label: str, min_filter_name: str, max_filter_name: str) -> rx.Component:
    """Create a range filter input with min/max fields

    Args:
        label: Display label for the filter (e.g., "Msgs", "In", "Out")
        min_filter_name: State attribute name for minimum value (e.g., "min_messages")
        max_filter_name: State attribute name for maximum value (e.g., "max_messages")
    """
    return rx.hstack(
        rx.text(label, weight="bold", size="2", min_width="50px"),
        rx.input(
            placeholder="Min",
            type="number",
            value=getattr(State, min_filter_name),
            on_change=lambda v: State.set_numeric_filter(min_filter_name, v),
            width="60px"
        ),
        rx.text("to", size="1"),
        rx.input(
            placeholder="Max",
            type="number",
            value=getattr(State, max_filter_name),
            on_change=lambda v: State.set_numeric_filter(max_filter_name, v),
            width="60px"
        ),
        spacing="2",
        align_items="center",
        width="100%"
    )


def left_sidebar() -> rx.Component:
    """Render the left sidebar with filters and session list"""
    return rx.vstack(
        rx.heading("🔍 Inspector Claude", size="7", font_style="italic"),

        # Collapsible filters section
        rx.vstack(
            # Filter header with toggle and reset buttons
            rx.hstack(
                rx.button(
                    rx.cond(
                        State.filters_expanded,
                        f"Hide Filters ({State.active_filter_count})",
                        f"Show Filters ({State.active_filter_count})"
                    ),
                    on_click=State.toggle_filters,
                    size="2",
                    flex="1"
                ),
                rx.button(
                    "Reset",
                    on_click=State.reset_filters,
                    size="2",
                    variant="soft",
                    color_scheme="gray"
                ),
                spacing="2",
                width="100%"
            ),

            # Filter controls (only shown when expanded)
            rx.cond(
                State.filters_expanded,
                rx.vstack(
                    # Message Count filter
                    range_filter_input("Msgs", "min_messages", "max_messages"),
                    # Input Tokens filter
                    range_filter_input("In", "min_input_tokens", "max_input_tokens"),
                    # Output Tokens filter
                    range_filter_input("Out", "min_output_tokens", "max_output_tokens"),
                    # Git Branch filter
                    rx.hstack(
                        rx.text("Branch", weight="bold", size="2", min_width="50px"),
                        rx.input(
                            placeholder="Filter by branch",
                            value=State.branch_filter,
                            on_change=State.set_branch_filter,
                            flex="1"
                        ),
                        spacing="2",
                        align_items="center",
                        width="100%"
                    ),
                    # Time Range filter
                    rx.hstack(
                        rx.text("Time", weight="bold", size="2", min_width="50px"),
                        rx.input(
                            placeholder="From",
                            type="date",
                            value=State.start_date_filter,
                            on_change=State.set_start_date_filter,
                            width="120px"
                        ),
                        rx.text("to", size="1"),
                        rx.input(
                            placeholder="To",
                            type="date",
                            value=State.end_date_filter,
                            on_change=State.set_end_date_filter,
                            width="120px"
                        ),
                        spacing="2",
                        align_items="center",
                        width="100%"
                    ),
                    spacing="2",
                    align_items="start",
                    padding="10px",
                    background_color="rgba(0,0,0,0.02)",
                    border_radius="8px",
                    width="100%"
                ),
                rx.box()  # Empty box when collapsed
            ),
            spacing="2",
            width="100%"
        ),

        # Session list
        rx.box(
            rx.foreach(
                State.filtered_sessions,
                session_card
            ),
            width="100%",
            max_height=rx.cond(
                State.filters_expanded,
                "calc(100vh - 420px)",
                "calc(100vh - 200px)"
            ),
            overflow_y="auto",
            padding="5px"
        ),

        spacing="3",
        align_items="start",
        width="400px",
        height="100vh",
        padding="20px 20px 5px 20px",
        overflow_y="auto"
    )


def index() -> rx.Component:
    """Main page"""
    return rx.hstack(
        # Left sidebar
        left_sidebar(),

        # Right detail panel
        rx.box(
            session_detail(),
            flex="1",
            padding="20px 20px 5px 20px",
            overflow_y="auto",
            height="100vh"
        ),

        spacing="0",
        width="100%",
        height="100vh",
        align_items="stretch"
    )


# Create the app
app = rx.App()
app.add_page(index, on_load=State.load_data)
