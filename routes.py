from flask import Blueprint, render_template
from models import Video, Task

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/videos')
def videos():
    all_videos = Video.query.all()
    return render_template('videos.html', videos=all_videos)

@main.route('/tasks')
def tasks():
    all_tasks = Task.query.all()
    return render_template('tasks.html', tasks=all_tasks)