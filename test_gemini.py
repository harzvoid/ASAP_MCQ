from google import genai
import os
from dotenv import load_dotenv
import json

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    print("Error: GEMINI_API_KEY not found in .env file")
    exit(1)

client = genai.Client(api_key=api_key)

try:
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents="Generate 3 MCQs on Operating System Deadlock with answers. Return ONLY valid JSON in the format: [{'question':'...','options':['A...','B...'],'answer':'...','explanation':'...'}]"
    )
    print("Response from Gemini:")
    print(response.text)
    
    # Try to parse as JSON to verify it's valid
    cleaned = response.text.strip()
    if cleaned.startswith("```json"):
        cleaned = cleaned[7:]
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3]
    
    data = json.loads(cleaned.strip())
    print(f"\nSuccessfully parsed {len(data)} questions")
    
except Exception as e:
    print(f"Error: {e}")