"""Tests for indexer module"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime

from inspector_claude.indexer import (
    extract_agent_metadata,
    load_sessions,
    load_session_messages,
    load_agent_session,
    normalize_content_block,
    AgentMetadata,
    Session,
    SessionMessage,
)


# Test Fixtures

@pytest.fixture
def sample_user_message_data():
    """Sample user message in JSONL format"""
    return {
        "uuid": "user-123",
        "type": "user",
        "timestamp": "2025-01-01T12:00:00.000Z",
        "message": {
            "role": "user",
            "content": "Hello, can you help me?"
        }
    }


@pytest.fixture
def sample_assistant_message_data():
    """Sample assistant message with tokens"""
    return {
        "uuid": "asst-456",
        "type": "assistant",
        "timestamp": "2025-01-01T12:00:05.000Z",
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-5-20250929",
            "content": [
                {"type": "text", "text": "I can help you!"}
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 50
            }
        }
    }


@pytest.fixture
def sample_agent_tool_result_data():
    """Sample tool result with agent metadata"""
    return {
        "uuid": "tool-789",
        "type": "user",
        "timestamp": "2025-01-01T12:01:00.000Z",
        "message": {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "toolu_abc123",
                    "content": "Agent completed successfully"
                }
            ]
        },
        "toolUseResult": {
            "status": "completed",
            "agentId": "abc12345",
            "prompt": "Search for files",
            "totalTokens": 5000,
            "totalDurationMs": 12345,
            "content": [
                {"type": "text", "text": "Found 10 files matching the pattern"}
            ]
        }
    }


@pytest.fixture
def sample_summary_data():
    """Sample summary entry"""
    return {
        "type": "summary",
        "summary": "User asked for help",
        "timestamp": "2025-01-01T12:05:00.000Z"
    }


@pytest.fixture
def sample_thinking_message():
    """Sample message with thinking block"""
    return {
        "uuid": "think-999",
        "type": "assistant",
        "timestamp": "2025-01-01T12:00:10.000Z",
        "message": {
            "role": "assistant",
            "model": "claude-sonnet-4-5-20250929",
            "content": [
                {"type": "thinking", "thinking": "I should analyze this request"},
                {"type": "text", "text": "Let me think about that..."}
            ],
            "usage": {
                "input_tokens": 150,
                "output_tokens": 75
            }
        }
    }


@pytest.fixture
def temp_session_file(tmp_path, sample_user_message_data, sample_assistant_message_data, sample_summary_data):
    """Create a temporary session file"""
    session_file = tmp_path / "test-session-id.jsonl"

    with open(session_file, 'w') as f:
        # Write messages
        f.write(json.dumps(sample_user_message_data) + '\n')
        f.write(json.dumps(sample_assistant_message_data) + '\n')
        f.write(json.dumps(sample_summary_data) + '\n')

    return session_file


@pytest.fixture
def temp_agent_file(tmp_path):
    """Create a temporary agent session file"""
    agent_file = tmp_path / "agent-abc12345.jsonl"

    agent_messages = [
        {
            "uuid": "agent-msg-1",
            "type": "user",
            "timestamp": "2025-01-01T12:01:00.000Z",
            "sessionId": "parent-session-id",
            "agentId": "abc12345",
            "isSidechain": True,
            "message": {
                "role": "user",
                "content": "Search for files"
            }
        },
        {
            "uuid": "agent-msg-2",
            "type": "assistant",
            "timestamp": "2025-01-01T12:01:05.000Z",
            "sessionId": "parent-session-id",
            "agentId": "abc12345",
            "isSidechain": True,
            "message": {
                "role": "assistant",
                "model": "claude-sonnet-4-5-20250929",
                "content": [
                    {"type": "text", "text": "Found 10 files"}
                ],
                "usage": {
                    "input_tokens": 200,
                    "output_tokens": 100
                }
            }
        }
    ]

    with open(agent_file, 'w') as f:
        for msg in agent_messages:
            f.write(json.dumps(msg) + '\n')

    return agent_file


# Tests for extract_agent_metadata

def test_extract_agent_metadata_success(sample_agent_tool_result_data):
    """Test extracting agent metadata from a tool result"""
    metadata = extract_agent_metadata(sample_agent_tool_result_data)

    assert metadata is not None
    assert isinstance(metadata, AgentMetadata)
    assert metadata.agent_id == "abc12345"
    assert metadata.tool_use_id == "toolu_abc123"
    assert metadata.prompt == "Search for files"
    assert metadata.status == "completed"
    assert metadata.total_tokens == 5000
    assert metadata.total_duration_ms == 12345
    assert "Found 10 files" in metadata.summary


def test_extract_agent_metadata_no_tool_result(sample_user_message_data):
    """Test that non-tool-result messages return None"""
    metadata = extract_agent_metadata(sample_user_message_data)
    assert metadata is None


def test_extract_agent_metadata_no_agent_id(sample_agent_tool_result_data):
    """Test that tool results without agentId return None"""
    # Remove agentId
    del sample_agent_tool_result_data["toolUseResult"]["agentId"]
    metadata = extract_agent_metadata(sample_agent_tool_result_data)
    assert metadata is None


# Tests for normalize_content_block

def test_normalize_text_block():
    """Test normalizing a text content block"""
    block = {"type": "text", "text": "Hello world"}
    normalized = normalize_content_block(block)

    assert normalized["type"] == "text"
    assert normalized["text"] == "Hello world"


def test_normalize_text_block_missing_text():
    """Test normalizing a text block without text field"""
    block = {"type": "text"}
    normalized = normalize_content_block(block)

    assert normalized["text"] == "(no text content)"


def test_normalize_tool_use_block():
    """Test normalizing a tool_use block"""
    block = {
        "type": "tool_use",
        "id": "toolu_veryLongIdString1234567890",
        "name": "Read",
        "input": {"file_path": "/test.py"}
    }
    normalized = normalize_content_block(block)

    assert normalized["type"] == "tool_use"
    assert normalized["name"] == "Read"
    assert normalized["id_short"] == "toolu_ve"  # First 8 chars
    assert isinstance(normalized["input"], str)  # Converted to JSON string


def test_normalize_tool_result_block():
    """Test normalizing a tool_result block"""
    block = {
        "type": "tool_result",
        "tool_use_id": "toolu_veryLongIdString",
        "content": "File contents here"
    }
    normalized = normalize_content_block(block)

    assert normalized["type"] == "tool_result"
    assert normalized["tool_use_id_short"] == "toolu_ve"
    assert normalized["content"] == "File contents here"
    assert normalized["is_long"] is False  # Short content


def test_normalize_tool_result_long_content():
    """Test normalizing a tool_result with long content"""
    long_content = "x" * 500  # Longer than CONTENT_PREVIEW_LENGTH
    block = {
        "type": "tool_result",
        "tool_use_id": "toolu_12345",
        "content": long_content
    }
    normalized = normalize_content_block(block)

    assert normalized["is_long"] is True
    assert len(normalized["content_preview"]) <= 303  # 300 + "..."
    assert normalized["content_preview"].endswith("...")


# Tests for load_sessions

def test_load_sessions_from_temp_dir(tmp_path, temp_session_file):
    """Test loading sessions from a temporary directory"""
    # Create projects structure
    projects_dir = tmp_path / "projects" / "test-project"
    projects_dir.mkdir(parents=True)

    # Move session file to projects dir
    import shutil
    shutil.move(str(temp_session_file), str(projects_dir / temp_session_file.name))

    # Load sessions
    sessions = load_sessions(claude_dir=tmp_path, load_messages=False)

    assert len(sessions) == 1
    assert "test-session-id" in sessions

    session = sessions["test-session-id"]
    assert session.session_id == "test-session-id"
    assert session.summary == "User asked for help"
    assert len(session.messages) == 2  # user + assistant (summary not counted)


def test_load_sessions_with_messages(tmp_path, temp_session_file):
    """Test loading sessions with full message content"""
    projects_dir = tmp_path / "projects" / "test-project"
    projects_dir.mkdir(parents=True)

    import shutil
    shutil.move(str(temp_session_file), str(projects_dir / temp_session_file.name))

    sessions = load_sessions(claude_dir=tmp_path, load_messages=True)
    session = sessions["test-session-id"]

    # Check that messages have content
    user_msg = [m for m in session.messages if m.type == "user"][0]
    assert user_msg.content == "Hello, can you help me?"

    asst_msg = [m for m in session.messages if m.type == "assistant"][0]
    assert asst_msg.tokens_input == 100
    assert asst_msg.tokens_output == 50


def test_load_sessions_skips_agents(tmp_path, temp_agent_file):
    """Test that load_sessions skips agent files"""
    projects_dir = tmp_path / "projects" / "test-project"
    projects_dir.mkdir(parents=True)

    import shutil
    shutil.move(str(temp_agent_file), str(projects_dir / temp_agent_file.name))

    sessions = load_sessions(claude_dir=tmp_path, load_messages=False)

    # Should not load agent files
    assert len(sessions) == 0


# Tests for load_agent_session

def test_load_agent_session(tmp_path, temp_agent_file):
    """Test loading an agent session"""
    projects_dir = tmp_path / "projects" / "test-project"
    projects_dir.mkdir(parents=True)

    import shutil
    shutil.move(str(temp_agent_file), str(projects_dir / temp_agent_file.name))

    agent_session = load_agent_session("abc12345", "test-project", claude_dir=tmp_path)

    assert agent_session is not None
    assert agent_session.is_agent is True
    assert agent_session.parent_session_id == "parent-session-id"
    assert len(agent_session.messages) == 2


def test_load_agent_session_not_found(tmp_path):
    """Test loading non-existent agent session"""
    projects_dir = tmp_path / "projects" / "test-project"
    projects_dir.mkdir(parents=True)

    agent_session = load_agent_session("nonexistent", "test-project", claude_dir=tmp_path)

    assert agent_session is None


# Tests for Session properties

def test_session_message_count():
    """Test session message_count property"""
    session = Session(
        session_id="test",
        project_path="/test",
        messages=[
            SessionMessage(uuid="1", type="user", timestamp="2025-01-01"),
            SessionMessage(uuid="2", type="assistant", timestamp="2025-01-01"),
            SessionMessage(uuid="3", type="file-history-snapshot", timestamp="2025-01-01"),
        ]
    )

    # Only counts user/assistant messages
    assert session.message_count == 2


def test_session_total_tokens():
    """Test session total_tokens property"""
    session = Session(
        session_id="test",
        project_path="/test",
        messages=[
            SessionMessage(uuid="1", type="user", timestamp="2025-01-01", tokens_input=100, tokens_output=0),
            SessionMessage(uuid="2", type="assistant", timestamp="2025-01-01", tokens_input=150, tokens_output=75),
        ]
    )

    assert session.total_tokens == 325  # 100 + 150 + 75


def test_session_description_uses_summary():
    """Test that session description prefers summary"""
    session = Session(
        session_id="test",
        project_path="/test",
        summary="This is the summary",
        messages=[
            SessionMessage(uuid="1", type="user", timestamp="2025-01-01", content="First message"),
        ]
    )

    assert session.description == "This is the summary"


def test_session_description_falls_back_to_first_message():
    """Test that session description falls back to first user message"""
    session = Session(
        session_id="test",
        project_path="/test",
        messages=[
            SessionMessage(uuid="1", type="user", timestamp="2025-01-01", content="First user message"),
        ]
    )

    assert session.description == "First user message"


def test_session_description_truncates_long_message():
    """Test that long descriptions are truncated"""
    long_content = "x" * 200  # Longer than MAX_DESCRIPTION_LENGTH
    session = Session(
        session_id="test",
        project_path="/test",
        messages=[
            SessionMessage(uuid="1", type="user", timestamp="2025-01-01", content=long_content),
        ]
    )

    assert len(session.description) <= 100
    assert session.description.endswith("...")
