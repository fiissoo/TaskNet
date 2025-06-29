from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime, timedelta
import os

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.permanent_session_lifetime = timedelta(minutes=10)

UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    conn = sqlite3.connect('tasknest.db')
    conn.row_factory = sqlite3.Row
    return conn


@app.route('/Recent')
def recent():
    username = session.get('username')
    if not username:
        return redirect(url_for('sign_in'))

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT id, created_at, deadline, title, description, image
        FROM task
        WHERE author = ?
        ORDER BY datetime(created_at) DESC
    """, (username,))

    tasks = cursor.fetchall()
    conn.close()
    return render_template('recent.html', tasks=tasks)


@app.route('/')
def index():
    username = session.get('username')
    if not username:
        return render_template('index.html', total_tasks=0, completed_count=0, incomplete_count=0, overdue_count=0)

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM task WHERE author = ?", (username,))
    total_tasks = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM completed_task WHERE author = ?", (username,))
    completed_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM incomplete_task WHERE author = ?", (username,))
    incomplete_count = cursor.fetchone()[0]

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        SELECT created_at, deadline, title, description, image, author
        FROM task
        WHERE author = ? AND deadline < ? AND title NOT IN (
            SELECT title FROM completed_task WHERE author = ?
        )
    """, (username, now, username))

    overdue_tasks = cursor.fetchall()

    for task in overdue_tasks:
        title = task[2]
        cursor.execute("SELECT 1 FROM overdue_task WHERE title = ? AND author = ?", (title, username))
        exists = cursor.fetchone()
        if not exists:
            cursor.execute("""
                INSERT INTO overdue_task (created_at, deadline, title, description, image, author)
                VALUES (?, ?, ?, ?, ?, ?)
            """, task)

    cursor.execute("SELECT COUNT(*) FROM overdue_task WHERE author = ?", (username,))
    overdue_count = cursor.fetchone()[0]

    cursor.execute("SELECT title FROM task WHERE author = ?", (username,))
    tasks = [row[0] for row in cursor.fetchall()]

    conn.commit()
    conn.close()

    return render_template('index.html',
                           total_tasks=total_tasks,
                           completed_count=completed_count,
                           incomplete_count=incomplete_count,
                           overdue_count=overdue_count,
                           tasks=tasks)

@app.route('/sign_up', methods=['GET', 'POST'])
def sign_up():
    message = None

    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = sqlite3.connect('tasknest.db')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM user WHERE username = ?", (username,))
        existing_user = cursor.fetchone()

        if existing_user:
            message = "Username is already taken. Please choose another one."
            conn.close()
            return render_template('sign_up.html', message=message)

        cursor.execute("INSERT INTO user (username, password) VALUES (?, ?)", (username, password))
        conn.commit()
        conn.close()

        return redirect(url_for('sign_in'))

    return render_template('sign_up.html', message=message)

@app.route('/sign_in', methods=['GET', 'POST'])
def sign_in():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = get_db_connection()
        user = conn.execute("SELECT * FROM user WHERE username = ? AND password = ?", (username, password)).fetchone()
        conn.close()

        if user:
            session['username'] = username
            return redirect('/')
        else:
            return render_template("sign_in.html", message="Incorrect username or password.")

    return render_template("sign_in.html")

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('index'))

