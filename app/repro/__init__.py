from flask import Blueprint

repro_bp = Blueprint("repro", __name__, url_prefix="/repro")

from app.repro import routes  # noqa: E402,F401
