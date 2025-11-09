"""Index and load Claude Code session data from configured claude_dir"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
from pydantic import BaseModel
import rxconfig

# Constants for session description
MAX_DESCRIPTION_LENGTH = 100
TRUNCATION_SUFFIX = "..."
CONTENT_PREVIEW_LENGTH = 300  # Used for tool result previews


def normalize_content_block(block: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize a content block by converting complex objects to strings for UI display"""
    normalized = block.copy()
    block_type = block.get('type')

    # Ensure text blocks have 'text' key
    if block_type == 'text':
        if 'text' not in normalized or normalized['text'] is None:
            normalized['text'] = '(no text content)'

    # Ensure thinking blocks have 'thinking' key
    if block_type == 'thinking':
        if 'thinking' not in normalized or normalized['thinking'] is None:
            normalized['thinking'] = '(no thinking content)'

    # Convert tool_use input to JSON string for display and truncate ID
    if block_type == 'tool_use':
        # Ensure required keys exist
        if 'name' not in normalized:
            normalized['name'] = 'unknown'
        if 'input' not in normalized:
            normalized['input'] = '{}'
        elif isinstance(normalized['input'], dict):
            normalized['input'] = json.dumps(normalized['input'], indent=2)
        # Truncate ID for display
        if 'id' in normalized:
            normalized['id_short'] = str(normalized['id'])[:8]
        else:
            normalized['id_short'] = 'unknown'

    # Convert tool_result content to string if it's a list and truncate tool_use_id
    if block_type == 'tool_result':
        # Ensure content exists
        if 'content' not in normalized:
            normalized['content'] = '(no content)'
        else:
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
        else:
            normalized['tool_use_id_short'] = 'unknown'

    # Flatten image source structure for easier UI rendering
    if block_type == 'image':
        if 'source' in normalized and isinstance(normalized['source'], dict):
            source = normalized['source']
            normalized['source_type'] = source.get('type', 'unknown')
            normalized['source_media_type'] = source.get('media_type', 'image/png')
            normalized['source_data'] = source.get('data', '')
            normalized['source_url'] = source.get('url', '')
        else:
            # Provide defaults if source is missing
            normalized['source_type'] = 'unknown'
            normalized['source_media_type'] = 'image/png'
            normalized['source_data'] = ''
            normalized['source_url'] = ''

    return normalized


class AgentMetadata(BaseModel):
    """Metadata about an agent invocation"""
    agent_id: str
    tool_use_id: str          # Links to the tool_use that created this agent
    prompt: str               # Task given to agent
    status: str               # "completed", "failed", etc.
    total_tokens: int
    total_duration_ms: int
    summary: str              # Summary from agent's final response (truncated)


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
    agent_metadata: Optional[AgentMetadata] = None  # For tool_result blocks that invoked agents


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
    is_agent: bool = False  # True if this is an agent side-chain
    parent_session_id: Optional[str] = None  # For agents, links to parent session ID

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


def extract_agent_metadata(message_data: dict) -> Optional[AgentMetadata]:
    """Extract agent metadata from toolUseResult field

    Args:
        message_data: The top-level message dict from JSONL

    Returns:
        AgentMetadata if this message has a toolUseResult with agentId, else None
    """
    tool_use_result = message_data.get('toolUseResult')
    if not tool_use_result or not isinstance(tool_use_result, dict):
        return None

    agent_id = tool_use_result.get('agentId')
    if not agent_id:
        return None

    # Extract tool_use_id from the message content
    tool_use_id = None
    message = message_data.get('message', {})
    content = message.get('content', [])
    if isinstance(content, list):
        for block in content:
            if isinstance(block, dict) and block.get('type') == 'tool_result':
                tool_use_id = block.get('tool_use_id', '')
                break

    # Extract summary from agent's final response (first text block, truncated)
    summary = ""
    result_content = tool_use_result.get('content', [])
    if isinstance(result_content, list):
        for item in result_content:
            if isinstance(item, dict) and item.get('type') == 'text':
                text = item.get('text', '')
                # Truncate to 200 characters
                summary = text[:200] + "..." if len(text) > 200 else text
                break

    return AgentMetadata(
        agent_id=agent_id,
        tool_use_id=tool_use_id or 'unknown',
        prompt=tool_use_result.get('prompt', ''),
        status=tool_use_result.get('status', 'unknown'),
        total_tokens=tool_use_result.get('totalTokens', 0),
        total_duration_ms=tool_use_result.get('totalDurationMs', 0),
        summary=summary
    )


