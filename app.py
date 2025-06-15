from flask import Flask, render_template, request, redirect, url_for, session, flash, abort
from models import db, User, Video, Task, Topic, UserVideoProgress, UserTaskProgress
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from flask_mail import Mail, Message
from flask_migrate import Migrate
from functools import wraps
from collections import defaultdict
import os
from datetime import datetime
import logging
from sqlalchemy.orm import joinedload
from sqlalchemy import event, delete
from sqlite3 import Connection as SQLite3Connection


logging.basicConfig(level=logging.INFO)
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'your_secret_key_here'

# Email config
app.config['MAIL_SERVER'] = 'smtp.mail.ru'
app.config['MAIL_PORT'] = 465
app.config['MAIL_USE_SSL'] = True
app.config['MAIL_USERNAME'] = 'edu_math@mail.ru'
app.config['MAIL_PASSWORD'] = 'gGcfCwtXHSAXwhMikvWh'

mail = Mail(app)
db.init_app(app)
migrate = Migrate(app, db)

with app.app_context():
    @event.listens_for(db.engine, "connect")
    def _on_connect(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON;")
        cursor.close()


# ------------------ Декораторы ------------------

def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            flash('Войдите в систему.', 'warning')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return wrapper

def roles_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            if 'role' not in session or session.get('role') not in roles:
                flash('У вас нет доступа к этой странице.', 'danger')
                return redirect(url_for('index'))
            return f(*args, **kwargs)
        return wrapper
    return decorator

# ------------------ Аутентификация ------------------

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        full_name = request.form['full_name']
        password = request.form['password']

        if User.query.filter((User.username == username) | (User.email == email)).first():
            flash('Пользователь с таким именем или email уже существует', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password)
        user = User(username=username, email=email, full_name=full_name, password_hash=hashed_password)
        db.session.add(user)
        db.session.commit()
        flash('Регистрация успешна. Войдите в систему.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.password_hash, password):
            session['user_id'] = user.id
            session['username'] = user.username
            session['role'] = user.role
            session['full_name'] = user.full_name
            flash('Вы вошли в систему.', 'success')
            return redirect(url_for('index'))
        flash('Неверный логин или пароль.', 'danger')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ------------------ Основное ------------------

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/course')
@login_required
def course():
    topics = Topic.query.order_by(Topic.id).all()
    videos = Video.query.order_by(Video.id).all()
    return render_template('course.html', topics=topics, videos=videos)

@app.route('/tasks')
@login_required
def tasks():
    topics = Topic.query.options(db.joinedload(Topic.tasks)).all()
    # просто вывод, без результатов
    return render_template('tasks.html', topics=topics, submitted=False)

@app.route('/tasks/check', methods=['POST'])
@login_required
def check_tasks():
    user_id = session['user_id']
    topic_id = int(request.form['topic_id'])
    tasks = Task.query.filter_by(topic_id=topic_id).all()

    answers: dict[int, str] = {}
    results: dict[int, bool] = {}

    for task in tasks:
        form_key = f"task_{task.id}"
        if form_key in request.form:
            selected = request.form[form_key]
            answers[task.id] = selected
            correct = (selected == task.correct_answer)
            results[task.id] = correct

            # ‑- сохраняем / обновляем прогресс ‑-
            progress = (UserTaskProgress
                        .query.filter_by(user_id=user_id, task_id=task.id)
                        .first())
            if not progress:
                progress = UserTaskProgress(user_id=user_id,
                                            task_id=task.id,
                                            is_correct=correct)
                db.session.add(progress)
            else:
                progress.is_correct = correct
            logging.info('SAVE progress: user=%s task=%s correct=%s',
                     user_id, task.id, correct)
    db.session.commit()

    # Загружаем все темы, чтобы отобразить страницу целиком
    topics = Topic.query.options(db.joinedload(Topic.tasks)).all()
    flash('Ответы проверены ✔️', 'success')
    return render_template('tasks.html',
                           topics=topics,
                           submitted=True,
                           answers=answers,
                           results=results)

@app.route('/topic_tasks/<int:topic_id>', methods=['GET', 'POST'])
@login_required
def topic_tasks(topic_id):
    topic = Topic.query.get_or_404(topic_id)
    tasks = Task.query.filter_by(topic_id=topic_id).all()
    user_id = session['user_id']

    if request.method == 'POST':
        user_answers = {}
        results = {}
        for task in tasks:
            selected = request.form.get(f'task_{task.id}')
            if selected:
                correct = (selected == task.correct_answer)
                user_answers[task.id] = selected
                results[task.id] = correct

                existing = UserTaskProgress.query.filter_by(user_id=user_id, task_id=task.id).first()
                if not existing:
                    progress = UserTaskProgress(user_id=user_id, task_id=task.id, is_correct=correct)
                    db.session.add(progress)
                else:
                    existing.is_correct = correct
        db.session.commit()
        flash('Ответы отправлены.', 'success')
        return render_template('tasks.html', topic=topic, tasks=tasks, results=results, user_answers=user_answers)

    return render_template('tasks.html', topic=topic, tasks=tasks)

@app.route('/admin/users/delete/<int:user_id>', methods=['POST'])
@login_required
@roles_required('admin')
def delete_user(user_id):
    # Нельзя удалить самого себя
    if session['user_id'] == user_id:
        flash('Нельзя удалить свою учётную запись.', 'warning')
        return redirect(url_for('manage_users'))

    user = User.query.get_or_404(user_id)
    # здесь можно добавить проверку, чтобы не удалять учителей и т.п.
    db.session.delete(user)
    db.session.commit()
    flash(f'Пользователь "{user.username}" удалён.', 'success')
    return redirect(url_for('manage_users'))

# ------------------ Прогресс ------------------

from flask import request, abort, render_template, session
from sqlalchemy.orm import joinedload
from collections import defaultdict
# импорт моделей
from models import User, Topic, Task, UserTaskProgress

@app.route('/progress')
@login_required
def progress():
    current_role = session.get('role')
    current_id   = session['user_id']

    student_id = request.args.get('student', type=int)
    # → определяем, чей прогресс показываем
    if current_role == 'student':
        student_id = current_id
    elif current_role in ('teacher', 'admin'):
        if student_id is None:
            students = User.query.filter_by(role='student').order_by(User.full_name).all()
            return render_template('progress_teacher_list.html', students=students)
        student = User.query.get_or_404(student_id)
        if student.role != 'student':
            abort(404)
    else:
        abort(403)

    user = User.query.get_or_404(student_id)

    # ——————————————————————————————
    # 2. Выбираем прогресс, отбрасывая "пустышки"
    # ——————————————————————————————
    progresses = (
      UserTaskProgress.query
      .join(Task)  # гарантируем, что task не None
      .filter(UserTaskProgress.user_id == student_id)
      .options(
        joinedload(UserTaskProgress.task)
        .joinedload(Task.topic)
      )
      .all()
    )

    # ——————————————————————————————
    # 3. Группируем, пропуская отсутствующие topic
    # ——————————————————————————————
    progress_by_topic = defaultdict(list)
    for p in progresses:
        # пропускаем, если нет задания или темы
        if p.task is None or p.task.topic is None:
            continue
        topic_title = p.task.topic.title
        progress_by_topic[topic_title].append(p)

    # ——————————————————————————————
    # 4. Считаем статистику по всем темам
    # ——————————————————————————————
    topic_stats = []
    for t in Topic.query.order_by(Topic.title).all():
        total   = len(t.tasks)  # все задания темы
        correct = sum(1 for p in progress_by_topic.get(t.title, [])
                      if p.is_correct)
        pct     = round(correct / total * 100) if total else 0
        topic_stats.append({
            'title':   t.title,
            'total':   total,
            'correct': correct,
            'percent': pct
        })

    # ——————————————————————————————
    # 5. Рендерим разный шаблон для студента/учителя
    # ——————————————————————————————
    template = ('progress_student.html'
                if current_role == 'student'
                else 'student_progress_detail.html')

    return render_template(
        template,
        user=user,
        progress_by_topic=progress_by_topic,
        topic_stats=topic_stats
    )

# ------------------ Управление курсом ------------------

@app.route('/manage_videos', methods=['GET', 'POST'])
@login_required
@roles_required('teacher', 'admin')
def manage_videos():
    topics = Topic.query.order_by(Topic.id).all()
    videos = Video.query.order_by(Video.id).all()

    if request.method == 'POST':
        # 1) Удаление видео
        if 'delete_video' in request.form:
            vid = int(request.form['delete_video'])
            video = Video.query.get_or_404(vid)
            title = video.title
            # Удалить файл (опционально)
            # filepath = video.url.replace('/static/', '')
            # os.remove(os.path.join(app.root_path, 'static', filepath))
            db.session.delete(video)
            db.session.commit()
            flash(f'Видео «{title}» удалено.', 'success')
            return redirect(url_for('manage_videos'))

        # 2) Удаление темы
        if 'delete_topic' in request.form:
            tid = int(request.form['delete_topic'])
            topic = Topic.query.get_or_404(tid)
            ttitle = topic.title
            # Удаляем: видео и задания, связанные через ON DELETE CASCADE или ручками
            db.session.delete(topic)
            db.session.commit()
            flash(f'Тема «{ttitle}» и все её видео удалены.', 'success')
            return redirect(url_for('manage_videos'))

        # 3) Добавление видео (и/или новой темы)
        if 'add_video' in request.form:
            title       = request.form['title']
            description = request.form.get('description', '')
            topic_id    = request.form.get('topic_id')
            new_topic   = request.form.get('new_topic')

            # Создаём новую тему, если нужно
            if new_topic:
                topic = Topic(title=new_topic)
                db.session.add(topic)
                db.session.commit()
                topic_id = topic.id

            # Загружаем видеофайл
            file = request.files.get('video_file')
            if file and file.filename.lower().endswith('.mp4'):
                filename = secure_filename(file.filename)
                path = os.path.join(app.root_path, 'static/videos')
                os.makedirs(path, exist_ok=True)
                filepath = os.path.join(path, filename)
                file.save(filepath)

                video_url = url_for('static', filename=f'videos/{filename}')
                video = Video(
                    title=title,
                    description=description,
                    url=video_url,
                    topic_id=topic_id
                )
                db.session.add(video)
                db.session.commit()
                flash('Видео загружено.', 'success')
                return redirect(url_for('manage_videos'))

            flash('Ошибка при загрузке видео. Проверьте формат .mp4.', 'danger')

    return render_template('manage_videos.html',
                           topics=topics,
                           videos=videos)

@app.route('/manage_tasks', methods=['GET', 'POST'])
@login_required
@roles_required('teacher', 'admin')
def manage_tasks():
    topics = Topic.query.order_by(Topic.title).all()

    # ── 1. Добавление новой задачи ───────────────────────────────
    if request.method == 'POST' and 'add_task' in request.form:
        topic_id = request.form['topic_id']
        question = request.form['question']
        options  = request.form.getlist('options[]')   # ["A","B","C","D"]
        correct  = request.form['correct']

        # валидация
        if len(options) != 4:
            flash('Нужно указать ровно 4 варианта ответа.', 'danger')
            return redirect(url_for('manage_tasks'))

        if correct not in options:
            flash('Правильный ответ должен совпадать с одним из вариантов.', 'danger')
            return redirect(url_for('manage_tasks'))

        task = Task(
            topic_id       = topic_id,
            question       = question,
            option1        = options[0],
            option2        = options[1],
            option3        = options[2],
            option4        = options[3],
            correct_answer = correct
        )
        db.session.add(task)
        db.session.commit()
        flash('Задание успешно добавлено.', 'success')
        return redirect(url_for('manage_tasks'))

    # ── 2. Удаление задачи + зачистка прогресса ──────────────────
    if request.method == 'POST' and 'delete_task' in request.form:
        task_id = int(request.form['delete_task'])

        # удаляем все записи прогресса по этой задаче
        UserTaskProgress.query.filter_by(task_id=task_id).delete()

        # удаляем саму задачу
        task = Task.query.get_or_404(task_id)
        db.session.delete(task)
        db.session.commit()

        flash(f'Задание #{task_id} удалено вместе с прогрессом студентов.', 'success')
        return redirect(url_for('manage_tasks'))

    # ── 3. Отображение страницы ──────────────────────────────────
    tasks = Task.query.order_by(Task.id).all()
    return render_template('manage_tasks.html', topics=topics, tasks=tasks)

# ------------------ Админ ------------------

@app.route('/admin/users', methods=['GET', 'POST'])
@login_required
@roles_required('admin')
def manage_users():
    users = User.query.all()

    if request.method == 'POST':
        action  = request.form.get('action')
        user_id = int(request.form.get('user_id', 0))
        user    = User.query.get_or_404(user_id)

        # Запрещаем удалять самого себя
        if action == 'delete_user':
            if session['user_id'] == user_id:
                flash('Нельзя удалить свою учётную запись.', 'warning')
            else:
                db.session.delete(user)
                db.session.commit()
                flash(f'Пользователь {user.username} удалён.', 'success')

        elif action == 'change_role':
            new_role = request.form.get('new_role')
            if new_role not in ('student','teacher','admin'):
                flash('Недопустимая роль.', 'danger')
            else:
                user.role = new_role
                db.session.commit()
                flash(f'Роль пользователя {user.username} изменена на {new_role}.', 'success')

        return redirect(url_for('manage_users'))

    return render_template('admin_users.html', users=users)

@app.route('/student/<int:student_id>/progress')
@login_required
@roles_required('teacher', 'admin')
def student_progress_detail(student_id):
    student = User.query.get_or_404(student_id)
    # берём только «реально присвоенные» значения
    progresses = (UserTaskProgress
                 .query
                 .filter_by(user_id=student_id)
                 .filter(UserTaskProgress.is_correct.isnot(None))
                 .all())

    from collections import defaultdict
    progress_by_topic = defaultdict(list)
    for p in progresses:
        title = p.task.topic.title if p.task and p.task.topic else 'Без темы'
        progress_by_topic[title].append(p)

    return render_template(
        'student_progress_detail.html',
        student=student,
        progress_by_topic=progress_by_topic
    )



@app.context_processor
def inject_now():
    return {'now': datetime.utcnow}

# ------------------ Запуск ------------------

if __name__ == '__main__':
    app.run(debug=True)
