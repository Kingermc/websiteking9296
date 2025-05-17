from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
from datetime import datetime
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from flask_socketio import SocketIO, emit

app = Flask(__name__)
app.secret_key = "supersecretkey"

socketio = SocketIO(app)

DB_LOGIN = "giris.db"
DB_REGISTER = "kayit.db"

# --- Veritabanı başlangıcı ---
def init_db():
    # Giris.db
    conn = sqlite3.connect(DB_LOGIN)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        email TEXT,
        phone TEXT
    )''')
    # Mesajlar tablosu
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            message TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

    # Kayit.db (örnek başka bilgiler için)
    conn2 = sqlite3.connect(DB_REGISTER)
    cursor2 = conn2.cursor()
    cursor2.execute('''CREATE TABLE IF NOT EXISTS extra_info (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        email TEXT,
        phone TEXT
    )''')
    conn2.commit()
    conn2.close()

# --- E-posta gönderme ---
def send_verification_email(email):
    code = str(random.randint(100000, 999999))
    session['verification_code'] = code
    session['email'] = email

    message = MIMEMultipart()
    message['From'] = "wsiteverif@gmail.com"
    message['To'] = email
    message['Subject'] = "Doğrulama Kodunuz"
    
    body = f"Kodunuz: {code}"
    message.attach(MIMEText(body, 'plain', 'utf-8'))

    with smtplib.SMTP("smtp.gmail.com", 587) as server:
        server.starttls()
        server.login("wsiteverif@gmail.com", "vlos daev dvxr rquf")
        server.sendmail(message['From'], email, message.as_string())

# --- Anasayfa => login ---
@app.route('/')
def login_page():
    return redirect(url_for('login'))

# --- Giriş işlemi ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username_or_email = request.form.get('user_input')
        password = request.form.get('password')

        if not username_or_email or not password:
            return render_template('login.html', error="Tüm alanları doldurun")

        conn = sqlite3.connect(DB_LOGIN)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE (username=? OR email=?) AND password=?", 
                       (username_or_email, username_or_email, password))
        user = cursor.fetchone()
        conn.close()

        if user:
            session['username'] = user[1]
            return redirect(url_for('chat'))
        else:
            return render_template('login.html', error="Bilgiler yanlış")
    return render_template('login.html')

# --- Kayıt işlemi ---
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        email = request.form.get('email')
        phone = request.form.get('phone')

        if not username or not password or not email or not phone:
            return render_template('register.html', error="Tüm alanlar zorunludur.")

        send_verification_email(email)
        session['temp_user'] = {
            'username': username,
            'password': password,
            'email': email,
            'phone': phone
        }
        return redirect(url_for('verify'))
    return render_template('register.html')

# --- Doğrulama kodu ---
@app.route('/verify', methods=['GET', 'POST'])
def verify():
    if request.method == 'POST':
        code = request.form.get('verification_code')
        if code == session.get('verification_code'):
            temp_user = session.get('temp_user')
            if temp_user:
                try:
                    conn = sqlite3.connect(DB_LOGIN)
                    cursor = conn.cursor()
                    cursor.execute("INSERT INTO users (username, password, email, phone) VALUES (?, ?, ?, ?)",
                        (temp_user['username'], temp_user['password'], temp_user['email'], temp_user['phone']))
                    conn.commit()
                    conn.close()

                    conn2 = sqlite3.connect(DB_REGISTER)
                    cursor2 = conn2.cursor()
                    cursor2.execute("INSERT INTO extra_info (username, email, phone) VALUES (?, ?, ?)",
                        (temp_user['username'], temp_user['email'], temp_user['phone']))
                    conn2.commit()
                    conn2.close()

                    session.pop('temp_user', None)
                    session.pop('verification_code', None)
                    return redirect(url_for('login'))
                except Exception as e:
                    return render_template('verify.html', error="Kullanıcı kayıt hatası: " + str(e))
        else:
            return render_template('verify.html', error="Kod yanlış")
    return render_template('verify.html')

# --- Chat ekranı ---
@app.route('/chat')
def chat():
    if 'username' not in session:
        return redirect(url_for('login'))

    conn = sqlite3.connect(DB_LOGIN)
    cursor = conn.cursor()
    cursor.execute("SELECT username, message, timestamp FROM messages ORDER BY id ASC")
    messages = cursor.fetchall()
    conn.close()

    messages = [
        {'username': m[0], 'text': m[1], 'timestamp': m[2]}
        for m in messages
    ]

    return render_template('chat.html', username=session['username'], messages=messages, current_user=session['username'])

# --- SocketIO: Mesaj gönder ve anında ilet ---
@socketio.on('send_message')
def handle_send_message(data):
    if 'username' not in session:
        return

    username = session['username']
    message_text = data.get('message')
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Mesajı DB'ye kaydet
    conn = sqlite3.connect(DB_LOGIN)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (username, message, timestamp) VALUES (?, ?, ?)",
                   (username, message_text, timestamp))
    conn.commit()
    conn.close()

    # Mesajı tüm bağlı kullanıcılara gönder
    emit('receive_message', {
        'username': username,
        'text': message_text,
        'timestamp': timestamp
    }, broadcast=True)

# --- Çıkış ---
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

if __name__ == '__main__':
    init_db()
    socketio.run(app, debug=True)
