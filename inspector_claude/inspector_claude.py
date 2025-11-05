"""Main application for Inspector Claude"""

import reflex as rx
from inspector_claude.state import State
from inspector_claude.components import left_sidebar, session_detail


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
