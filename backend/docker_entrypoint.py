"""Container entrypoint: binds 0.0.0.0 and honors PORT.

Note: Uvicorn does not enforce a maximum request duration by default.
Long-running POST /api/generate-menu requests depend on the hosting
platform or reverse-proxy timeout, not --timeout-keep-alive.
"""

from __future__ import annotations

import os

import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
