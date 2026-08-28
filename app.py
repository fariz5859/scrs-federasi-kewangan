"""SSPS — Shariah Compliance Review System v2.0."""
from flask import Flask
from flask_login import LoginManager
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from models import db, User
import os


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Fix for reverse proxy (Render.com HTTPS)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

    # Ensure directories exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    os.makedirs(os.path.join(app.instance_path), exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), 'reports'), exist_ok=True)

    # Init extensions
    db.init_app(app)
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Sila log masuk untuk mengakses halaman ini.'
    login_manager.login_message_category = 'warning'

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # Register blueprints (v2.0 — Koperasi portal removed)
    from routes.auth import auth_bp
    from routes.fedkew import fedkew_bp
    from routes.koseri import koseri_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(fedkew_bp, url_prefix='/fedkew')
    app.register_blueprint(koseri_bp, url_prefix='/koseri')

    # Root redirect
    @app.route('/')
    def index():
        from flask import redirect, url_for
        from flask_login import current_user
        if current_user.is_authenticated:
            if current_user.role == 'fedkew':
                return redirect(url_for('fedkew.dashboard'))
            elif current_user.role == 'koseri':
                return redirect(url_for('koseri.dashboard'))
            else:
                return redirect(url_for('fedkew.dashboard'))
        return redirect(url_for('auth.login'))

    # Context processors
    @app.context_processor
    def inject_globals():
        return {'app_name': 'SSPS', 'app_version': '2.0'}

    return app


app = create_app()

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)
