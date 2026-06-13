"""Entrypoint that reads PORT from the environment and starts uvicorn.

Avoids all shell-expansion issues: Python reads the env var directly, so it
works regardless of whether the platform invokes the command through a shell.
Railway injects PORT; falls back to 8000 locally.
"""
import os
import uvicorn

if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    uvicorn.run("app.api.main:app", host="0.0.0.0", port=port)
