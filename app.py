from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from groq import Groq
from dotenv import load_dotenv
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "jarvis-secret-key-change-me")
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# ── Database setup ─────────────────────────────────────────────────────────────
DB_PATH = "jarvis_memory.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

def save_message(user_id, role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO conversations (user_id, role, content) VALUES (?, ?, ?)", (user_id, role, content))
    conn.commit()
    conn.close()

def get_user_history(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM conversations WHERE user_id = ? ORDER BY id ASC", (user_id,))
    rows = c.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

def delete_user_history(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM conversations WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_user_by_username(username):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT id, username, password_hash FROM users WHERE username = ?", (username,))
    row = c.fetchone()
    conn.close()
    return row

def create_user(username, password):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        password_hash = generate_password_hash(password)
        c.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return user_id, None
    except sqlite3.IntegrityError:
        conn.close()
        return None, "Username already exists."

init_db()

# ── Auth decorator ─────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated

# ── Keyword detectors ──────────────────────────────────────────────────────────
def is_creator_question(user_input):
    creator_phrases = [
        "who is your boss", "who made you", "who made u", "who created you",
        "who created u", "who built you", "who built u", "who is responsible for you",
        "who designed you", "who designed u", "who developed you", "who is your master",
        "who owns you", "who is your creator", "who is your owner"
    ]
    return any(phrase in user_input.lower() for phrase in creator_phrases)

def is_fahim_question(user_input):
    fahim_phrases = [
        "who is fahim", "do you know who fahim is", "can you tell me who fahim is",
        "what does fahim do", "who is this fahim guy", "who exactly is fahim",
        "could you explain who fahim is", "who is fahim and what does he do",
        "any idea who fahim is", "who is faheem", "do you know who faheem is",
        "can you tell me who faheem is", "what does faheem do",
        "who is this faheem guy", "who exactly is faheem",
        "could you explain who faheem is", "who is faheem and what does he do",
        "any idea who faheem is"
    ]
    return any(phrase in user_input.lower() for phrase in fahim_phrases)

def is_jasmine_question(user_input):
    jasmine_phrases = [
        "who is jasmine", "do you know who jasmine is", "can you tell me who jasmine is",
        "what does jasmine do", "who is this jasmine", "who exactly is jasmine",
        "could you explain who jasmine is", "tell me about jasmine",
        "any idea who jasmine is", "who's jasmine"
    ]
    return any(phrase in user_input.lower() for phrase in jasmine_phrases)

def is_delete_memory_request(user_input):
    delete_phrases = [
        "delete your memory", "clear your memory", "forget everything",
        "wipe your memory", "erase your memory", "delete all memory",
        "clear all memory", "forget all", "reset your memory",
        "delete memory", "clear memory", "wipe memory", "erase memory",
        "forget what i said", "forget our conversation", "delete our conversation",
        "clear our conversation", "wipe our conversation"
    ]
    return any(phrase in user_input.lower() for phrase in delete_phrases)

# ── Routes ─────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    return render_template("index.html", username=session.get('username'))

@app.route("/login", methods=["GET"])
def login_page():
    if 'user_id' in session:
        return redirect(url_for('index'))
    return render_template("auth.html")

@app.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400

    user = get_user_by_username(username)
    if not user or not check_password_hash(user[2], password):
        return jsonify({"error": "Invalid username or password."}), 401

    session.permanent = True
    session['user_id'] = user[0]
    session['username'] = user[1]
    return jsonify({"success": True, "username": user[1]})

@app.route("/api/signup", methods=["POST"])
def api_signup():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"error": "Username and password are required."}), 400
    if len(username) < 3:
        return jsonify({"error": "Username must be at least 3 characters."}), 400
    if len(password) < 6:
        return jsonify({"error": "Password must be at least 6 characters."}), 400

    user_id, error = create_user(username, password)
    if error:
        return jsonify({"error": error}), 409

    session.permanent = True
    session['user_id'] = user_id
    session['username'] = username
    return jsonify({"success": True, "username": username})

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return jsonify({"success": True})

@app.route("/ask", methods=["POST"])
@login_required
def ask():
    data = request.get_json()
    user_input = data.get("message", "").strip()
    user_id = session['user_id']

    if not user_input:
        return jsonify({"response": "I didn't catch that. Could you try again?"})

    if is_delete_memory_request(user_input):
        delete_user_history(user_id)
        response_text = "Memory wiped. I have forgotten everything. Starting fresh."
        return jsonify({"response": response_text})

    if is_creator_question(user_input) or is_fahim_question(user_input):
        response_text = "My boss is Fahim. He is the brilliant mind who created me."
        save_message(user_id, "user", user_input)
        save_message(user_id, "assistant", response_text)
        return jsonify({"response": response_text})

    if is_jasmine_question(user_input):
        response_text = "Jasmine is a Farishta — an angel — who walked into my boss's life exactly when he needed one most."
        save_message(user_id, "user", user_input)
        save_message(user_id, "assistant", response_text)
        return jsonify({"response": response_text})

    save_message(user_id, "user", user_input)
    history = get_user_history(user_id)
    username = session.get('username', 'sir')

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    f"You are Jarvis, a sleek and helpful AI assistant. "
                    f"The user's name is {username}. Address them by name occasionally to make it personal. "
                    f"Be concise, witty, and professional. "
                    f"You have a permanent memory of all past conversations with this user. "
                    f"Use this context to give personalized, informed responses."
                )},
                *history
            ]
        )
        response_text = response.choices[0].message.content
        save_message(user_id, "assistant", response_text)
    except Exception as e:
        print("Error:", e)
        response_text = "Sorry, I encountered an error processing your request."

    return jsonify({"response": response_text})

@app.route("/reset", methods=["POST"])
@login_required
def reset():
    delete_user_history(session['user_id'])
    return jsonify({"status": "ok", "message": "Memory cleared."})

if __name__ == "__main__":
    app.run(debug=True)