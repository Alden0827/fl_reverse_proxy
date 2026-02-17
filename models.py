from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)
    load_balancing_enabled = db.Column(db.Boolean, default=False)
    last_backend_index = db.Column(db.Integer, default=0)

    backends = db.relationship('BackendURL', backref='application', cascade="all, delete-orphan", lazy=True)
    logs = db.relationship('RequestLog', backref='application', cascade="all, delete-orphan", lazy=True)

    def __repr__(self):
        return f'<Application {self.name}>'

class BackendURL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    is_online = db.Column(db.Boolean, default=True)
    last_checked = db.Column(db.DateTime, default=datetime.utcnow)

    logs = db.relationship('RequestLog', backref='backend', lazy=True)

class RequestLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('application.id'), nullable=False)
    backend_url_id = db.Column(db.Integer, db.ForeignKey('backend_url.id'), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    status_code = db.Column(db.Integer)
    is_success = db.Column(db.Boolean)
    path = db.Column(db.String(255))
