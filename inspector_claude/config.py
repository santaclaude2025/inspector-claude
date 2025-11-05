"""Configuration constants for Inspector Claude"""

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
