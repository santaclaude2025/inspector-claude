# TODO

## Features

1. **Support displaying image content** ✅ (Complete)
   - ✅ Added 'image' to known content block types in indexer
   - ✅ Flattened image source structure (source_type, source_data, source_url, source_media_type)
   - ✅ Created render_image_block function with conditional rendering
   - ✅ Supports both base64-encoded images and URL-based images
   - ✅ Images display inline with max dimensions (600px height, 100% width)
   - ✅ Styled with violet badge and purple background (#faf5ff)

2. **Toggle on/off messages from sender**
   - Add toggles to filter messages by sender role (user, assistant, etc.)
   - Add toggle for file-history-snapshot messages
   - Allow users to show/hide messages based on sender type

3. **Codebase cleanup / refactoring** ✅ (Mostly Complete)
   - ✅ Consolidated duplicate filter setter logic (8 methods → 1 generic method)
   - ✅ Created reusable styled_content_block wrapper
   - ✅ Removed unused computed properties (5 @rx.var methods)
   - ✅ Created range_filter_input helper (eliminated ~45 lines)
   - ✅ Removed dead code (session_list function)
   - ✅ Extracted magic numbers to constants
   - ✅ Extracted color scheme to COLORS dictionary
   - ✅ Simplified reset_filters and active_filter_count with loops
   - ✅ Removed debug print statements
   - 📋 Consider separating UI components from state management (future enhancement)

4. **Understand and handle session compaction**
   - Investigate how Claude Code session compaction works
   - Understand the impact on session history and message availability
   - Handle compacted sessions appropriately in the UI
   - Determine if compacted messages should be displayed differently
