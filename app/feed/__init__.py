from flask import Blueprint

feed_bp = Blueprint("feed", __name__, url_prefix="/feed")

from app.feed import routes  # noqa: E402,F401
