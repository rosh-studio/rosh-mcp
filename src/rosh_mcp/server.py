#!/usr/bin/env python3
"""
Rosh MCP Server — Model Context Protocol wrapper for the rosh.cloud API.

Lets any MCP-capable AI tool (Claude Desktop, Claude Code, Cursor, Windsurf,
etc.) compile, publish, browse, and moderate Rosh programs directly.

Environment variables:
    ROSH_API_KEY   — rosh.cloud API key (required for all tools, including compile/docs)
    ROSH_API_BASE  — API base URL (default: https://rosh.cloud)
"""

import json
import os
from typing import Optional

import httpx
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Rosh")

# ── Config ──

API_BASE = os.environ.get("ROSH_API_BASE", "https://rosh.cloud").rstrip("/")
API_KEY = os.environ.get("ROSH_API_KEY", "")


def _headers() -> dict[str, str]:
    h = {
        "User-Agent": "RoshMCP/0.1",
        "Content-Type": "application/json",
    }
    if API_KEY:
        h["Authorization"] = f"Bearer {API_KEY}"
    return h


def _api(method: str, path: str, data: dict | None = None) -> dict:
    """Make an authenticated request to the Rosh API."""
    url = f"{API_BASE}{path}"
    with httpx.Client(timeout=30) as client:
        resp = client.request(method, url, headers=_headers(), json=data)
        resp.raise_for_status()
        return resp.json()


def _api_safe(method: str, path: str, data: dict | None = None) -> str:
    """Like _api but returns a formatted string, handling errors gracefully."""
    try:
        result = _api(method, path, data)
        return json.dumps(result, indent=2)
    except httpx.HTTPStatusError as e:
        body = e.response.text
        try:
            detail = json.loads(body)
        except json.JSONDecodeError:
            detail = body[:500]
        result = {"error": True, "status": e.response.status_code, "detail": detail}
        if e.response.status_code == 401:
            result["hint"] = "Set the ROSH_API_KEY environment variable to a valid rosh.cloud API key (Settings -> API Keys at rosh.cloud)."
        return json.dumps(result, indent=2)
    except Exception as e:
        return json.dumps({"error": True, "detail": str(e)}, indent=2)


# ── Tools ──

@mcp.tool()
def rosh_docs() -> str:
    """Get the Rosh language documentation — keywords, widgets, targets, and examples.

    Returns the full language reference including all 25 keywords, available widgets,
    compile targets (web, phaser, threejs), and example programs. Requires ROSH_API_KEY.
    """
    return _api_safe("GET", "/api/v1/docs")


@mcp.tool()
def rosh_compile(code: str, target: str = "web") -> str:
    """Compile Rosh code into a runnable HTML page. Requires ROSH_API_KEY.

    Rosh is a plain-English programming language. Example:
        create box called player at 400 300
        set player color "blue"
        on key "ArrowRight" then set player x to player x + 5

    Args:
        code: Rosh source code to compile
        target: Target platform — "web" (HTML5 canvas), "phaser" (game engine), or "threejs" (3D)
    """
    return _api_safe("POST", "/api/v1/compile", {"code": code, "target": target})


@mcp.tool()
def rosh_publish(title: str, slug: str, code: str, target: str = "web",
                 description: str = "") -> str:
    """Compile and publish a Rosh program to rosh.cloud. Requires API key with write scope.

    The published program gets a public URL at https://rosh.cloud/p/{username}/{slug}

    Args:
        title: Display title for the program
        slug: URL-safe identifier (lowercase, hyphens only, e.g. "space-shooter")
        code: Rosh source code
        target: Target platform — "web", "phaser", or "threejs"
        description: One-line description of what the program does
    """
    return _api_safe("POST", "/api/v1/programs", {
        "title": title,
        "slug": slug,
        "code": code,
        "target": target,
        "description": description,
    })


@mcp.tool()
def rosh_list_programs() -> str:
    """List all programs owned by the authenticated user. Requires API key."""
    return _api_safe("GET", "/api/v1/programs")


@mcp.tool()
def rosh_get_program(program_id: int) -> str:
    """Get details of a specific program by ID. Requires API key.

    Args:
        program_id: The numeric program ID
    """
    return _api_safe("GET", f"/api/v1/programs/{program_id}")


@mcp.tool()
def rosh_update_program(program_id: int, title: Optional[str] = None,
                        description: Optional[str] = None, code: Optional[str] = None,
                        target: Optional[str] = None) -> str:
    """Update an existing program. Only provided fields are changed. Requires API key with write scope.

    Args:
        program_id: The numeric program ID
        title: New title (optional)
        description: New description (optional)
        code: New source code (optional)
        target: New target platform (optional)
    """
    data = {}
    if title is not None:
        data["title"] = title
    if description is not None:
        data["description"] = description
    if code is not None:
        data["code"] = code
    if target is not None:
        data["target"] = target
    return _api_safe("PUT", f"/api/v1/programs/{program_id}", data)


@mcp.tool()
def rosh_delete_program(program_id: int) -> str:
    """Permanently delete a program. Requires API key with write scope.

    Args:
        program_id: The numeric program ID
    """
    return _api_safe("DELETE", f"/api/v1/programs/{program_id}")


@mcp.tool()
def rosh_hide_program(identifier: str) -> str:
    """Hide a program from public view (moderation). Requires API key with moderate scope.

    Args:
        identifier: Program ID (numeric) or slug (string)
    """
    return _api_safe("POST", f"/api/v1/programs/{identifier}/hide")


@mcp.tool()
def rosh_show_program(identifier: str) -> str:
    """Make a hidden program visible again. Requires API key with moderate scope.

    Args:
        identifier: Program ID (numeric) or slug (string)
    """
    return _api_safe("POST", f"/api/v1/programs/{identifier}/show")


def main():
    """Entry point for the MCP server."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
