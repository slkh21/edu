from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    full_name = db.Column(db.String(120))
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='student')

class Topic(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)

class Video(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    url = db.Column(db.String(255))
    topic_id = db.Column(db.Integer, db.ForeignKey('topic.id'))
    topic = db.relationship('Topic', backref=db.backref('videos', lazy=True))

class Task(db.Model):
    __tablename__ = 'task'
    id             = db.Column(db.Integer, primary_key=True)
    topic_id       = db.Column(db.Integer, db.ForeignKey('topic.id'))
    question       = db.Column(db.String(300))
    option1        = db.Column(db.String(120))
    option2        = db.Column(db.String(120))
    option3        = db.Column(db.String(120))
    option4        = db.Column(db.String(120))
    correct_answer = db.Column(db.String(120))

    # ↓ Добавляем эту строку:
    topic = db.relationship(
        'Topic',
        backref=db.backref('tasks', lazy=True, cascade='all, delete-orphan')
    )


class UserVideoProgress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    video_id = db.Column(db.Integer, db.ForeignKey('video.id'))
    completed = db.Column(db.Boolean, default=False)

class UserTaskProgress(db.Model):
    __tablename__ = 'user_task_progress'
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id', ondelete='CASCADE'), nullable=False)
    task_id    = db.Column(db.Integer, db.ForeignKey('task.id', ondelete='CASCADE'), nullable=False)
    is_correct = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='task_progress', passive_deletes=True)
    task = db.relationship('Task', backref='user_progress', passive_deletes=True)