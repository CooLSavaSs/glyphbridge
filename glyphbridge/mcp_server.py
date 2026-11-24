"""MCP server: lets AI assistants (Claude and others) use Glyphbridge as a tool.

Start it with ``glyphbridge mcp`` (stdio transport). Example client config:

    {"mcpServers": {"glyphbridge": {"command": "glyphbridge", "args": ["mcp"]}}}
"""

from __future__ import annotations

from .engine import SUPPORTED_LANGUAGES, TranslationError, get_engine


def build_server():
    try:
        from mcp.server.fastmcp import FastMCP  # type: ignore
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise SystemExit("MCP support needs: pip install 'glyphbridge[mcp]'") from exc

    server = FastMCP("glyphbridge")

    @server.tool()
    def translate(text: str, target: str, source: str = "auto") -> dict:
        """Translate text offline. `target` and `source` are language codes such as
        'en', 'tr', 'de'; use source='auto' to detect the language."""
        try:
            return get_engine().translate(text, target=target, source=source).to_dict()
        except TranslationError as exc:
            return {"error": str(exc)}

    @server.tool()
    def list_languages() -> dict:
        """List Glyphbridge's core language codes."""
        return SUPPORTED_LANGUAGES

    return server


def run() -> None:
    build_server().run()
