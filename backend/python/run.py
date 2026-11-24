import logging
import os
import sys

from app import create_app

try:
    app = create_app()
except Exception as exc:
    logging.getLogger(__name__).critical("Server startup failed: %s", exc)
    sys.exit(1)


if __name__ == "__main__":
    app.run(
        host=os.getenv("HOST", "127.0.0.1"),
        port=int(os.getenv("PORT", "5001")),
        debug=os.getenv("FLASK_DEBUG", "0") == "1",
    )
