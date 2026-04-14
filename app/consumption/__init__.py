from flask import Blueprint
consumption_bp = Blueprint('consumption', __name__, template_folder='../templates/consumption')
from app.consumption import routes
