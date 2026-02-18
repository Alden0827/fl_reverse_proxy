from flask import Blueprint, render_template, request
from models import Application

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    query = request.args.get('q', '')
    if query:
        apps = Application.query.filter(Application.name.contains(query)).all()
    else:
        apps = Application.query.all()

    # Determine app status: online if at least one backend is online
    app_statuses = {}
    for app_item in apps:
        app_statuses[app_item.id] = any(b.is_online for b in app_item.backends)

    return render_template('index.html', apps=apps, app_statuses=app_statuses, query=query)
