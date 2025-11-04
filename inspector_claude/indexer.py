"""Index and load Claude Code session data from ~/.claude"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime

# Constants for session description
MAX_DESCRIPTION_LENGTH = 100
TRUNCATION_SUFFIX = "..."
CONTENT_PREVIEW_LENGTH = 300  # Used for tool result previews


def normalize_content_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a content block by converting complex objects to strings for UI display"""
    normalized = block.copy()
    block_type = block.get('type')

    # Convert tool_use input to JSON string for display and truncate ID
    if block_type == 'tool_use':
        if 'input' in normalized and isinstance(normalized['input'], dict):
            normalized['input'] = json.dumps(normalized['input'], indent=2)
        # Truncate ID for display
        if 'id' in normalized:
            normalized['id_short'] = str(normalized['id'])[:8]

    # Convert tool_result content to string if it's a list and truncate tool_use_id
    if block_type == 'tool_result':
        if 'content' in normalized:
            content = normalized['content']
            if isinstance(content, list):
                # Tool result content can be a list of text blocks
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get('type') == 'text':
                        text_parts.append(item.get('text', ''))
                    else:
                        text_parts.append(str(item))
                normalized['content'] = '\n'.join(text_parts)
            elif isinstance(content, dict):
                normalized['content'] = json.dumps(content, indent=2)

        # Create a preview version for UI display
        if 'content' in normalized:
            content_str = str(normalized['content'])
            if len(content_str) > CONTENT_PREVIEW_LENGTH:
                normalized['content_preview'] = content_str[:CONTENT_PREVIEW_LENGTH] + TRUNCATION_SUFFIX
                normalized['is_long'] = True
            else:
                normalized['content_preview'] = content_str
                normalized['is_long'] = False

        # Truncate tool_use_id for display
        if 'tool_use_id' in normalized:
            normalized['tool_use_id_short'] = str(normalized['tool_use_id'])[:8]

    return normalized


@dataclass
class SessionMessage:
    """Represents a single message in a conversation"""
    uuid: str
    type: str
    timestamp: str
    role: Optional[str] = None
    content: Optional[str] = None  # Legacy text-only content
    content_blocks: List[Dict] = field(default_factory=list)  # Structured content blocks
    model: Optional[str] = None
    tokens_input: int = 0
    tokens_output: int = 0


