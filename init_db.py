"""Initialize SSPS database with default users."""
from app import app
from models import db, User
from werkzeug.security import generate_password_hash

with app.app_context():
    db.create_all()

    # Default users
    users = [
        {'username': 'fedkew', 'password': 'ssps2026', 'role': 'fedkew', 'name': 'Pegawai FedKew'},
        {'username': 'koseri', 'password': 'ssps2026', 'role': 'koseri', 'name': 'Penasihat Syariah'},
        {'username': 'admin',  'password': 'ssps2026', 'role': 'admin',  'name': 'Administrator'},
    ]

    for u in users:
        existing = User.query.filter_by(username=u['username']).first()
        if not existing:
            user = User(
                username=u['username'],
                password=generate_password_hash(u['password']),
                role=u['role'],
                name=u['name'],
            )
            db.session.add(user)
            print(f"  Created: {u['username']} ({u['role']})")
        else:
            print(f"  Exists:  {u['username']} ({u['role']})")

    db.session.commit()
    print("✅ Database initialized successfully.")
