import functools
from flask import session, redirect, url_for


def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('admin.admin_login'))
        return view(**kwargs)
    return wrapped_view
