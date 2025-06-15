from models import db, User
from werkzeug.security import generate_password_hash
from flask import Flask

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here'

db.init_app(app)

with app.app_context():
    # Замените значения на нужные
    username = 'admin'
    email = 'salikh.2003@mail.ru'
    full_name = 'Администратор Системы'
    password = 'admin123'
    role = 'admin'

    existing_user = User.query.filter_by(username=username).first()
    if existing_user:
        print('Пользователь уже существует.')
    else:
        hashed_password = generate_password_hash(password)
        new_admin = User(
            username=username,
            email=email,
            full_name=full_name,
            password_hash=hashed_password,
            role=role
        )
        db.session.add(new_admin)
        db.session.commit()
        print('Администратор успешно создан.')
