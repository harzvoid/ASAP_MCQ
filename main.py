import json
import os
from dotenv import load_dotenv

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory=".")

load_dotenv()
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
]
"""

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

        formatted = []

        for item in mcqs:
            formatted.append({
                "q": item["question"],
                "opts": item["options"],
                "ans": item["options"].index(item["answer"]),
                "explain": item["explanation"],
                "why": ["", "", "", ""],
                "topic": data.topic
            })

        return {
            "topic": data.topic,
            "mcqs": formatted
        }

    except Exception:

        return {
            "topic": data.topic,
            "raw_response": response.text
        }
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="index.html"
    )

@app.get("/generator")
def generator(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="generator.html"
    )

@app.get("/loading")
def loading(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="loading.html"
    )

@app.get("/quiz")
def quiz(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="quiz.html"
    )

@app.get("/result")
def result(request: Request):
    return templates.TemplateResponse(
        request=request,
        name="result.html"
    )