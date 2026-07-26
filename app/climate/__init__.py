from flask import Blueprint

climate_bp = Blueprint("climate", __name__, url_prefix="/climate")

from app.climate import routes  # noqa: E402,F401
