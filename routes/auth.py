"""Auth routes — login/logout for KoSERI & FedKew staff."""
from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.security import check_password_hash
from models import db, User, AuditLog

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        if current_user.role == 'fedkew':
            return redirect(url_for('fedkew.dashboard'))
        elif current_user.role == 'koseri':
            return redirect(url_for('koseri.dashboard'))
        else:
            return redirect(url_for('fedkew.dashboard'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        user = User.query.filter_by(username=username).first()

        if user and check_password_hash(user.password, password):
            login_user(user)
            db.session.add(AuditLog(
                user_id=user.id,
                action='login',
                detail=f'{user.username} ({user.role})',
                ip_addr=request.remote_addr
            ))
            db.session.commit()
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            if user.role == 'fedkew':
                return redirect(url_for('fedkew.dashboard'))
            elif user.role == 'koseri':
                return redirect(url_for('koseri.dashboard'))
            else:
                return redirect(url_for('fedkew.dashboard'))
        flash('Nama pengguna atau kata laluan tidak sah.', 'danger')

    return render_template('login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    db.session.add(AuditLog(
        user_id=current_user.id,
        action='logout',
        detail=f'{current_user.username} ({current_user.role})',
        ip_addr=request.remote_addr
    ))
    db.session.commit()
    logout_user()
    flash('Anda telah log keluar.', 'info')
    return redirect(url_for('auth.login'))