@dataclass
class Session:
    """Represents a Claude Code session"""
    session_id: str
    project_path: str
    project_dir: str = ""  # Encoded directory name (e.g., "-Users-santaclaude-dev")
    summary: Optional[str] = None
    git_branch: Optional[str] = None
    messages: List[SessionMessage] = field(default_factory=list)
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

    @property
    def message_count(self) -> int:
        """Return count of user/assistant messages (not system messages)"""
        return len([m for m in self.messages if m.type in ('user', 'assistant')])

    @property
    def total_tokens(self) -> int:
        """Return total token usage across all messages"""
        return sum(m.tokens_input + m.tokens_output for m in self.messages)

    @property
    def total_input_tokens(self) -> int:
        """Return total input tokens across all messages"""
        return sum(m.tokens_input for m in self.messages)

    @property
    def total_output_tokens(self) -> int:
        """Return total output tokens across all messages"""
        return sum(m.tokens_output for m in self.messages)

    @property
    def duration_minutes(self) -> Optional[float]:
        """Return session duration in minutes"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds() / 60
        return None

    @property
    def description(self) -> str:
        """Return a short description, preferring summary if available"""
        # Use summary if available
        if self.summary:
            return self.summary

        # Fall back to first user message
        for msg in self.messages:
            if msg.type == 'user' and msg.content:
                # Get first line or first MAX_DESCRIPTION_LENGTH chars, whichever is shorter
                content = msg.content.strip()
                if '\n' in content:
                    first_line = content.split('\n')[0].strip()
                else:
                    first_line = content

                # Truncate if too long
                if len(first_line) > MAX_DESCRIPTION_LENGTH:
                    return first_line[:MAX_DESCRIPTION_LENGTH - len(TRUNCATION_SUFFIX)] + TRUNCATION_SUFFIX
                return first_line

        return "Untitled Session"


def load_sessions(claude_dir: Path = Path.home() / ".claude", load_messages: bool = False) -> Dict[str, Session]:
    """Load all sessions from ~/.claude directory

    Args:
        claude_dir: Path to .claude directory
        load_messages: If True, load full message content. If False, only load metadata.
    """
    sessions = {}

    projects_dir = claude_dir / "projects"
    if not projects_dir.exists():
        return sessions

    # Iterate through project directories
    for project_dir in projects_dir.iterdir():
        if not project_dir.is_dir():
            continue

        # Load each session file
        for session_file in project_dir.glob("*.jsonl"):
            if session_file.name.startswith("agent-"):
                continue  # Skip agent sub-sessions for now

            session_id = session_file.stem
            session = Session(
                session_id=session_id,
                project_path="",  # Will be populated from cwd field in session data
                project_dir=project_dir.name  # Store encoded directory name for file lookups
            )

            # Track if we've loaded the first user message content
            first_user_message_loaded = False

            try:
                with open(session_file, 'r') as f:
                    for line in f:
                        if not line.strip():
                            continue

                        try:
                            data = json.loads(line)

                            # Extract message data
                            msg_type = data.get('type', '')

                            # Extract summary if available
                            if msg_type == 'summary' and session.summary is None:
                                session.summary = data.get('summary', '')
                                continue

                            timestamp_str = data.get('timestamp', '')

                            # Parse timestamp
                            timestamp = None
                            if timestamp_str:
                                try:
                                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))

                                    # Update session start/end times
                                    if session.start_time is None or timestamp < session.start_time:
                                        session.start_time = timestamp
                                    if session.end_time is None or timestamp > session.end_time:
                                        session.end_time = timestamp
                                except:
                                    pass

                            # Extract git branch from first message
                            if session.git_branch is None:
                                session.git_branch = data.get('gitBranch')

                            # Extract project path from cwd field
                            if not session.project_path and 'cwd' in data:
                                session.project_path = data['cwd']

                            # Create message object
                            msg = SessionMessage(
                                uuid=data.get('uuid', ''),
                                type=msg_type,
                                timestamp=timestamp_str
                            )

                            # Extract content and usage from message
                            if 'message' in data:
                                message_data = data['message']
                                msg.role = message_data.get('role')

                                # Always load content for first user message (for description), or all if load_messages is True
                                should_load_content = load_messages or (msg_type == 'user' and not first_user_message_loaded)

                                if should_load_content:
                                    content = message_data.get('content')
                                    if isinstance(content, str):
                                        msg.content = content
                                    elif isinstance(content, list):
                                        # Store all content blocks with their types
                                        text_parts = []
                                        for block in content:
                                            if isinstance(block, dict):
                                                block_type = block.get('type')

                                                # Store only known block types that we can render
                                                if block_type in ('text', 'thinking', 'tool_use', 'tool_result', 'file-history-snapshot'):
                                                    if load_messages:  # Only store blocks if loading all messages
                                                        msg.content_blocks.append(normalize_content_block(block))

                                                # Also collect text for legacy content field
                                                if block_type == 'text':
                                                    text_parts.append(block.get('text', ''))

                                        msg.content = '\n'.join(text_parts) if text_parts else None

                                    # Mark first user message as loaded
                                    if msg_type == 'user' and msg.content:
                                        first_user_message_loaded = True

                                msg.model = message_data.get('model')

                                # Extract token usage
                                usage = message_data.get('usage', {})
                                msg.tokens_input = usage.get('input_tokens', 0)
                                msg.tokens_output = usage.get('output_tokens', 0)

                            session.messages.append(msg)

                        except json.JSONDecodeError:
                            continue

                sessions[session_id] = session

            except Exception as e:
                print(f"Error loading session {session_id}: {e}")
                continue

    return sessions


def load_session_messages(session_id: str, project_dir: str, claude_dir: Path = Path.home() / ".claude") -> List[SessionMessage]:
    """Load messages for a specific session on demand

    Args:
        session_id: The session ID
        project_dir: The encoded project directory name (e.g., "-Users-santaclaude-dev")
        claude_dir: Path to .claude directory

    Returns:
        List of SessionMessage objects with full content
    """
    messages = []

    # Use the encoded project directory name directly
    session_file = claude_dir / "projects" / project_dir / f"{session_id}.jsonl"

    if not session_file.exists():
        return messages

    try:
        with open(session_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)
                    msg_type = data.get('type', '')

                    # Skip summary entries
                    if msg_type == 'summary':
                        continue

                    timestamp_str = data.get('timestamp', '')

                    # Create message object
                    msg = SessionMessage(
                        uuid=data.get('uuid', ''),
                        type=msg_type,
                        timestamp=timestamp_str
                    )

                    # Extract content and usage from message
                    if 'message' in data:
                        message_data = data['message']
                        msg.role = message_data.get('role')

                        # Extract content (can be string or list)
                        content = message_data.get('content')
                        if isinstance(content, str):
                            msg.content = content
                        elif isinstance(content, list):
                            # Store all content blocks with their types
                            text_parts = []
                            for block in content:
                                if isinstance(block, dict):
                                    block_type = block.get('type')

                                    # Store only known block types that we can render
                                    if block_type in ('text', 'thinking', 'tool_use', 'tool_result', 'file-history-snapshot'):
                                        msg.content_blocks.append(normalize_content_block(block))

                                    # Also collect text for legacy content field
                                    if block_type == 'text':
                                        text_parts.append(block.get('text', ''))

                            msg.content = '\n'.join(text_parts) if text_parts else None

                        msg.model = message_data.get('model')

                        # Extract token usage
                        usage = message_data.get('usage', {})
                        msg.tokens_input = usage.get('input_tokens', 0)
                        msg.tokens_output = usage.get('output_tokens', 0)

                    messages.append(msg)

                except json.JSONDecodeError:
                    continue

    except Exception as e:
        print(f"Error loading messages for session {session_id}: {e}")

    return messages


def get_session_summary(session: Session) -> Dict:
    """Get a summary dictionary for a session"""
    return {
        'session_id': session.session_id,
        'project_path': session.project_path,
        'git_branch': session.git_branch or 'unknown',
        'message_count': session.message_count,
        'total_tokens': session.total_tokens,
        'start_time': session.start_time.isoformat() if session.start_time else None,
        'end_time': session.end_time.isoformat() if session.end_time else None,
        'duration_minutes': session.duration_minutes
    }
