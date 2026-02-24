from flask import Flask, render_template, request, jsonify
from groq import Groq
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

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

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/ask", methods=["POST"])
def ask():
    data = request.get_json()
    user_input = data.get("message", "").strip()

    if not user_input:
        return jsonify({"response": "I didn't catch that. Could you try again?"})

    if is_creator_question(user_input) or is_fahim_question(user_input):
        response_text = "My boss is Fahim. He is the brilliant mind who created me."
    elif is_jasmine_question(user_input):
        response_text = "Jasmine is a Farishta — an angel — who walked into my boss's life exactly when he needed one most."
    else:
        try:
            response = client.chat.completions.create(
                model="llama-3.3-70b-versatile",
                messages=[
                    {"role": "system", "content": "You are Jarvis, a sleek and helpful AI assistant. Be concise, witty, and professional."},
                    {"role": "user", "content": user_input},
                ]
            )
            response_text = response.choices[0].message.content
        except Exception as e:
            print("Error:", e)
            response_text = "Sorry, I encountered an error processing your request."

    return jsonify({"response": response_text})

if __name__ == "__main__":
    app.run(debug=True)