from flask import Blueprint
wages_bp = Blueprint('wages', __name__, template_folder='../templates/wages')
from app.wages import routes
