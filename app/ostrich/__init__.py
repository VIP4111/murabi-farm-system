from flask import Blueprint

ostrich_bp = Blueprint("ostrich", __name__, url_prefix="/ostrich")

from app.ostrich import routes  # noqa: E402,F401
