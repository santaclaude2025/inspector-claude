"""UI components for Inspector Claude"""

import reflex as rx
from typing import Optional, Dict
from inspector_claude.state import State, SessionSummary
from inspector_claude.config import COLORS


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


def render_agent_invocation_block(block: Dict, agent_metadata) -> rx.Component:
    """Render a Task tool_use block with agent information

    Shows agent ID, status, summary, and button to open agent history
    """
    from inspector_claude.state import State

    # Format duration in seconds (using rx.cond instead of if)
    duration_sec = rx.cond(
        agent_metadata.total_duration_ms,
        agent_metadata.total_duration_ms / 1000,
        0
    )

    # Build status indicator (using rx.cond)
    status_icon = rx.cond(agent_metadata.status == "completed", "✓", "✗")
    status_color = rx.cond(agent_metadata.status == "completed", "green", "red")

    header_extras = rx.hstack(
        rx.text(
            "Agent: " + agent_metadata.agent_id,
            size="1",
            color="gray"
        ),
        rx.badge(
            status_icon + " " + agent_metadata.status,
            color_scheme=status_color,
            size="1"
        ),
        spacing="2"
    )

    content = rx.vstack(
        # Task prompt
        rx.vstack(
            rx.text("Task:", size="1", weight="bold", color="#555"),
            rx.text(
                agent_metadata.prompt,
                size="2",
                white_space="pre-wrap",
                color="#333"
            ),
            spacing="1",
            align_items="start",
            width="100%"
        ),

        # Summary
        rx.cond(
            agent_metadata.summary != "",
            rx.vstack(
                rx.text("Summary:", size="1", weight="bold", color="#555"),
                rx.text(
                    agent_metadata.summary,
                    size="2",
                    white_space="pre-wrap",
                    color="#333"
                ),
                spacing="1",
                align_items="start",
                width="100%"
            ),
            rx.box()
        ),

        # Stats and button
        rx.hstack(
            rx.badge(
                "📊 " + agent_metadata.total_tokens.to(str) + " tokens",
                color_scheme="cyan",
                size="1"
            ),
            rx.badge(
                "⏱️ " + duration_sec.to(str) + "s",
                color_scheme="orange",
                size="1"
            ),
            rx.spacer(),
            rx.button(
                "Open Agent History ➜",
                on_click=lambda: State.open_agent_session(agent_metadata.agent_id),
                size="2",
                variant="solid",
                color_scheme="blue"
            ),
            spacing="2",
            align_items="center",
            width="100%"
        ),

        spacing="3",
        align_items="start",
        width="100%"
    )

    return styled_content_block(
        badge_text="🤖 Tool: Task",
        badge_color="blue",
        content=content,
        background_color="#eff6ff",
        border_color="#93c5fd",
        header_extras=header_extras
    )


def agent_view_header() -> rx.Component:
    """Header shown when viewing an agent side-chain"""
    from inspector_claude.state import State

    return rx.box(
        rx.hstack(
            rx.button(
                "🔙 Back to Parent",
                on_click=State.close_agent_session,
                size="2",
                variant="soft",
                color_scheme="gray"
            ),
            rx.badge(
                f"🤖 Agent Side-Chain: {State.viewing_agent_id}",
                color_scheme="blue",
                size="2"
            ),
            spacing="3",
            align_items="center",
            width="100%"
        ),
        padding="12px",
        border_radius="6px",
        background_color="#eff6ff",
        border="2px solid #93c5fd",
        width="100%",
        margin_bottom="10px"
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


def render_agent_card_if_present(msg) -> rx.Component:
    """Render agent invocation card if message has agent metadata"""
    return rx.cond(
        msg.agent_metadata,
        # Render agent card with a placeholder block (agent metadata has all info we need)
        render_agent_invocation_block({}, msg.agent_metadata),
        rx.box()  # No agent metadata, render nothing
    )


def render_message_content_blocks(msg) -> rx.Component:
    """Render content blocks for a message"""
    # Simply render all content blocks normally
    return rx.vstack(
        rx.foreach(
            msg.content_blocks,
            render_content_block
        ),
        spacing="3",
        width="100%",
        align_items="start"
    )


def render_message_content(msg) -> rx.Component:
    """Render message content - either structured blocks or legacy text"""
    # Use rx.cond to handle conditional rendering (Reflex doesn't allow if statements on Vars)
    return rx.cond(
        msg.content_blocks.length() > 0,
        # If we have content_blocks, render agent card first (if present) then blocks
        rx.vstack(
            render_agent_card_if_present(msg),
            render_message_content_blocks(msg),
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
            # Show agent header if viewing agent, otherwise show session summary
            rx.cond(
                State.is_viewing_agent,
                # Agent header
                agent_view_header(),
                # Session summary (normal mode)
                rx.cond(
                    State.selected_session_summary,
                    rx.box(
                        rx.vstack(
                            rx.badge("Session Summary", color_scheme="blue", size="2"),
                            rx.text(State.selected_session_summary, size="2", color="#555"),
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
                )
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