def parse_message_from_jsonl(data: dict, load_content: bool = True, load_blocks: bool = True) -> Optional[SessionMessage]:
    """Parse a single JSONL line into a SessionMessage

    Args:
        data: Parsed JSON object from JSONL line
        load_content: Whether to load full message content
        load_blocks: Whether to populate content_blocks (only applies if load_content=True)

    Returns:
        SessionMessage or None if this is a non-message entry (e.g., summary)
    """
    msg_type = data.get('type', '')

    # Skip summary entries
    if msg_type == 'summary':
        return None

    msg = SessionMessage(
        uuid=data.get('uuid', ''),
        type=msg_type,
        timestamp=data.get('timestamp', '')
    )

    # Extract agent metadata if present (only for user messages)
    if msg_type == 'user':
        agent_metadata = extract_agent_metadata(data)
        if agent_metadata:
            msg.agent_metadata = agent_metadata

    # Extract content and usage from message
    if 'message' in data:
        message_data = data['message']
        msg.role = message_data.get('role')

        if load_content:
            content = message_data.get('content')
            if isinstance(content, str):
                msg.content = content
            elif isinstance(content, list):
                text_parts = []
                for block in content:
                    if isinstance(block, dict):
                        block_type = block.get('type')
                        if block_type in ('text', 'thinking', 'tool_use', 'tool_result', 'file-history-snapshot', 'image'):
                            if load_blocks:
                                msg.content_blocks.append(normalize_content_block(block))
                        if block_type == 'text':
                            text_parts.append(block.get('text', ''))
                msg.content = '\n'.join(text_parts) if text_parts else None

        msg.model = message_data.get('model')

        # Extract token usage
        usage = message_data.get('usage', {})
        msg.tokens_input = usage.get('input_tokens', 0)
        msg.tokens_output = usage.get('output_tokens', 0)

    return msg


def parse_session_metadata_from_jsonl(data: dict, session: Session) -> None:
    """Update session metadata from a JSONL line (in-place)

    Args:
        data: Parsed JSON object from JSONL line
        session: Session object to update
    """
    msg_type = data.get('type', '')

    # Extract summary
    if msg_type == 'summary' and session.summary is None:
        session.summary = data.get('summary', '')
        return

    # Parse timestamp and update session time range
    timestamp_str = data.get('timestamp', '')
    if timestamp_str:
        try:
            timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            if session.start_time is None or timestamp < session.start_time:
                session.start_time = timestamp
            if session.end_time is None or timestamp > session.end_time:
                session.end_time = timestamp
        except:
            pass

    # Extract git branch
    if session.git_branch is None:
        session.git_branch = data.get('gitBranch')

    # Extract project path
    if not session.project_path and 'cwd' in data:
        session.project_path = data['cwd']


def load_agent_session(agent_id: str, project_dir: str, claude_dir: Path = None) -> Optional[Session]:
    """Load a specific agent session file

    Args:
        agent_id: The 8-char agent ID (e.g., "57a58820")
        project_dir: Encoded project directory name
        claude_dir: Path to .claude directory (defaults to rxconfig.claude_dir)

    Returns:
        Session object with agent messages, or None if not found
    """
    if claude_dir is None:
        claude_dir = rxconfig.claude_dir

    agent_file = claude_dir / "projects" / project_dir / f"agent-{agent_id}.jsonl"

    if not agent_file.exists():
        print(f"Agent file not found: {agent_file}")
        return None

    # Create agent session object
    session = Session(
        session_id=f"agent-{agent_id}",
        project_path="",
        project_dir=project_dir,
        is_agent=True
    )

    try:
        with open(agent_file, 'r') as f:
            for line in f:
                if not line.strip():
                    continue

                try:
                    data = json.loads(line)

                    # Extract parent session ID from first message
                    if session.parent_session_id is None:
                        session.parent_session_id = data.get('sessionId')

                    # Update session metadata
                    parse_session_metadata_from_jsonl(data, session)

                    # Parse message (with full content)
                    msg = parse_message_from_jsonl(data, load_content=True)
                    if msg:
                        session.messages.append(msg)

                except json.JSONDecodeError:
                    continue

    except Exception as e:
        print(f"Error loading agent session {agent_id}: {e}")
        return None

    return session


def load_sessions(claude_dir: Path = None, load_messages: bool = False) -> Dict[str, Session]:
    """Load all sessions from configured claude_dir

    Args:
        claude_dir: Path to .claude directory (defaults to rxconfig.claude_dir)
        load_messages: If True, load full message content. If False, only load metadata.
    """
    if claude_dir is None:
        claude_dir = rxconfig.claude_dir
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

                            # Update session metadata
                            parse_session_metadata_from_jsonl(data, session)

                            # Determine content loading strategy
                            msg_type = data.get('type', '')
                            should_load_content = load_messages or (msg_type == 'user' and not first_user_message_loaded)
                            should_load_blocks = load_messages  # Only load blocks if loading all messages

                            # Parse message
                            msg = parse_message_from_jsonl(data, load_content=should_load_content, load_blocks=should_load_blocks)
                            if msg:
                                session.messages.append(msg)

                                # Track first user message for description
                                if msg_type == 'user' and msg.content:
                                    first_user_message_loaded = True

                        except json.JSONDecodeError:
                            continue

                sessions[session_id] = session

            except Exception as e:
                print(f"Error loading session {session_id}: {e}")
                continue

    return sessions


def load_session_messages(session_id: str, project_dir: str, claude_dir: Path = None) -> List[SessionMessage]:
    """Load messages for a specific session on demand

    Args:
        session_id: The session ID
        project_dir: The encoded project directory name (e.g., "-Users-santaclaude-dev")
        claude_dir: Path to .claude directory (defaults to rxconfig.claude_dir)

    Returns:
        List of SessionMessage objects with full content
    """
    if claude_dir is None:
        claude_dir = rxconfig.claude_dir
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

                    # Parse message with full content and blocks
                    msg = parse_message_from_jsonl(data, load_content=True, load_blocks=True)
                    if msg:
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
