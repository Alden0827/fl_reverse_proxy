from flask import Flask, render_template, request, redirect, url_for, flash, Response, session, jsonify
from models import db, Application, BackendURL, RequestLog
import requests
import functools
import re
import threading
import time
from datetime import datetime, timedelta
from sqlalchemy import func
from requests.exceptions import RequestException

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///proxy.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'dev-secret-key'
app.config['SESSION_COOKIE_NAME'] = 'proxyhub_session'

db.init_app(app)

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

def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin_login'))
        return view(**kwargs)
    return wrapped_view

@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin': # Simple admin/admin
            session['logged_in'] = True
            return redirect(url_for('admin'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/admin/logout')
def admin_logout():
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
        description = request.form.get('description')
        image_url = request.form.get('image_url')
        load_balancing_enabled = 'load_balancing_enabled' in request.form
        urls = request.form.getlist('urls')

        new_app = Application(
            name=name,
            description=description,
            image_url=image_url,
            load_balancing_enabled=load_balancing_enabled
        )

        for url in urls:
            if url.strip():
                backend = BackendURL(url=url.strip())
                new_app.backends.append(backend)

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
        app_to_edit.description = request.form.get('description')
        app_to_edit.image_url = request.form.get('image_url')
        app_to_edit.load_balancing_enabled = 'load_balancing_enabled' in request.form

        # Update backends
        new_urls = [u.strip() for u in request.form.getlist('urls') if u.strip()]

        # Simple approach: remove all and re-add
        for backend in app_to_edit.backends:
            db.session.delete(backend)

        for url in new_urls:
            new_backend = BackendURL(url=url)
            app_to_edit.backends.append(new_backend)

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

@app.route('/admin/dashboard/<int:id>')
@login_required
def app_dashboard(id):
    app_item = Application.query.get_or_404(id)

    # Filters
    start_date_str = request.args.get('start_date')
    end_date_str = request.args.get('end_date')
    backend_id = request.args.get('backend_id', type=int)

    query = RequestLog.query.filter_by(application_id=id)

    if start_date_str:
        try:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
            query = query.filter(RequestLog.timestamp >= start_date)
        except ValueError:
            pass

    if end_date_str:
        try:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d') + timedelta(days=1)
            query = query.filter(RequestLog.timestamp < end_date)
        except ValueError:
            pass

    if backend_id:
        query = query.filter_by(backend_url_id=backend_id)

    logs = query.order_by(RequestLog.timestamp.desc()).all()

    # Stats for the dashboard
    total_requests = len(logs)
    success_requests = sum(1 for log in logs if log.is_success)
    failed_requests = total_requests - success_requests
    success_rate = (success_requests / total_requests * 100) if total_requests > 0 else 0

    # Translations per day (last 30 days)
    today = datetime.utcnow().date()
    daily_stats = []
    for i in range(29, -1, -1):
        day = today - timedelta(days=i)
        count = sum(1 for log in logs if log.timestamp.date() == day)
        daily_stats.append({'date': day.strftime('%Y-%m-%d'), 'count': count})

    # Translations per hour (last 24 hours)
    now = datetime.utcnow()
    hourly_stats = []
    for i in range(23, -1, -1):
        hour_time = now - timedelta(hours=i)
        count = sum(1 for log in logs if log.timestamp.replace(minute=0, second=0, microsecond=0) == hour_time.replace(minute=0, second=0, microsecond=0))
        hourly_stats.append({'hour': hour_time.strftime('%H:00'), 'count': count})

    return render_template('admin/dashboard.html',
                           app=app_item,
                           total_requests=total_requests,
                           success_requests=success_requests,
                           failed_requests=failed_requests,
                           success_rate=success_rate,
                           daily_stats=daily_stats,
                           hourly_stats=hourly_stats,
                           start_date=start_date_str,
                           end_date=end_date_str,
                           selected_backend_id=backend_id)

@app.route('/proxy/<int:app_id>/', defaults={'path': ''})
@app.route('/proxy/<int:app_id>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy(app_id, path):
    app_item = Application.query.get_or_404(app_id)

    backends = app_item.backends
    if not backends:
         return render_template('error.html', app_name=app_item.name, message="No backends configured"), 503

    selected_backend = None
    if app_item.load_balancing_enabled:
        # Round-robin among online backends
        for i in range(len(backends)):
            idx = (app_item.last_backend_index + i + 1) % len(backends)
            if backends[idx].is_online:
                selected_backend = backends[idx]
                app_item.last_backend_index = idx
                db.session.commit()
                break
    else:
        # Use first online backend
        for b in backends:
            if b.is_online:
                selected_backend = b
                break

    if not selected_backend:
        return render_template('error.html', app_name=app_item.name, message="No online backends available"), 503

    target_url = f"{selected_backend.url.rstrip('/')}/{path}"

    try:
        # Forward the request to the target application
        forward_headers = {key: value for (key, value) in request.headers if key.lower() not in ['host', 'cookie']}

        # Add X-Forwarded headers
        forward_headers['X-Forwarded-For'] = request.remote_addr
        forward_headers['X-Forwarded-Host'] = request.host
        forward_headers['X-Forwarded-Proto'] = request.scheme
        forward_headers['X-Forwarded-Prefix'] = f"/proxy/{app_id}"

        resp = requests.request(
            method=request.method,
            url=target_url,
            headers=forward_headers,
            data=request.get_data(),
            cookies=request.cookies,
            allow_redirects=False,
            timeout=10
        )

        # Log the request
        log = RequestLog(
            application_id=app_id,
            backend_url_id=selected_backend.id,
            status_code=resp.status_code,
            is_success=(200 <= resp.status_code < 400),
            path=path
        )
        db.session.add(log)
        db.session.commit()

        # Create a response to return to the user
        excluded_headers = ['content-encoding', 'content-length', 'transfer-encoding', 'connection']
        headers = []
        content_type = resp.headers.get('Content-Type', '')

        for name, value in resp.headers.items():
            name_lower = name.lower()
            if name_lower not in excluded_headers:
                if name_lower == 'location':
                    proxy_prefix = f"/proxy/{app_id}"
                    if value.startswith('/'):
                        if not value.startswith(f"{proxy_prefix}/"):
                            value = f"{proxy_prefix}{value}"
                    elif value.startswith(selected_backend.url.rstrip('/')):
                        backend_url = selected_backend.url.rstrip('/')
                        if not value.startswith(f"{backend_url}{proxy_prefix}/"):
                            value = value.replace(backend_url, proxy_prefix, 1)
                        else:
                            value = value.replace(backend_url, "", 1)
                headers.append((name, value))

        content = resp.content
        if any(t in content_type for t in ['text/html', 'text/css', 'application/javascript', 'application/json']):
            proxy_prefix = f"/proxy/{app_id}"
            pattern = rb'(?<=["\'=\(])/(?![/]|proxy/\d+/)'
            replacement = f"{proxy_prefix}/".encode()
            content = re.sub(pattern, replacement, content)

            backend_url = selected_backend.url.rstrip('/')
            base_url_no_proto = backend_url.split('://')[-1]
            full_url_pattern = rb'(https?://|//)' + re.escape(base_url_no_proto.encode()) + rb'/?(?![/]|proxy/\d+/)'
            content = re.sub(full_url_pattern, proxy_prefix.encode() + b'/', content)

        return Response(content, resp.status_code, headers)
    except RequestException as e:
        log = RequestLog(
            application_id=app_id,
            backend_url_id=selected_backend.id,
            status_code=503,
            is_success=False,
            path=path
        )
        db.session.add(log)
        db.session.commit()
        return render_template('error.html', app_name=app_item.name, message="Backend request failed"), 503

@app.route('/')
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)
