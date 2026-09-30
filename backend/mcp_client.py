"""
================================ SKELETON STUB ================================
NorthStar Retail Digital Twin -- MCP Client  (mcp_client.py)

  BUILD PHASE : 3 (MCP Server is pre-shipped; you build the client)
  BUILT BY    : the Phase 3 prompt in the Build Guide
  CONTRACT    : GATE B -- the 6 tool input/output shapes are declared in
                mcp-server/server.py (frozen, already shipped). Build the client
                against those shapes.

WHAT IT IS
  The ONLY thing that calls the MCP Server's declared tools. It spawns
  mcp-server/server.py as a stdio subprocess (the MCP server is NOT run by
  hand) and exposes one async wrapper per tool. The executor (Phase 5) imports
  and awaits these -- it never talks to the MCP server directly, and the AF
  agents never call tools at all (they only REQUEST a tool by name).

PUBLIC SURFACE TO BUILD (one async fn per declared MCP tool)
  get_resource_metrics(resource_id=None)
  get_thresholds(...)
  run_rca(...)
  suggest_fix(...)
  apply_fix(...)
  create_servicenow_ticket(...)
  close()                      # tear down the stdio session on shutdown

TIP: use the `mcp` Python SDK's stdio client + ClientSession; keep ONE session
     open for the process lifetime and reuse it across tool calls.
==============================================================================
"""

import asyncio
import json
import sys
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


BASE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent
SERVER_SCRIPT = PROJECT_ROOT / "mcp-server" / "server.py"

_session = None
_exit_stack = None
_session_lock = asyncio.Lock()


async def _get_session() -> ClientSession:
  global _session, _exit_stack

  if _session is not None:
    return _session

  async with _session_lock:
    if _session is not None:
      return _session
    if not SERVER_SCRIPT.exists():
      raise RuntimeError(f"MCP server script not found: {SERVER_SCRIPT}")

    exit_stack = AsyncExitStack()
    try:
      await exit_stack.__aenter__()
      params = StdioServerParameters(command=sys.executable, args=[str(SERVER_SCRIPT)])
      read, write = await exit_stack.enter_async_context(stdio_client(params))
      session = await exit_stack.enter_async_context(ClientSession(read, write))
      await session.initialize()
    except Exception:
      await exit_stack.aclose()
      raise

    _session = session
    _exit_stack = exit_stack
    return session


async def close():
  global _session, _exit_stack

  async with _session_lock:
    exit_stack = _exit_stack
    _session = None
    _exit_stack = None
    if exit_stack is not None:
      await exit_stack.aclose()


async def _call_tool(name, arguments) -> dict:
  session = await _get_session()
  result = await session.call_tool(name, arguments)
  text = "".join(block.text for block in result.content if getattr(block, "text", None))
  if result.is_error:
    raise RuntimeError(text)
  if not text:
    return {}
  return json.loads(text)


async def get_resource_metrics(resource_id=None):
  arguments = {}
  if resource_id is not None:
    arguments["resource_id"] = resource_id
  return await _call_tool("get_resource_metrics", arguments)


async def get_thresholds(resource_id=None, metric_name=None):
  arguments = {}
  if resource_id is not None:
    arguments["resource_id"] = resource_id
  if metric_name is not None:
    arguments["metric_name"] = metric_name
  return await _call_tool("get_thresholds", arguments)


async def run_rca(incident_id=None, resource_id=None):
  arguments = {}
  if incident_id is not None:
    arguments["incident_id"] = incident_id
  if resource_id is not None:
    arguments["resource_id"] = resource_id
  return await _call_tool("run_rca", arguments)


async def suggest_fix(incident_id=None, resource_id=None):
  arguments = {}
  if incident_id is not None:
    arguments["incident_id"] = incident_id
  if resource_id is not None:
    arguments["resource_id"] = resource_id
  return await _call_tool("suggest_fix", arguments)


async def apply_fix(resource_id, incident_id=None, fix_description=None):
  arguments = {"resource_id": resource_id}
  if incident_id is not None:
    arguments["incident_id"] = incident_id
  if fix_description is not None:
    arguments["fix_description"] = fix_description
  return await _call_tool("apply_fix", arguments)


async def create_servicenow_ticket(
    short_description,
    description,
    urgency=None,
    category=None,
    incident_id=None,
):
  arguments = {
    "short_description": short_description,
    "description": description,
  }
  if urgency is not None:
    arguments["urgency"] = urgency
  if category is not None:
    arguments["category"] = category
  if incident_id is not None:
    arguments["incident_id"] = incident_id
  return await _call_tool("create_servicenow_ticket", arguments)
