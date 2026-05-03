# simulator/mgmt/routes/__init__.py
from flask import Blueprint

# Single blueprint used across all route modules
bp = Blueprint("main", __name__)

# Import modules so their routes register on the blueprint
from . import (  # noqa: E402
    bridge,  # noqa: E402,F401
    errors,  # noqa: E402,F401
    gcs,  # noqa: E402,F401
    pages_attacks,  # noqa: E402,F401
    pages_guide,  # noqa: E402,F401
    pages_learning,  # noqa: E402,F401
    stages,  # noqa: E402,F401
)

# Expose as "main" for app.register_blueprint(main)
main = bp
