from google import genai
import os
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents="Generate 3 MCQs on Operating System Deadlock with answers."
)

print(response.text)
from pydantic import BaseModel

class TopicRequest(BaseModel):
    topic: str
    difficulty: str
    questions: int
    question_types: list[str]