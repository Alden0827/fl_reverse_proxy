from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class Application(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    url = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    image_url = db.Column(db.String(255), nullable=True)

    def __repr__(self):
        return f'<Application {self.name}>'
