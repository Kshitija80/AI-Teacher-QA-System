from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from supabase import create_client, Client
from datetime import datetime
from dotenv import load_dotenv
import time
import os

# Load environment variables
load_dotenv()

# ==============================
# FLASK APP
# ==============================
app = Flask(__name__)
CORS(app)

# ==============================
# ENV VARIABLES
# ==============================
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not GROQ_API_KEY:
    raise ValueError("Missing GROQ_API_KEY")

if not SUPABASE_URL:
    raise ValueError("Missing SUPABASE_URL")

if not SUPABASE_KEY:
    raise ValueError("Missing SUPABASE_KEY")

# ==============================
# GROQ SETUP
# ==============================
llm = ChatGroq(
    model="llama-3.1-8b-instant",
    api_key=GROQ_API_KEY
)

# ==============================
# SUPABASE SETUP
# ==============================
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ==============================
# HOME PAGE
# ==============================
@app.route("/")
def home():
    return render_template("index.html")

# ==============================
# ASK AI ROUTE
# ==============================
@app.route("/ask", methods=["POST"])
def ask():
    try:
        data = request.get_json()
        question = data.get("question", "").strip()

        if not question:
            return jsonify({"detail": "Question is required"}), 400

        start_time = time.time()

        response = llm.invoke([HumanMessage(content=question)])
        answer = response.content

        duration = int((time.time() - start_time) * 1000)

        try:
            supabase.table("AI_Teacher").insert({
                "question": question,
                "answer": answer,
                "created_at": datetime.utcnow().isoformat()
            }).execute()
            saved = True
        except Exception as e:
            print("Supabase Error:", e)
            saved = False

        return jsonify({
            "answer": answer,
            "duration_ms": duration,
            "saved_to_sheet": saved
        })

    except Exception as e:
        return jsonify({"detail": str(e)}), 500

# ==============================
# LOAD HISTORY
# ==============================
@app.route("/history", methods=["GET"])
def history():
    try:
        data = supabase.table("AI_Teacher") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute()

        history_list = [
            {
                "question": row.get("question"),
                "answer": row.get("answer"),
                "timestamp": row.get("created_at"),
                "duration_ms": None
            }
            for row in data.data
        ]

        return jsonify(history_list)

    except Exception as e:
        return jsonify({"detail": str(e)}), 500

# ==============================
# CLEAR HISTORY
# ==============================
@app.route("/history", methods=["DELETE"])
def clear_history():
    try:
        supabase.table("AI_Teacher").delete().neq("id", 0).execute()
        return jsonify({"message": "History cleared"})
    except Exception as e:
        return jsonify({"detail": str(e)}), 500

# ==============================
# RUN APP
# ==============================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)