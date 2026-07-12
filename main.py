import json
import os
from dotenv import load_dotenv
import logging
import re

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google import genai
from fastapi.templating import Jinja2Templates

# forr logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# gemini
API_KEY = os.getenv("GEMINI_API_KEY")
if not API_KEY:
    logger.error("GEMINI_API_KEY not found in environment variables!")
    raise ValueError("GEMINI_API_KEY is required")

client = genai.Client(api_key=API_KEY)

class TopicRequest(BaseModel):
    topic: str
    difficulty: str
    count: int
    types: list[str]

# Test endpoint to verify API key is working
@app.get("/test-api")
def test_api():
    try:
        logger.info("Testing Gemini API connection...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents="Hello, respond with 'API is working'"
        )
        return {"status": "ok", "response": response.text}
    except Exception as e:
        logger.error(f"API test failed: {e}")
        return {"status": "error", "error": str(e)}

@app.post("/generate-mcq")
async def generate_mcq(data: TopicRequest):
    logger.info(f"Received request: topic={data.topic}, difficulty={data.difficulty}, count={data.count}, types={data.types}")
    
    # Build the prompt based on question types
    type_descriptions = []
    for t in data.types:
        if t == "mcq":
            type_descriptions.append("Multiple Choice (4 options, single correct answer)")
        elif t == "msq":
            type_descriptions.append("Multi-Select (4 options, one or more correct answers)")
        elif t == "tf":
            type_descriptions.append("True/False (with explanation)")
        elif t == "fib":
            type_descriptions.append("Fill in the Blank (key term recall)")
    
    prompt = f"""Generate exactly {data.count} exam-level MCQs on the topic: "{data.topic}".

Difficulty Level: {data.difficulty}

Question Types:
{chr(10).join(f"- {desc}" for desc in type_descriptions)}

IMPORTANT: Return ONLY valid JSON. No additional text, no markdown, no explanation outside the JSON.

Format:
[
  {{
    "question": "The question text here",
    "options": ["Option 1", "Option 2", "Option 3", "Option 4"],
    "answer": "Option 1",
    "explanation": "Detailed explanation of why this is correct",
    "why": [
      "Explanation of why option 1 is incorrect/correct",
      "Explanation of why option 2 is incorrect/correct",
      "Explanation of why option 3 is incorrect/correct",
      "Explanation of why option 4 is incorrect/correct"
    ]
  }}
]

Make sure:
1. Questions are relevant to {data.topic}
2. Difficulty matches {data.difficulty} level
3. All options are plausible
4. Explanations are educational and clear
5. For True/False questions, options should be ["True", "False"]
6. For Fill in the Blank, options should be 4 plausible terms
7. For Multi-Select, clearly indicate which options are correct in the explanation
8. Return EXACTLY {data.count} questions
"""

    try:
        logger.info("Sending request to Gemini API...")
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        
        # Get response text
        response_text = response.text if hasattr(response, 'text') else str(response)
        logger.info(f"Raw response from Gemini (first 500 chars): {response_text[:500]}...")
        
        # Clean the response - remove markdown code blocks
        cleaned = response_text.strip()
        
        # Remove markdown code blocks if present
        cleaned = re.sub(r'```json\s*', '', cleaned)
        cleaned = re.sub(r'```\s*', '', cleaned)
        cleaned = cleaned.strip()
        
        # Try to find JSON array in the response
        json_match = re.search(r'\[\s*\{.*\}\s*\]', cleaned, re.DOTALL)
        if json_match:
            cleaned = json_match.group(0)
        
        logger.info(f"Cleaned JSON (first 200 chars): {cleaned[:200]}...")
        
        # Parse JSON
        mcqs = json.loads(cleaned)
        logger.info(f"Successfully parsed {len(mcqs)} questions")
        
        # Format the MCQs
        formatted = []
        for item in mcqs:
            opts = item.get("options", ["Option 1", "Option 2", "Option 3", "Option 4"])
            ans = item.get("answer", opts[0] if opts else "Option 1")
            
            # Find the index of the answer
            ans_index = 0
            for i, opt in enumerate(opts):
                # Try exact match
                if ans == opt:
                    ans_index = i
                    break
                # Try match where answer is contained in the option
                if ans in opt or opt in ans:
                    ans_index = i
                    break
                # Try matching just the letter (A, B, C, D) or number
                if len(ans) <= 2:
                    # Check if answer is like "A" or "A)"
                    letter_match = re.search(r'([A-D])', ans.upper())
                    if letter_match:
                        letter = letter_match.group(1)
                        expected_letter = chr(65 + i)  # A, B, C, D
                        if letter == expected_letter:
                            ans_index = i
                            break
                    # Check if answer is like "1" or "1)"
                    num_match = re.search(r'([1-4])', ans)
                    if num_match:
                        num = int(num_match.group(1))
                        if num == i + 1:
                            ans_index = i
                            break
            
            # Ensure why has 4 items
            why = item.get("why", [])
            while len(why) < 4:
                why.append(f"Option {chr(65 + len(why))} - No explanation provided")
            
            formatted.append({
                "q": item.get("question", f"Sample question about {data.topic}"),
                "opts": opts,
                "ans": ans_index,
                "explain": item.get("explanation", "No explanation provided."),
                "why": why[:4],
                "topic": data.topic
            })
        
        if not formatted:
            raise ValueError("No valid questions were generated")
        
        # Ensure we have exactly the requested number of questions
        if len(formatted) > data.count:
            formatted = formatted[:data.count]
        
        logger.info(f"Returning {len(formatted)} formatted questions")
        
        return {
            "topic": data.topic,
            "mcqs": formatted
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"JSON parsing error: {e}")
        logger.error(f"Response that failed to parse: {response_text if 'response_text' in locals() else 'No response'}")
        
        # Try to extract JSON from the raw response even if parsing failed
        try:
            # Try to find JSON array in the response
            json_match = re.search(r'\[\s*\{.*\}\s*\]', response_text, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                mcqs = json.loads(json_str)
                logger.info(f"Extracted {len(mcqs)} questions from raw response")
                # Format and return
                formatted = []
                for item in mcqs:
                    opts = item.get("options", ["Option 1", "Option 2", "Option 3", "Option 4"])
                    ans = item.get("answer", opts[0] if opts else "Option 1")
                    ans_index = 0
                    for i, opt in enumerate(opts):
                        if ans == opt or ans in opt or opt in ans:
                            ans_index = i
                            break
                    why = item.get("why", [])
                    while len(why) < 4:
                        why.append(f"Option {chr(65 + len(why))} - No explanation provided")
                    formatted.append({
                        "q": item.get("question", f"Question about {data.topic}"),
                        "opts": opts,
                        "ans": ans_index,
                        "explain": item.get("explanation", "No explanation provided."),
                        "why": why[:4],
                        "topic": data.topic
                    })
                if formatted:
                    return {"topic": data.topic, "mcqs": formatted}
        except Exception as e2:
            logger.error(f"Fallback parsing also failed: {e2}")
        
        # Return fallback MCQs
        return generate_fallback_mcqs(data.topic, data.count)
        
    except Exception as e:
        logger.error(f"Error generating MCQs: {e}")
        # Return fallback MCQs
        return generate_fallback_mcqs(data.topic, data.count)

def generate_fallback_mcqs(topic, count):
    """Generate fallback MCQs when API fails"""
    logger.info(f"Generating fallback MCQs for topic: {topic}")
    
    fallback_questions = [
        {
            "q": f"What is the fundamental concept of {topic}?",
            "opts": ["Fundamental principle", "Secondary concept", "Advanced theory", "Basic definition"],
            "ans": 0,
            "explain": "This is the fundamental concept that forms the basis of understanding in this area.",
            "why": [
                "This is the foundational concept - Correct",
                "This is a derivative concept - Incorrect",
                "This is an advanced application - Incorrect",
                "This is too basic - Incorrect"
            ],
            "topic": topic
        },
        {
            "q": f"Which of the following is a key application of {topic}?",
            "opts": ["Real-world application 1", "Real-world application 2", "Real-world application 3", "Real-world application 4"],
            "ans": 0,
            "explain": "This is a well-known application of the concept.",
            "why": [
                "This is a key application - Correct",
                "This is less directly related - Incorrect",
                "This is not directly applicable - Incorrect",
                "This is a different field - Incorrect"
            ],
            "topic": topic
        },
        {
            "q": f"What is the main purpose of studying {topic}?",
            "opts": ["Understanding core principles", "Memorizing facts", "Passing exams", "Gaining general knowledge"],
            "ans": 0,
            "explain": "The main purpose is to understand the core principles and how they apply.",
            "why": [
                "Understanding core principles is the main purpose - Correct",
                "Memorization is a byproduct, not the main purpose - Incorrect",
                "Passing exams is a goal, not the purpose of studying - Incorrect",
                "General knowledge is too broad - Incorrect"
            ],
            "topic": topic
        }
    ]
    
    # Generate more if needed
    while len(fallback_questions) < min(count, 10):
        idx = len(fallback_questions) % 3
        q = fallback_questions[idx].copy()
        q["q"] = f"Additional question {len(fallback_questions)+1} about {topic}: {q['q']}"
        fallback_questions.append(q)
    
    return {
        "topic": topic,
        "mcqs": fallback_questions[:count]
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