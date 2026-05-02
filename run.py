"""
Local dev server — run this file from VS Code (Play) or `python run.py`.

Uses port 5002 by default (override with env SYNAPSE_PORT).
"""

import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    port = int(os.environ.get("SYNAPSE_PORT", "5002"))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() in ("1", "true", "yes")
    app.run(host="127.0.0.1", port=port, debug=debug)
