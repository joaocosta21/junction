# T11 — MCP surface

**Scores on:** 15% ("open, documented standards rather than a proprietary format"; the brief wants the wholesaler "openly readable by autonomous agents"). First item to cut if the night runs short.
**Needs:** T09. **Owns:** `src/tta/api/mcp_surface.py`, `tests/mcp/`.
**Read first:** SPEC §2 · **the current documentation of the official MCP Python SDK** (server, tools, streamable HTTP transport, mounting in an ASGI app, authentication). Do not rely on memory.

## Build
- The tools of SPEC §2 (`get_authority`, `search_products`, `get_product`, `find_substitutes`, `get_offer`, `place_order`, `get_order`, `get_audit`), each a thin call into the same service functions the REST routes use, with typed inputs and a description an agent can act on.
- The same bearer identity as REST. There is no approval tool: approving is for humans.
- Mountable by `create_app` at `/mcp`.

## Tests to write first
- The server lists exactly these tools, each with an input schema.
- `get_offer` in replay returns the same offer as the REST route for scenario 2.
- A call without identity is refused.
- No tool can decide an approval.
