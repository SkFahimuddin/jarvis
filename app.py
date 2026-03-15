from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from groq import Groq
from dotenv import load_dotenv
import os
import sqlite3
import json
import re
from datetime import datetime, timedelta
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
    c.execute('''
        CREATE TABLE IF NOT EXISTS moments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            timestamp DATETIME NOT NULL,
            activity TEXT,
            location TEXT,
            mood TEXT,
            note TEXT,
            raw_text TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
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

# ── Moments DB helpers ─────────────────────────────────────────────────────────
def save_moment(user_id, timestamp, activity=None, location=None, mood=None, note=None, raw_text=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO moments (user_id, timestamp, activity, location, mood, note, raw_text) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, timestamp, activity, location, mood, note, raw_text)
    )
    conn.commit()
    conn.close()

def get_moments_in_range(user_id, start_dt, end_dt):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, activity, location, mood, note FROM moments WHERE user_id = ? AND timestamp BETWEEN ? AND ? ORDER BY timestamp ASC",
        (user_id, start_dt.isoformat(), end_dt.isoformat())
    )
    rows = c.fetchall()
    conn.close()
    return rows

def get_all_moments(user_id, limit=100):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "SELECT timestamp, activity, location, mood, note FROM moments WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
        (user_id, limit)
    )
    rows = c.fetchall()
    conn.close()
    return rows

def delete_all_moments(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM moments WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

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

def is_timeline_query(user_input):
    """Detect if the user is asking about their past moments/location/activity."""
    query_phrases = [
        "where was i", "what was i doing", "what did i do", "where were you",
        "what happened at", "show my timeline", "show timeline", "my timeline",
        "what were you doing", "show my day", "show my moments", "my moments",
        "yesterday at", "today at", "last night", "this morning", "this afternoon",
        "what time did i", "where i was", "when did i", "show me yesterday",
        "show me today", "show me my", "recap my day", "day recap",
        "log for", "moments for", "what was happening", "what happened today",
        "what happened yesterday"
    ]
    return any(phrase in user_input.lower() for phrase in query_phrases)

def is_explicit_log(user_input):
    """Detect explicit log commands like 'log: at the gym'"""
    return user_input.lower().startswith("log:") or user_input.lower().startswith("log ")

# ── AI moment extractor ────────────────────────────────────────────────────────
def extract_moment_from_text(text, current_time_str):
    """Use Groq to extract moment data from natural text."""
    prompt = f"""You are a data extractor. Given a user's message, extract life-log moment details.
Current time: {current_time_str}

Extract and return ONLY a valid JSON object with these fields (use null if not mentioned):
- activity: string (what they are doing, e.g. "eating lunch", "at the gym", "working")
- location: string (where they are, e.g. "office", "Pizza Hut", "home", "gym")
- mood: string (emotional state if mentioned, e.g. "happy", "tired", "excited")
- note: string (any extra details worth remembering)
- is_moment: boolean (true if this message describes a real-life activity/location/event, false if it's a question or command)

User message: "{text}"

Return ONLY the JSON object, no explanation, no markdown."""

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1
        )
        raw = response.choices[0].message.content.strip()
        # Strip markdown if present
        raw = re.sub(r'^```json\s*', '', raw)
        raw = re.sub(r'\s*```$', '', raw)
        data = json.loads(raw)
        return data
    except Exception as e:
        print("Moment extraction error:", e)
        return None

# ── Timeline query parser ──────────────────────────────────────────────────────
def parse_timeline_query(user_input, now):
    """Parse what time range the user is asking about."""
    text = user_input.lower()

    # Specific time mentions like "2pm yesterday", "at 3pm today"
    time_pattern = re.search(r'(\d{1,2})(?::(\d{2}))?\s*(am|pm)', text)
    
    today = now.date()
    yesterday = today - timedelta(days=1)

    if "yesterday" in text:
        base_date = yesterday
    elif "today" in text or "this morning" in text or "this afternoon" in text or "tonight" in text:
        base_date = today
    elif "last night" in text:
        base_date = yesterday
    else:
        base_date = today  # default to today

    if time_pattern:
        hour = int(time_pattern.group(1))
        minute = int(time_pattern.group(2)) if time_pattern.group(2) else 0
        period = time_pattern.group(3)
        if period == 'pm' and hour != 12:
            hour += 12
        elif period == 'am' and hour == 12:
            hour = 0
        point_time = datetime.combine(base_date, datetime.min.time().replace(hour=hour, minute=minute))
        # Return a 2-hour window around that time
        return point_time - timedelta(hours=1), point_time + timedelta(hours=1), f"around {time_pattern.group(0)}"
    elif "morning" in text:
        start = datetime.combine(base_date, datetime.min.time().replace(hour=5))
        end = datetime.combine(base_date, datetime.min.time().replace(hour=12))
        return start, end, "the morning"
    elif "afternoon" in text:
        start = datetime.combine(base_date, datetime.min.time().replace(hour=12))
        end = datetime.combine(base_date, datetime.min.time().replace(hour=18))
        return start, end, "the afternoon"
    elif "evening" in text or "night" in text:
        start = datetime.combine(base_date, datetime.min.time().replace(hour=18))
        end = datetime.combine(base_date, datetime.min.time().replace(hour=23, minute=59))
        return start, end, "the evening"
    else:
        # Full day
        start = datetime.combine(base_date, datetime.min.time())
        end = datetime.combine(base_date, datetime.min.time().replace(hour=23, minute=59, second=59))
        label = "yesterday" if base_date == yesterday else "today"
        return start, end, label

def format_moments_timeline(rows, period_label):
    """Format moments as a structured timeline string for JARVIS to return."""
    if not rows:
        return f"No moments logged for {period_label}."
    
    lines = [f"📅 TIMELINE — {period_label.upper()}"]
    lines.append("─" * 36)
    for row in rows:
        ts, activity, location, mood, note = row
        try:
            dt = datetime.fromisoformat(ts)
            time_str = dt.strftime("%I:%M %p")
        except:
            time_str = ts

        parts = [f"🕐 {time_str}"]
        if activity:
            parts.append(f"  ▸ {activity}")
        if location:
            parts.append(f"  📍 {location}")
        if mood:
            parts.append(f"  💭 Mood: {mood}")
        if note:
            parts.append(f"  📝 {note}")
        lines.append("\n".join(parts))
        lines.append("─" * 36)
    
    return "\n".join(lines)

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
    now = datetime.now()

    if not user_input:
        return jsonify({"response": "I didn't catch that. Could you try again?"})

    # ── Delete memory ──────────────────────────────────────────────────
    if is_delete_memory_request(user_input):
        delete_user_history(user_id)
        response_text = "Memory wiped. I have forgotten everything. Starting fresh."
        return jsonify({"response": response_text})

    # ── Creator / special Q ────────────────────────────────────────────
    if is_creator_question(user_input) or is_fahim_question(user_input):
        response_text = "My boss is Fahim. He is the brilliant mind who created me."
        save_message(user_id, "user", user_input)
        save_message(user_id, "assistant", response_text)
        return jsonify({"response": response_text})

    

    # ── Timeline query ─────────────────────────────────────────────────
    if is_timeline_query(user_input):
        start_dt, end_dt, period_label = parse_timeline_query(user_input, now)
        rows = get_moments_in_range(user_id, start_dt, end_dt)
        timeline_text = format_moments_timeline(rows, period_label)
        save_message(user_id, "user", user_input)
        save_message(user_id, "assistant", timeline_text)
        return jsonify({"response": timeline_text, "is_timeline": True})

    # ── Explicit log command ───────────────────────────────────────────
    if is_explicit_log(user_input):
        log_text = user_input[4:].strip() if user_input.lower().startswith("log:") else user_input[4:].strip()
        moment_data = extract_moment_from_text(log_text, now.strftime("%Y-%m-%d %H:%M"))
        if moment_data and moment_data.get("is_moment", True):
            save_moment(
                user_id=user_id,
                timestamp=now,
                activity=moment_data.get("activity"),
                location=moment_data.get("location"),
                mood=moment_data.get("mood"),
                note=moment_data.get("note"),
                raw_text=log_text
            )
            parts = ["✅ Moment logged!"]
            if moment_data.get("activity"): parts.append(f"Activity: {moment_data['activity']}")
            if moment_data.get("location"): parts.append(f"Location: {moment_data['location']}")
            if moment_data.get("mood"):     parts.append(f"Mood: {moment_data['mood']}")
            if moment_data.get("note"):     parts.append(f"Note: {moment_data['note']}")
            response_text = "\n".join(parts)
        else:
            response_text = "✅ Moment logged at " + now.strftime("%I:%M %p")
        save_message(user_id, "user", user_input)
        save_message(user_id, "assistant", response_text)
        return jsonify({"response": response_text})

    # ── Auto-detect moment from casual message ─────────────────────────
    moment_data = extract_moment_from_text(user_input, now.strftime("%Y-%m-%d %H:%M"))
    moment_logged = False
    if moment_data and moment_data.get("is_moment") is True:
        if moment_data.get("activity") or moment_data.get("location"):
            save_moment(
                user_id=user_id,
                timestamp=now,
                activity=moment_data.get("activity"),
                location=moment_data.get("location"),
                mood=moment_data.get("mood"),
                note=moment_data.get("note"),
                raw_text=user_input
            )
            moment_logged = True

    # ── Normal AI response ─────────────────────────────────────────────
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
                    + (f" Note: I just automatically logged this moment from the user's message." if moment_logged else "")
                )},
                *history
            ]
        )
        response_text = response.choices[0].message.content
        if moment_logged:
            response_text += "\n\n_(📍 Moment auto-logged)_"
        save_message(user_id, "assistant", response_text)
    except Exception as e:
        print("Error:", e)
        response_text = "Sorry, I encountered an error processing your request."

    return jsonify({"response": response_text, "moment_logged": moment_logged})

@app.route("/reset", methods=["POST"])
@login_required
def reset():
    delete_user_history(session['user_id'])
    return jsonify({"status": "ok", "message": "Memory cleared."})

@app.route("/moments", methods=["GET"])
@login_required
def get_moments():
    """Return all moments for the logged-in user as JSON (for the timeline panel)."""
    user_id = session['user_id']
    rows = get_all_moments(user_id, limit=200)
    moments = []
    for row in rows:
        ts, activity, location, mood, note = row
        try:
            dt = datetime.fromisoformat(ts)
            date_str = dt.strftime("%b %d, %Y")
            time_str = dt.strftime("%I:%M %p")
        except:
            date_str = ts
            time_str = ""
        moments.append({
            "timestamp": ts,
            "date": date_str,
            "time": time_str,
            "activity": activity,
            "location": location,
            "mood": mood,
            "note": note
        })
    return jsonify({"moments": moments})

@app.route("/moments/clear", methods=["POST"])
@login_required
def clear_moments():
    delete_all_moments(session['user_id'])
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(debug=True)