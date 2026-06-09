"""Visibility (level 6): terminal stream + two HTML pages (Streaming Log + State View) over a
stdlib WebSocket. Read-only; never affects execution."""

from planfoldr.visibility.events import VisibilityState
from planfoldr.visibility.terminal import TerminalStream
from planfoldr.visibility.web import VisibilityServer, render_state_view_html, render_stream_log_html

__all__ = [
    "TerminalStream",
    "VisibilityState",
    "VisibilityServer",
    "render_stream_log_html",
    "render_state_view_html",
]
