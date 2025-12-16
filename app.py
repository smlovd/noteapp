import os
import sys
import sqlite3
from datetime import datetime, timedelta
from flask import Flask, render_template, redirect, url_for, request, flash, session, abort
from flask_wtf import CSRFProtect
from models import db, Note, User
from forms import NoteForm, LoginForm, RegisterForm
from dotenv import load_dotenv
from waitress import serve
import urllib.parse

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'supersecret')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SECURE'] = False
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

PG_USER = urllib.parse.quote_plus(os.getenv('PG_USER', 'postgres'))
PG_PASSWORD = urllib.parse.quote_plus(os.getenv('PG_PASSWORD', 'qwerty123'))
PG_HOST = os.getenv('PG_HOST', '127.0.0.1')
PG_PORT = os.getenv('PG_PORT', '5432')
PG_DB = urllib.parse.quote_plus(os.getenv('PG_DB', 'noteapp_db'))

app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"postgresql+psycopg2://{PG_USER}:{PG_PASSWORD}@{PG_HOST}:{PG_PORT}/{PG_DB}"
)

db.init_app(app)
csrf = CSRFProtect(app)

def get_raw_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

@app.after_request
def set_security_headers(response):
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = "default-src 'self'"
    response.headers['Server'] = 'SecureApp'
    return response

@app.cli.command('init-db')
def init_db_command():
    with app.app_context():
        db.drop_all()
        db.create_all()

        admin = User(username='admin', password='admin123')
        user = User(username='user', password='password')
        db.session.add_all([admin, user])
        db.session.commit()

        n1 = Note(title='Публичная заметка', content='Эта заметка принадлежит admin', owner_id=1)
        db.session.add(n1)
        db.session.commit()

        print('DB initialized for PostgreSQL.')

@app.route('/')
def index():
    notes = Note.query.order_by(Note.created_at.desc()).all()
    form = NoteForm()
    return render_template('index.html', notes=notes, form=form)

@app.route('/create', methods=['POST'])
def create_note():
    if 'user_id' not in session:
        flash('Требуется вход', 'warning')
        return redirect(url_for('login'))

    form = NoteForm()
    if form.validate_on_submit():
        note = Note(
            title=form.title.data,
            content=form.content.data,
            owner_id=session['user_id']
        )
        db.session.add(note)
        db.session.commit()
        flash('Заметка создана', 'success')
    return redirect(url_for('index'))

@app.route('/delete/<int:note_id>', methods=['POST'])
def delete_note(note_id):
    if 'user_id' not in session:
        abort(403)

    note = Note.query.get_or_404(note_id)

    if note.owner_id != session['user_id']:
        abort(403)

    db.session.delete(note)
    db.session.commit()
    flash('Заметка удалена', 'success')
    return redirect(url_for('index'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = User.query.filter_by(
            username=username,
            password=password
        ).first()

        if user:
            session['user_id'] = user.id
            session['username'] = user.username
            flash('Вход выполнен', 'success')
            return redirect(url_for('index'))

        flash('Неверные данные', 'danger')
        return redirect(url_for('login'))

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data

        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            flash('Пользователь уже существует', 'warning')
            return render_template('register.html', form=form)

        user = User(username=username, password=password)
        db.session.add(user)
        db.session.commit()

        flash('Регистрация успешна', 'success')
        return redirect(url_for('login'))

    return render_template('register.html', form=form)

@app.route('/logout')
def logout():
    session.clear()
    flash('Выход выполнен', 'info')
    return redirect(url_for('index'))

if __name__ == '__main__':
    
