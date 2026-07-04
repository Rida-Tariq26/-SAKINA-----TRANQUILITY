import os
from dotenv import load_dotenv
# Replace this import with the specific class from your 'google-adk' if different
from google import genai 

# Load environment variables from .env
load_dotenv()

def main():
    # Initialize the client (it automatically picks up GEMINI_API_KEY from the environment)
    client = genai.Client()
    
    print("Testing connection to Gemini...")
    
    # Generate a simple response
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents='Hello! Confirming that our connection is successful.',
    )
    
    print("\n--- Agent Response ---")
    print(response.text)
    print("----------------------")

if __name__ == "__main__":
    main()