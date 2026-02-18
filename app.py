from flask import Flask
from models import db, BackendURL
import requests
import threading
import time
from datetime import datetime
from routes.main import main_bp
from routes.admin import admin_bp
from routes.proxy import proxy_bp

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///proxy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SESSION_COOKIE_NAME'] = 'alpha_proxy_session'

db.init_app(app)

app.register_blueprint(main_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(proxy_bp)

with app.app_context():
    db.create_all()

def health_check_worker():
    with app.app_context():
        while True:
            try:
                backends = BackendURL.query.all()
                for backend in backends:
                    try:
                        resp = requests.get(backend.url, timeout=5)
                        backend.is_online = (resp.status_code == 200)
                    except:
                        backend.is_online = False
                    backend.last_checked = datetime.utcnow()
                db.session.commit()
            except Exception as e:
                print(f"Health check error: {e}")
            time.sleep(30)

# Start health check thread
thread = threading.Thread(target=health_check_worker, daemon=True)
thread.start()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
