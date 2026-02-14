from flask import Flask, render_template, request, redirect, url_for, flash, Response, session
from models import db, Application
import requests
import functools
from requests.exceptions import RequestException

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///proxy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-key'

db.init_app(app)

with app.app_context():
    db.create_all()

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return view(**kwargs)
    return wrapped_view

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin': # Simple admin/admin
            session['logged_in'] = True
            return redirect(url_for('admin'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('index'))

@app.route('/admin')
@login_required
def admin():
    apps = Application.query.all()
    return render_template('admin/index.html', apps=apps)

@app.route('/admin/add', methods=['GET', 'POST'])
@login_required
def add_app():
    if request.method == 'POST':
        name = request.form.get('name')
        url = request.form.get('url')
        description = request.form.get('description')
        image_url = request.form.get('image_url')

        new_app = Application(name=name, url=url, description=description, image_url=image_url)
        db.session.add(new_app)
        db.session.commit()
        flash('Application added successfully')
        return redirect(url_for('admin'))
    return render_template('admin/add.html')

@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_app(id):
    app_to_edit = Application.query.get_or_404(id)
    if request.method == 'POST':
        app_to_edit.name = request.form.get('name')
        app_to_edit.url = request.form.get('url')
        app_to_edit.description = request.form.get('description')
        app_to_edit.image_url = request.form.get('image_url')

        db.session.commit()
        flash('Application updated successfully')
        return redirect(url_for('admin'))
    return render_template('admin/edit.html', app=app_to_edit)

@app.route('/admin/delete/<int:id>', methods=['POST'])
@login_required
def delete_app(id):
    app_to_delete = Application.query.get_or_404(id)
    db.session.delete(app_to_delete)
    db.session.commit()
    flash('Application deleted successfully')
    return redirect(url_for('admin'))

@app.route('/proxy/<int:app_id>/', defaults={'path': ''})
@app.route('/proxy/<int:app_id>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(app_id, path):
    app_item = Application.query.get_or_404(app_id)
    target_url = f"{app_item.url.rstrip('/')}/{path}"

    try:
        # Forward the request to the target application
        resp = requests.request(
            method=request.method,
            url=target_url,
            headers={key: value for (key, value) in request.headers if key != 'Host'},
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=5
        )

        # Create a response to return to the user
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = [(name, value) for (name, value) in resp.raw.headers.items()
                   if name.lower() not in excluded_headers]

        response = Response(resp.content, resp.status_code, headers)
        return response
    except RequestException as e:
        return render_template('error.html', app_name=app_item.name), 503

@app.route('/')
def index():
    query = request.args.get('q', '')
    if query:
        apps = Application.query.filter(Application.name.contains(query)).all()
    else:
        apps = Application.query.all()

    # Simple status check (might be slow if many apps, but fine for now)
    # In a real app, this should be cached or done via JS on the frontend
    app_statuses = {}
    for app_item in apps:
        try:
            response = requests.get(app_item.url, timeout=1)
            app_statuses[app_item.id] = response.status_code == 200
        except:
            app_statuses[app_item.id] = False

    return render_template('index.html', apps=apps, app_statuses=app_statuses, query=query)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
