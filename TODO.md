# TODO

## Features

1. **Support displaying image content**
   - Add support for rendering image content blocks in messages
   - Handle image URLs and embedded image data
   - Display images inline with appropriate sizing and controls

2. **Toggle on/off messages from sender**
   - Add toggles to filter messages by sender role (user, assistant, etc.)
   - Add toggle for file-history-snapshot messages
   - Allow users to show/hide messages based on sender type

3. **Codebase cleanup / refactoring**
   - Review and refactor code organization
   - Improve code documentation
   - Consolidate duplicate logic
   - Consider separating UI components from state management

4. **Understand and handle session compaction**
   - Investigate how Claude Code session compaction works
   - Understand the impact on session history and message availability
   - Handle compacted sessions appropriately in the UI
   - Determine if compacted messages should be displayed differently
