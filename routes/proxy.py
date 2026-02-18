from flask import Blueprint, render_template, request, Response, redirect
from models import db, Application, RequestLog
import requests
import re
from requests.exceptions import RequestException

proxy_bp = Blueprint('proxy', __name__)


@proxy_bp.route('/proxy/<int:app_id>/', defaults={'path': ''}, methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
@proxy_bp.route('/proxy/<int:app_id>/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def rewrite_content(content, content_type, proxy_prefix, selected_backend):
    if any(t in content_type for t in ['text/html', 'text/css', 'application/javascript', 'application/json']):
        pattern = rb'(?<=["\'=\(])/(?![/]|proxy/\d+/)'
        replacement = f"{proxy_prefix}/".encode()
        content = re.sub(pattern, replacement, content)

        backend_url = selected_backend.url.rstrip('/')
        base_url_no_proto = backend_url.split('://')[-1]
        full_url_pattern = rb'(https?://|//)' + re.escape(base_url_no_proto.encode()) + rb'/?(?![/]|proxy/\d+/)'
        content = re.sub(full_url_pattern, proxy_prefix.encode() + b'/', content)
    return content


def get_selected_backend(app_item, backends):
    if app_item.load_balancing_enabled:
        # Round-robin among online backends
        for i in range(len(backends)):
            idx = (app_item.last_backend_index + i) % len(backends)
            if backends[idx].is_online:
                selected_backend = backends[idx]
                app_item.last_backend_index = idx
                db.session.commit()
                return selected_backend
    else:
        # Use first online backend
        for b in backends:
            if b.is_online:
                return b
    return None


def handle_protocol_redirect(app_item, backends, path):
    selected_backend = backends[0]  # Default to first
    if app_item.load_balancing_enabled:
        idx = (app_item.last_backend_index + 1) % len(backends)
        selected_backend = backends[idx]
        app_item.last_backend_index = idx
        db.session.commit()

    backend_scheme = selected_backend.url.split('://')[0]
    if request.scheme != backend_scheme:
        return f"{selected_backend.url.rstrip('/')}/{path}"
    return None


def rewrite_location_header(value, proxy_prefix, selected_backend):
    if value.startswith('/'):
        if not value.startswith(f"{proxy_prefix}/"):
            value = f"{proxy_prefix}{value}"
    elif value.startswith(selected_backend.url.rstrip('/')):
        backend_url = selected_backend.url.rstrip('/')
        if not value.startswith(f"{backend_url}{proxy_prefix}/"):
            value = value.replace(backend_url, proxy_prefix, 1)
        else:
            value = value.replace(backend_url, "", 1)
    return value


def proxy(app_id, path):
    app_item = Application.query.get_or_404(app_id)
    backends = app_item.backends
    if not backends:
        return render_template('error.html', app_name=app_item.name, message="No backends configured"), 503

    redirect_url = handle_protocol_redirect(app_item, backends, path)
    if redirect_url:
        return redirect(redirect_url)

    selected_backend = get_selected_backend(app_item, backends)
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
                    value = rewrite_location_header(value, f"/proxy/{app_id}", selected_backend)
                headers.append((name, value))

        content = rewrite_content(resp.content, content_type, f"/proxy/{app_id}", selected_backend)

        return Response(content, resp.status_code, headers)
    except RequestException:
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
