# 🔍 Inspector Claude

Web UI for exploring and analyzing your local Claude Code session data.

## ✨ Features

- 🔎 Filter by message count, tokens, git branch, and date
- 📝 View complete session messages and interactions
- 🛠️ Expandable tool use/result blocks
- 💭 See Claude's internal thinking process
- 📊 Track token usage
- ⚡ Lazy loading with pagination

## 📋 Requirements

- Python 3.10+
- [UV](https://docs.astral.sh/uv/) package manager
- Claude Code session data in `~/.claude/projects/`

## 🚀 Installation

1. Clone the repository:
```bash
git clone https://github.com/santaclaude2025/inspector-claude.git
cd inspector-claude
```

2. Install dependencies:
```bash
uv sync
```

## 💻 Usage

Run the application with:
```bash
uv run reflex run
```

The web interface will be available at `http://localhost:3000`.

## 🏗️ Architecture

Built with Python and Reflex framework - the entire application is written in Python, with the frontend automatically generated.

**Data Flow:**
- Session metadata is indexed at startup from `~/.claude/projects/*.jsonl`
- Message content is loaded on-demand for selected sessions

## 📁 Project Structure

```
inspector_claude/
├── inspector_claude/
│   ├── __init__.py              # Package initialization
│   ├── indexer.py               # Data loading and session indexing
│   └── inspector_claude.py      # Main Reflex UI application
├── .web/                        # Generated frontend code (React)
├── pyproject.toml               # Python dependencies
├── rxconfig.py                  # Reflex configuration
└── README.md                    # This file
```

## 🔧 Development

Key components:
- `indexer.py` - Reads and parses JSONL session files
- `inspector_claude.py` - Application state and UI components

Session data is indexed in memory at startup for simplicity.

## 🚧 Future Enhancements

See [TODO.md](TODO.md) for planned features including:
- Image content support
- Message sender type filters
- Session compaction handling
