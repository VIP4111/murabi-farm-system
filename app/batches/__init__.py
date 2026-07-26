from flask import Blueprint

batches_bp = Blueprint("batches", __name__, url_prefix="/batches")

from app.batches import routes  # noqa: E402,F401
