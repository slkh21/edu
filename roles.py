from models import db, User
from app import app

with app.app_context():
    user = User.query.filter_by(username='admin').first()
    if user:
        user.role = 'admin'
        db.session.commit()
        print('Роль изменена на "admin"')
