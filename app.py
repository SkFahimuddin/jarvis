import openai
import pyttsx3  # For text-to-speech (Jarvis voice)
import speech_recognition as sr  # For speech recognition

# Initialize OpenAI API key
openai.api_key = "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"  # Replace with your API key

# Initialize text-to-speech engine
engine = pyttsx3.init()

# Initialize speech recognizer
recognizer = sr.Recognizer()

def speak(text):
    engine.say(text)
    engine.runAndWait()

def is_creator_question(user_input):
    creator_phrases = [
        "who is your boss",
        "who made you",
        "who made u",
        "who created you",
        "who created u",
        "who built you",
        "who built u",
        "who is responsible for you",
        "who designed you",
        "who designed u",
        "who developed you",
        "who is your master",
        "who owns you",
        "who is your creator",
        "who is your owner"
    ]
    return any(phrase in user_input.lower() for phrase in creator_phrases)

def fahim(user_input):
    fahim_phrases = [
        "Who is Fahim?",  
        "Do you know who Fahim is?",  
        "Can you tell me who Fahim is?",  
        "What does Fahim do?",  
        "Who is this Fahim guy?",  
        "Who exactly is Fahim?",  
        "Could you explain who Fahim is?",  
        "Who is Fahim, and what does he do?",  
        "I’ve heard of Fahim, but who is he?",  
        "Any idea who Fahim is?",  
        "who is fahim",  
        "do you know who fahim is",  
        "can you tell me who fahim is",  
        "what does fahim do",  
        "who is this fahim guy",  
        "who exactly is fahim",  
        "could you explain who fahim is",  
        "who is fahim and what does he do",  
        "i’ve heard of fahim but who is he",  
        "any idea who fahim is" 
        
        "Who is Faheem?",  
        "Do you know who Faheem is?",  
        "Can you tell me who Faheem is?",  
        "What does Faheem do?",  
        "Who is this Faheem guy?",  
        "Who exactly is Faheem?",  
        "Could you explain who Faheem is?",  
        "Who is Faheem, and what does he do?",  
        "I’ve heard of Faheem, but who is he?",  
        "Any idea who Faheem is?",  
        "who is faheem",  
        "do you know who faheem is",  
        "can you tell me who faheem is",  
        "what does faheem do",  
        "who is this faheem guy",  
        "who exactly is faheem",  
        "could you explain who faheem is",  
        "who is faheem and what does he do",  
        "i’ve heard of faheem but who is he",  
        "any idea who faheem is"
    ]
    return any(phrase in user_input.lower() for phrase in fahim_phrases)

def ask_jarvis(user_input):
    if is_creator_question(user_input) or fahim(user_input):
        response = "My boss is Fahim. Fahim is the one who made me."
    else:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are Jarvis, a helpful AI assistant."},
                    {"role": "user", "content": user_input},
                ]
            )
            response = response['choices'][0]['message']['content']
        except Exception as e:
            print("Error:", e)
            response = "Sorry, I couldn't process that request."
    
    print(f"Jarvis: {response}")
    return response

def get_speech_input():
    with sr.Microphone() as source:
        print("Listening...")
        recognizer.adjust_for_ambient_noise(source)
        try:
            audio = recognizer.listen(source)
            text = recognizer.recognize_google(audio)
            print(f"You (voice): {text}")
            return text
        except sr.UnknownValueError:
            print("Sorry, I couldn't understand. Please try again.")
            return ""
        except sr.RequestError:
            print("Speech recognition service is unavailable.")
            return ""

def run_jarvis():
    mode = input("Choose input mode - 'speak' or 'type': ").strip().lower()
    while mode not in ["speak", "type"]:
        mode = input("Invalid choice. Please type 'speak' or 'type': ").strip().lower()
    
    speak("Hello, I am Jarvis. How can I assist you today?")
    
    while True:
        if mode == "speak":
            user_input = get_speech_input()
            if user_input.lower() in ["exit", "quit"]:
                speak("Goodbye! Have a great day!")
                print("Jarvis: Goodbye!")
                break
        else:
            user_input = input("You: ")
            if user_input.lower() in ["exit", "quit"]:
                speak("Goodbye! Have a great day!")
                print("Jarvis: Goodbye!")
                break
        
        if user_input:
            answer = ask_jarvis(user_input)
            speak(answer)

if __name__ == "__main__":
    run_jarvis()
