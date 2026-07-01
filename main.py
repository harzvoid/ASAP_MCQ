import json
import os
from dotenv import load_dotenv

from fastapi import FastAPI
from pydantic import BaseModel
from google import genai

load_dotenv()
app = FastAPI()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

class TopicRequest(BaseModel):
    topic: str
    difficulty: str
    count: int
    types: list[str]

@app.post("/generate-mcq")
def generate_mcq(data: TopicRequest):

    prompt = f"""
Generate {data.count} exam-level MCQs.

Topic:
{data.topic}

Difficulty:
{data.difficulty}

Question Types:
{", ".join(data.types)}

Return ONLY valid JSON.

Format:

[
  {{
    "question": "...",
    "options": [
      "A",
      "B",
      "C",
      "D"
    ],
    "answer": "...",
    "explanation": "..."
  }}
]"""

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )

    try:

        cleaned = (
            response.text
            .replace("```json", "")
            .replace("```", "")
            .strip()
        )

        mcqs = json.loads(cleaned)

        return {
            "topic": data.topic,
            "mcqs": mcqs
        }

    except Exception:

        return {
            "topic": data.topic,
            "raw_response": response.text
        }
