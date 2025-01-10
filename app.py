import openai
import pyttsx3  # For text-to-speech (Jarvis voice)

# Initialize OpenAI API key
openai.api_key = "your-api-key"  # Replace with your API key

# Initialize text-to-speech engine
engine = pyttsx3.init()

# Function to make Jarvis speak
def speak(text):
    engine.say(text)
    engine.runAndWait()

# Function to check if the user input asks about Jarvis's creator or boss
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

# Function to interact with the OpenAI API (GPT-3.5 Turbo)
def ask_jarvis(user_input):
    # Check if the query asks about Jarvis's creator or boss
    if is_creator_question(user_input):
        response = "My boss is Fahim. Fahim is the one who made me."
    else:
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",  # Using GPT-3.5 Turbo
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

# Main function to run the assistant
def run_jarvis():
    speak("Hello, I am Jarvis. How can I assist you today?")
    
    while True:
        # Get user input (typing)
        user_input = input("You: ")
        
        # Handle exit command
        if "exit" in user_input.lower() or "quit" in user_input.lower():
            speak("Goodbye! Have a great day!")
            print("Jarvis: Goodbye!")
            break
        
        # Ask Jarvis (OpenAI API)
        answer = ask_jarvis(user_input)
        
        # Make Jarvis speak the answer
        speak(answer)

if __name__ == "__main__":
    run_jarvis()
