from flask import Flask, send_file, request, redirect, session
import uuid
import qrcode
from datetime import datetime, timedelta
import sqlite3

app = Flask(__name__)
app.secret_key = "secret123"

current_token = None
expiry_time = None

# ---------------- DATABASE ---------------- #

def init_db():
    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()

    # users table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            password TEXT,
            role TEXT
        )
    ''')

    # attendance table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            timestamp TEXT
        )
    ''')

    # default users
    cursor.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (1, 'teacher', '123', 'teacher')")
    cursor.execute("INSERT OR IGNORE INTO users (id, username, password, role) VALUES (2, 'student', '123', 'student')")

    conn.commit()
    conn.close()

# ---------------- LOGIN ---------------- #

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM users WHERE username=? AND password=?", (username, password))
        user = cursor.fetchone()

        conn.close()

        if user:
            session['user'] = user[1]
            session['role'] = user[3]

            if user[3] == 'teacher':
                return redirect('/generate')
            else:
                return redirect('/scan')
        else:
            return "❌ Invalid Login"

    return '''
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <div class="container mt-5 text-center">
        <h2>Login</h2>
        <form method="post" class="mt-4">
            <input class="form-control mb-3" name="username" placeholder="Username">
            <input class="form-control mb-3" name="password" type="password" placeholder="Password">
            <button class="btn btn-primary">Login</button>
        </form>

        <p class="mt-3">Teacher: teacher / 123</p>
        <p>Student: student / 123</p>
    </div>
    '''

# ---------------- GENERATE QR (Teacher) ---------------- #

from io import BytesIO
import base64

@app.route('/generate')
def generate_qr():
    global current_token, expiry_time

    current_token = str(uuid.uuid4())
    expiry_time = datetime.now() + timedelta(seconds=60)

    img = qrcode.make(current_token)

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    img_str = base64.b64encode(buffer.getvalue()).decode()

    return f"""
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <div class="container text-center mt-5">
        <h2>QR Code Generated</h2>
        <p><b>Token:</b> {current_token}</p>
        <p class="text-danger">Valid for 60 seconds</p>

        <img src="data:image/png;base64,{img_str}" style="max-width:300px;"><br><br>

        <a href="/" class="btn btn-secondary">Back</a>
    </div>
    """

# ---------------- SCAN (Student) ---------------- #

@app.route('/scan')
def scan():
    if session.get('role') != 'student':
        return "❌ Access Denied"

    return '''
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">

    <div class="container text-center mt-5">
        <h2>Scan QR Code</h2>
        <div id="reader" style="width:300px;margin:auto;"></div>
    </div>

    <form id="form" method="POST" action="/mark">
        <input type="hidden" name="token" id="token">
    </form>

    <script src="https://unpkg.com/html5-qrcode"></script>

    <script>
    function onScanSuccess(decodedText) {
        document.getElementById("token").value = decodedText;
        document.getElementById("form").submit();
    }

    let scanner = new Html5QrcodeScanner("reader", { fps: 10, qrbox: 250 });
    scanner.render(onScanSuccess);
    </script>
    '''

# ---------------- MARK ---------------- #

@app.route('/mark', methods=['POST'])
def mark():
    name = session.get('user')
    user_token = request.form['token']

    global current_token, expiry_time

    if user_token == current_token and datetime.now() <= expiry_time:

        conn = sqlite3.connect('attendance.db')
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM attendance WHERE name=?", (name,))
        if cursor.fetchone():
            conn.close()
            return "❌ Already Marked"

        cursor.execute("INSERT INTO attendance (name, timestamp) VALUES (?, ?)",
                       (name, str(datetime.now())))

        conn.commit()
        conn.close()

        return "✅ Attendance Marked"

    return "❌ Invalid or Expired"

# ---------------- HISTORY ---------------- #

@app.route('/history')
def history():
    if session.get('role') != 'teacher':
        return "❌ Access Denied"

    conn = sqlite3.connect('attendance.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM attendance")
    data = cursor.fetchall()
    conn.close()

    html = "<h2>Attendance</h2><table border=1>"
    for row in data:
        html += f"<tr><td>{row[1]}</td><td>{row[2]}</td></tr>"
    html += "</table>"

    return html

# ---------------- START ---------------- #

if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=10000)
