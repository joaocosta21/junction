"""FastAPI app, routes, authentication and the MCP surface.

    from tta.api import create_app
    app = create_app(settings)          # or: uvicorn --factory tta.api:create_app

`tta.api.service.Gateway` is the one object behind every transport (the `GatewayService` port);
`tta.api.hooks` says how the buyer agent, the MCP surface and the pages plug in.
"""

from tta.api.app import create_app

__all__ = ["create_app"]