@app.route('/add_task', methods=['POST'])
def add_task():
    title = request.form['title']
    description = request.form['description']
    raw_deadline = request.form['deadline']
    deadline = datetime.strptime(raw_deadline, "%Y-%m-%dT%H:%M").strftime('%Y-%m-%d %H:%M:%S')
    author = session.get('username', 'anonymous')
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    image_file = request.files['image']
    image_path = None
    if image_file and image_file.filename != '':
        image_filename = datetime.now().strftime('%Y%m%d%H%M%S_') + image_file.filename
        image_path = os.path.join(app.config['UPLOAD_FOLDER'], image_filename)
        image_file.save(image_path)

    image_path = image_path.replace('\\', '/') if image_path else None

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO task (created_at, deadline, title, description, image, author, is_completed)
        VALUES (?, ?, ?, ?, ?, ?, 0)
    """, (created_at, deadline, title, description, image_path, author))
    conn.commit()
    conn.close()

    return redirect(url_for('index'))

@app.route('/task/notes', methods=['GET', 'POST'])
def add_note():
    username = session.get('username')
    if not username:
        return redirect(url_for('sign_in'))

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()

    if request.method == 'POST':
        title = request.form.get('task_title')
        note = request.form.get('note')
        cursor.execute("UPDATE task SET notes = ? WHERE title = ? AND author = ?", (note, title, username))
        conn.commit()
        conn.close()
        return redirect(url_for('index'))

    cursor.execute("SELECT title FROM task WHERE author = ?", (username,))
    tasks = [row[0] for row in cursor.fetchall()]
    conn.close()

    return render_template('notes.html', tasks=tasks)

@app.route('/task/<int:task_id>')
def view_task(task_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM task WHERE id = ?", (task_id,))
    row = cursor.fetchone()
    conn.close()

    if row:
        Task = {
            "id": row["id"],
            "title": row["title"],
            "short_description": row["description"][:100],
            "description": row["description"],
            "imageURL": row["image"],
            "author": row["author"],
            "note": row["notes"] or "",
            "is_completed": row["is_completed"]
        }
        return render_template('show_tasks.html', Task=Task)

    return "Task not found", 404

@app.route('/tasks/upcomming')
def upccomming():
    username = session.get('username')
    if not username:
        return redirect(url_for('sign_in'))

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()

    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("""
        SELECT title, description, deadline, image, id
        FROM task
        WHERE author = ? AND deadline >= ? AND is_completed = 0
        ORDER BY deadline ASC
    """, (username, now))

    tasks = cursor.fetchall()
    conn.close()

    return render_template('upcomming_tasks.html', tasks=tasks)

@app.route('/task/<int:task_id>/complete', methods=['POST'])
def complete_task(task_id):
    username = session.get('username')
    if not username:
        return redirect(url_for('sign_in'))

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM task WHERE id = ? AND author = ?", (task_id, username))
    task = cursor.fetchone()

    if task:
        cursor.execute("""
            INSERT INTO completed_task (created_at, deadline, title, description, image, author)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (task['created_at'], task['deadline'], task['title'], task['description'], task['image'], task['author']))

        cursor.execute("DELETE FROM task WHERE id = ?", (task_id,))
        conn.commit()

    conn.close()
    return redirect(url_for('completed_tasks'))

@app.route('/tasks/completed')
def completed_tasks():
    username = session.get('username')
    if not username:
        return redirect(url_for('sign_in'))

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT created_at, deadline, title, description, image
        FROM completed_task
        WHERE author = ?
        ORDER BY deadline DESC
    """, (username,))
    tasks = cursor.fetchall()
    conn.close()

    return render_template('completed_tasks.html', tasks=tasks)

@app.route('/undo_completed/<string:title>', methods=['POST'])
def undo_completed(title):
    username = session.get('username')
    if not username:
        return redirect(url_for('sign_in'))

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()

    cursor.execute("""
        SELECT created_at, deadline, title, description, image
        FROM completed_task WHERE title = ? AND author = ?
    """, (title, username))
    task = cursor.fetchone()

    if task:
        cursor.execute("""
            INSERT INTO task (created_at, deadline, title, description, image, author, is_completed)
            VALUES (?, ?, ?, ?, ?, ?, 0)
        """, (task[0], task[1], task[2], task[3], task[4], username))

        cursor.execute("DELETE FROM completed_task WHERE title = ? AND author = ?", (title, username))
        conn.commit()

    conn.close()
    return redirect(url_for('completed_tasks'))

@app.route('/delete_completed/<string:title>', methods=['POST'])
def delete_completed(title):
    username = session.get('username')
    if not username:
        return redirect(url_for('sign_in'))

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM completed_task WHERE title = ? AND author = ?", (title, username))
    conn.commit()
    conn.close()

    return redirect(url_for('completed_tasks'))

@app.route('/completed/<string:title>')
def view_completed_task(title):
    username = session.get('username')
    if not username:
        return redirect(url_for('sign_in'))

    conn = sqlite3.connect('tasknest.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT created_at, deadline, title, description, image
        FROM completed_task
        WHERE title = ? AND author = ?
    """, (title, username))
    task = cursor.fetchone()
    conn.close()

    if task:
        return render_template('view_completed_task.html', task=task)

    return "Completed task not found", 404

@app.route('/add/tasks')
def add_tasks():
    return render_template('add_tasks.html')

if __name__ == '__main__':
    app.run(debug=True)
