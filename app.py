from flask import Flask, render_template, request, jsonify, session
from groq import Groq
from dotenv import load_dotenv
import os
import sqlite3

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
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def save_message(role, content):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("INSERT INTO conversations (role, content) VALUES (?, ?)", (role, content))
    conn.commit()
    conn.close()

def get_all_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT role, content FROM conversations ORDER BY id ASC")
    rows = c.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

def delete_all_history():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("DELETE FROM conversations")
    conn.commit()
    conn.close()

# Initialize DB on startup
init_db()

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
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_input = data.get("message", "").strip()

    if not user_input:
        return jsonify({"response": "I didn't catch that. Could you try again?"})

    # Check if user wants to delete memory
    if is_delete_memory_request(user_input):
        delete_all_history()
        response_text = "Memory wiped. I have forgotten everything. Starting fresh."
        return jsonify({"response": response_text})

    if is_creator_question(user_input) or is_fahim_question(user_input):
        response_text = "My boss is Fahim. He is the brilliant mind who created me."
        save_message("user", user_input)
        save_message("assistant", response_text)
        return jsonify({"response": response_text})

    if is_jasmine_question(user_input):
        response_text = "Jasmine is a Farishta — an angel — who walked into my boss's life exactly when he needed one most."
        save_message("user", user_input)
        save_message("assistant", response_text)
        return jsonify({"response": response_text})

    # Save user message to permanent memory
    save_message("user", user_input)

    # Load full history from DB
    history = get_all_history()

    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {"role": "system", "content": (
                    "You are Jarvis, a sleek and helpful AI assistant. "
                    "Be concise, witty, and professional. "
                    "You have a permanent memory of all past conversations with the user. "
                    "Use this context to give personalized, informed responses."
                )},
                *history
            ]
        )
        response_text = response.choices[0].message.content

        # Save Jarvis reply to permanent memory
        save_message("assistant", response_text)

    except Exception as e:
        print("Error:", e)
        response_text = "Sorry, I encountered an error processing your request."

    return jsonify({"response": response_text})

@app.route("/reset", methods=["POST"])
def reset():
    delete_all_history()
    return jsonify({"status": "ok", "message": "Memory cleared."})

if __name__ == "__main__":
    app.run(debug=True)