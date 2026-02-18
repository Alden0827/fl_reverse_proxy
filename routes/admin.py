from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models import db, Application, BackendURL, RequestLog
from .utils import login_required
from datetime import datetime, timedelta

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

@admin_bp.route('/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        if username == 'admin' and password == 'admin': # Simple admin/admin
            session['logged_in'] = True
            return redirect(url_for('admin.admin'))
        flash('Invalid credentials')
    return render_template('login.html')

@admin_bp.route('/logout')
def admin_logout():
    session.pop('logged_in', None)
    return redirect(url_for('main.index'))

@admin_bp.route('/')
@login_required
def admin():
    apps = Application.query.all()
    return render_template('admin/index.html', apps=apps)

@admin_bp.route('/add', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.admin'))
    return render_template('admin/add.html')

@admin_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
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
        return redirect(url_for('admin.admin'))
    return render_template('admin/edit.html', app=app_to_edit)

@admin_bp.route('/delete/<int:id>', methods=['POST'])
@login_required
def delete_app(id):
    app_to_delete = Application.query.get_or_404(id)
    db.session.delete(app_to_delete)
    db.session.commit()
    flash('Application deleted successfully')
    return redirect(url_for('admin.admin'))

@admin_bp.route('/dashboard/<int:id>')
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
