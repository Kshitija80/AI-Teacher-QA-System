from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import TypedDict, Optional
from langgraph.graph import StateGraph
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import os

app = FastAPI(title="AI Teacher API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Config ──────────────────────────────────────────────────────────────────
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "YOUR_GROQ_API_KEY")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "AI_Teacher")
GOOGLE_CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "credentials.json")

# ── LLM ─────────────────────────────────────────────────────────────────────
llm = ChatGroq(model="llama-3.1-8b-instant", api_key=GROQ_API_KEY)

# ── Google Sheets ────────────────────────────────────────────────────────────
def get_sheet():
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]

    creds = Credentials.from_service_account_file(
        GOOGLE_CREDS_FILE,
        scopes=scopes
    )

    client = gspread.authorize(creds)

    try:
        sheet = client.open(GOOGLE_SHEET_NAME).sheet1
    except gspread.SpreadsheetNotFound:
        spreadsheet = client.create(GOOGLE_SHEET_NAME)
        sheet = spreadsheet.sheet1
        sheet.append_row(["#", "Timestamp", "Question", "Answer", "Duration (ms)"])
        sheet.format("A1:E1", {"textFormat": {"bold": True}})

    return sheet


def save_to_sheet(question: str, answer: str, duration_ms: int):
    try:
        sheet = get_sheet()
        row_count = len(sheet.get_all_values())

        sheet.append_row([
            row_count,
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            question,
            answer,
            duration_ms,
        ])

        return True

    except Exception as e:
        print("Google Sheets error:", e)
        return False


# ── LangGraph ────────────────────────────────────────────────────────────────
class StudentState(TypedDict, total=False):
    question: str
    answer: str


def ask_ai(state: StudentState) -> StudentState:
    response = llm.invoke([HumanMessage(content=state["question"])])
    return {"answer": response.content}


builder = StateGraph(StudentState)
builder.add_node("chatgpt", ask_ai)
builder.set_entry_point("chatgpt")
builder.set_finish_point("chatgpt")
graph = builder.compile()


# ── Schemas ───────────────────────────────────────────────────────────────────
class QuestionRequest(BaseModel):
    question: str


class QuestionResponse(BaseModel):
    question: str
    answer: str
    saved_to_sheet: bool
    duration_ms: int


class HistoryItem(BaseModel):
    row: int
    timestamp: str
    question: str
    answer: str
    duration_ms: Optional[int] = None


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"message": "AI Teacher API is running 🚀"}


@app.post("/ask", response_model=QuestionResponse)
def ask_question(body: QuestionRequest):
    if not body.question.strip():
        raise HTTPException(status_code=400, detail="Question cannot be empty")

    start = datetime.now()
    result = graph.invoke({"question": body.question})
    duration_ms = int((datetime.now() - start).total_seconds() * 1000)

    answer = result.get("answer", "No answer generated.")
    saved = save_to_sheet(body.question, answer, duration_ms)

    return QuestionResponse(
        question=body.question,
        answer=answer,
        saved_to_sheet=saved,
        duration_ms=duration_ms,
    )


@app.get("/history", response_model=list[HistoryItem])
def get_history():
    try:
        sheet = get_sheet()
        rows = sheet.get_all_values()

        if len(rows) <= 1:
            return []

        history = []

        for row in rows[1:]:
            if len(row) >= 4:
                history.append(HistoryItem(
                    row=int(row[0]) if row[0].isdigit() else 0,
                    timestamp=row[1],
                    question=row[2],
                    answer=row[3],
                    duration_ms=int(row[4]) if len(row) > 4 and row[4].isdigit() else None,
                ))

        return list(reversed(history))

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/history")
def clear_history():
    try:
        sheet = get_sheet()
        sheet.clear()
        sheet.append_row(["#", "Timestamp", "Question", "Answer", "Duration (ms)"])
        return {"message": "History cleared"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))