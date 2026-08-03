from flask import Blueprint

equipment_bp = Blueprint("equipment", __name__, url_prefix="/equipment")

from app.equipment import routes  # noqa: E402,F401
