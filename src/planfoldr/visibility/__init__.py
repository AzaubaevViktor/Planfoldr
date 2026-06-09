"""Visibility (level 6): terminal stream + four HTML pages (Streaming Log, State View, Tickets,
Knowledge Base) + a Run Analysis artifact, live over a stdlib WebSocket and as static files.
Read-only; never affects execution."""

from planfoldr.visibility.analysis import build_analysis
from planfoldr.visibility.events import VisibilityState
from planfoldr.visibility.terminal import TerminalStream
from planfoldr.visibility.web import (
    VisibilityServer,
    render_kb_html,
    render_state_view_html,
    render_stream_log_html,
    render_tickets_html,
    write_report,
)

__all__ = [
    "TerminalStream",
    "VisibilityState",
    "VisibilityServer",
    "render_stream_log_html",
    "render_state_view_html",
    "render_tickets_html",
    "render_kb_html",
    "write_report",
    "build_analysis",
]
