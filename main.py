import json
import os
from dotenv import load_dotenv
import traceback

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
      "Option 1",
      "Option 2",
      "Option 3",
      "Option 4"
    ],
    "answer": ,
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

        print(cleaned)
        mcqs = json.loads(cleaned)
        if not isinstance(mcqs, list):
            raise Exception("Gemini did not return a list of MCQs.")

        formatted = []

        for item in mcqs:

                answer = item["answer"]

        if isinstance(answer, int):
            ans_index = answer

        elif isinstance(answer, str):
            answer = answer.strip().upper()

            if answer in ["A", "B", "C", "D"]:
                ans_index = ord(answer) - ord("A")
            else:
                ans_index = next(
            (
                i
                    for i, opt in enumerate(item["options"])
                    if answer.lower() in opt.lower()
            ),
            0,
        )

        else:
            ans_index = 0

            if answer in ["A", "B", "C", "D"]:
                ans_index = ord(answer) - ord("A")

            else:
                ans_index = next(
                    (
                        i for i, opt in enumerate(item["options"])
                        if answer.lower() in opt.lower()
                    ),
                    0
                )

            formatted.append({
                "q": item["question"],
                "opts": item["options"],
                "ans": ans_index,
                "explain": item["explanation"],
                "why": ["", "", "", ""],
                "topic": data.topic
            })

        return {
            "topic": data.topic,
            "mcqs": formatted
        }

    except Exception as e:
            traceback.print_exc()

    return {
            "topic": data.topic,
            "error": str(e),
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
