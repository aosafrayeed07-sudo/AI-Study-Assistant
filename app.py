from flask import Flask, render_template, request, redirect, url_for, flash, session
import sqlite3
import random
import json
import os
import time
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

try:
    from google import genai
except ImportError:
    genai = None

load_dotenv()

app = Flask(__name__)
app.secret_key = "change-this-secret-key"

DATABASE = "database.db"
UPLOAD_FOLDER = "uploads"
ALLOWED_EXTENSIONS = {"pdf"}

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ---------------- GEMINI AI ----------------

def get_ai_client():
    """Return a Gemini client using GEMINI_API_KEY from .env."""
    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key or genai is None:
        return None

    return genai.Client(api_key=api_key)


def generate_ai_text(prompt):
    """Generate text with Gemini. Returns None if unavailable/error."""
    client = get_ai_client()

    if client is None:
        return None

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )
        return response.text.strip() if response.text else None
    except Exception:
        return None


def generate_ai_quiz(subject, number=10):
    client = get_ai_client()

    if client is None:
        return None

    prompt = f"""
Create exactly {number} multiple-choice questions about {subject}.

Return ONLY valid JSON. Do not use markdown or code fences.

Use exactly this format:
{{
  "questions": [
    {{
      "question": "question text",
      "options": ["A", "B", "C", "D"],
      "answer": 0
    }}
  ]
}}

Rules:
- There must be exactly {number} questions.
- Every question must have exactly 4 options.
- "answer" must be an integer from 0 to 3.
- The answer is the zero-based index of the correct option.
- Make the questions educational and appropriate for a student.
"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt
        )

        text = (response.text or "").strip()

        # Remove accidental markdown fences if Gemini returns them.
        if text.startswith("```"):
            lines = text.splitlines()
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        data = json.loads(text)
        questions = data.get("questions", [])

        if len(questions) != number:
            return None

        valid = []

        for q in questions:
            if (
                isinstance(q.get("question"), str)
                and isinstance(q.get("options"), list)
                and len(q["options"]) == 4
                and all(isinstance(option, str) for option in q["options"])
                and isinstance(q.get("answer"), int)
                and 0 <= q["answer"] <= 3
            ):
                valid.append(q)

        return valid if len(valid) == number else None

    except Exception:
        return None


# ---------------- DATABASE ----------------

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS subjects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            description TEXT
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS study_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER,
            minutes INTEGER NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS quiz_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subject_id INTEGER,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            date TEXT NOT NULL,
            FOREIGN KEY(subject_id) REFERENCES subjects(id)
        )
    """)

    conn.commit()
    conn.close()


# ---------------- QUESTION BANK ----------------

QUESTION_BANK = {
    "python": [
        {
            "question": "Which keyword is used to define a function in Python?",
            "options": ["func", "def", "function", "define"],
            "answer": 1
        },
        {
            "question": "Which data type stores key-value pairs?",
            "options": ["List", "Tuple", "Dictionary", "Set"],
            "answer": 2
        },
        {
            "question": "What does len([1, 2, 3]) return?",
            "options": ["2", "3", "4", "1"],
            "answer": 1
        },
        {
            "question": "Which symbol starts a Python comment?",
            "options": ["//", "#", "/*", "--"],
            "answer": 1
        },
        {
            "question": "Which function displays output in Python?",
            "options": ["display()", "echo()", "print()", "write()"],
            "answer": 2
        },
        {
            "question": "Which collection is ordered and mutable?",
            "options": ["Tuple", "List", "String", "Set"],
            "answer": 1
        },
        {
            "question": "What is the result of 3 ** 2?",
            "options": ["6", "9", "8", "5"],
            "answer": 1
        },
        {
            "question": "Which keyword is used to create a loop over a sequence?",
            "options": ["for", "loop", "repeat", "iterate"],
            "answer": 0
        },
        {
            "question": "What does input() normally return?",
            "options": ["An integer", "A float", "A string", "A Boolean"],
            "answer": 2
        },
        {
            "question": "Which library is commonly used to create Flask web apps?",
            "options": ["flask", "pygame", "numpy", "turtle"],
            "answer": 0
        },
    ],

    "math": [
        {
            "question": "What is the derivative of x²?",
            "options": ["x", "2x", "x²", "2"],
            "answer": 1
        },
        {
            "question": "What is ∫ 1 dx?",
            "options": ["1", "x + C", "0", "ln(x)"],
            "answer": 1
        },
        {
            "question": "What is sin(90°)?",
            "options": ["0", "1/2", "1", "√3/2"],
            "answer": 2
        },
        {
            "question": "What is the slope of y = 3x + 2?",
            "options": ["2", "3", "-3", "1"],
            "answer": 1
        },
        {
            "question": "What is the value of 5!?",
            "options": ["20", "60", "100", "120"],
            "answer": 3
        },
        {
            "question": "What is the derivative of sin(x)?",
            "options": ["cos(x)", "-cos(x)", "sin(x)", "-sin(x)"],
            "answer": 0
        },
        {
            "question": "What is the integral of x?",
            "options": ["x² + C", "x²/2 + C", "2x + C", "1 + C"],
            "answer": 1
        },
        {
            "question": "What is log₁₀(100)?",
            "options": ["1", "2", "10", "100"],
            "answer": 1
        },
        {
            "question": "If a = 4 and b = 3, what is √(a²+b²)?",
            "options": ["5", "6", "7", "12"],
            "answer": 0
        },
        {
            "question": "What is the sum of the first 5 positive integers?",
            "options": ["10", "12", "15", "20"],
            "answer": 2
        },
    ],

    "physics": [
        {
            "question": "What is the SI unit of force?",
            "options": ["Joule", "Newton", "Watt", "Pascal"],
            "answer": 1
        },
        {
            "question": "What is the approximate acceleration due to gravity on Earth?",
            "options": ["3.8 m/s²", "6.67 m/s²", "9.8 m/s²", "12.5 m/s²"],
            "answer": 2
        },
        {
            "question": "Which quantity is measured in watts?",
            "options": ["Energy", "Power", "Force", "Charge"],
            "answer": 1
        },
        {
            "question": "What is the SI unit of electric charge?",
            "options": ["Volt", "Ohm", "Coulomb", "Ampere"],
            "answer": 2
        },
        {
            "question": "Which law relates voltage, current and resistance?",
            "options": ["Newton's law", "Ohm's law", "Faraday's law", "Hooke's law"],
            "answer": 1
        },
        {
            "question": "What is the speed of light in vacuum approximately?",
            "options": ["3×10⁶ m/s", "3×10⁸ m/s", "3×10¹⁰ m/s", "9.8 m/s"],
            "answer": 1
        },
        {
            "question": "What is the SI unit of resistance?",
            "options": ["Ohm", "Volt", "Ampere", "Farad"],
            "answer": 0
        },
        {
            "question": "Kinetic energy depends on mass and:",
            "options": ["Velocity squared", "Height only", "Charge", "Temperature"],
            "answer": 0
        },
        {
            "question": "Which device measures electric current?",
            "options": ["Voltmeter", "Ammeter", "Ohmmeter", "Wattmeter"],
            "answer": 1
        },
        {
            "question": "Potential difference is commonly measured in:",
            "options": ["Volts", "Amperes", "Ohms", "Newtons"],
            "answer": 0
        },
    ],

    "circuit": [
        {
            "question": "What is the SI unit of resistance?",
            "options": ["Volt", "Ohm", "Ampere", "Watt"],
            "answer": 1
        },
        {
            "question": "In a series circuit, the current is:",
            "options": ["Different everywhere", "The same through each element", "Always zero", "Infinite"],
            "answer": 1
        },
        {
            "question": "In a parallel circuit, the voltage across ideal branches is:",
            "options": ["The same", "Always zero", "Different by definition", "Infinite"],
            "answer": 0
        },
        {
            "question": "KCL is based on conservation of:",
            "options": ["Energy", "Charge", "Momentum", "Mass only"],
            "answer": 1
        },
        {
            "question": "KVL is based on conservation of:",
            "options": ["Charge", "Energy", "Mass", "Current"],
            "answer": 1
        },
        {
            "question": "An ideal voltage source has:",
            "options": ["Fixed voltage", "Fixed current only", "Zero voltage", "Infinite resistance"],
            "answer": 0
        },
        {
            "question": "An ideal current source has:",
            "options": ["Fixed voltage", "Fixed current", "Zero current", "Infinite current"],
            "answer": 1
        },
        {
            "question": "What instrument measures voltage?",
            "options": ["Ammeter", "Voltmeter", "Galvanometer only", "Wattmeter"],
            "answer": 1
        },
        {
            "question": "The resistance of an ideal wire is:",
            "options": ["Infinite", "1 Ω", "Zero", "100 Ω"],
            "answer": 2
        },
        {
            "question": "Power in a resistor can be calculated using:",
            "options": ["P = VI", "P = V/I only", "P = I/V only", "P = R/V"],
            "answer": 0
        },
    ]
}


def get_question_set(subject_name):
    name = subject_name.lower()

    if "python" in name or "program" in name or "coding" in name:
        return QUESTION_BANK["python"]

    if "math" in name or "calculus" in name or "algebra" in name:
        return QUESTION_BANK["math"]

    if "circuit" in name or "electrical" in name or "eee" in name:
        return QUESTION_BANK["circuit"]

    if "physics" in name:
        return QUESTION_BANK["physics"]

    combined = (
        QUESTION_BANK["python"]
        + QUESTION_BANK["math"]
        + QUESTION_BANK["physics"]
        + QUESTION_BANK["circuit"]
    )

    return combined


# ---------------- GENERAL ----------------

@app.route("/")
def index():
    conn = get_db()

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY name"
    ).fetchall()

    study_time = conn.execute(
        "SELECT COALESCE(SUM(minutes), 0) FROM study_sessions"
    ).fetchone()[0]

    score, total = conn.execute(
        """
        SELECT COALESCE(SUM(score), 0),
               COALESCE(SUM(total), 0)
        FROM quiz_results
        """
    ).fetchone()

    percentage = round(score / total * 100) if total else 0

    conn.close()

    return render_template(
        "index.html",
        subjects=subjects,
        study_time=study_time,
        percentage=percentage
    )


# ---------------- SUBJECTS ----------------

@app.route("/subjects")
def subjects():
    conn = get_db()

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY name"
    ).fetchall()

    conn.close()

    return render_template("subjects.html", subjects=subjects)


@app.route("/add_subject", methods=["POST"])
def add_subject():
    name = request.form.get("name", "").strip()
    description = request.form.get("description", "").strip()

    if name:
        conn = get_db()
        conn.execute(
            "INSERT INTO subjects (name, description) VALUES (?, ?)",
            (name, description)
        )
        conn.commit()
        conn.close()

    return redirect(url_for("subjects"))


@app.route("/delete_subject/<int:subject_id>")
def delete_subject(subject_id):
    conn = get_db()

    conn.execute(
        "DELETE FROM study_sessions WHERE subject_id = ?",
        (subject_id,)
    )

    conn.execute(
        "DELETE FROM quiz_results WHERE subject_id = ?",
        (subject_id,)
    )

    conn.execute(
        "DELETE FROM subjects WHERE id = ?",
        (subject_id,)
    )

    conn.commit()
    conn.close()

    return redirect(url_for("subjects"))


# ---------------- TIMER ----------------

@app.route("/timer")
def timer():
    conn = get_db()

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY name"
    ).fetchall()

    conn.close()

    return render_template("timer.html", subjects=subjects)


@app.route("/save_session", methods=["POST"])
def save_session():
    subject_id = request.form.get("subject_id")
    minutes = request.form.get("minutes")

    try:
        minutes = int(minutes)
    except (TypeError, ValueError):
        minutes = 0

    if subject_id and minutes > 0:
        conn = get_db()

        conn.execute(
            """
            INSERT INTO study_sessions
            (subject_id, minutes, date)
            VALUES (?, ?, ?)
            """,
            (
                subject_id,
                minutes,
                datetime.now().strftime("%Y-%m-%d %H:%M")
            )
        )

        conn.commit()
        conn.close()

    return redirect(url_for("timer"))


# ---------------- QUIZ ----------------

@app.route("/quiz")
def quiz():
    conn = get_db()

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY name"
    ).fetchall()

    conn.close()

    return render_template("quiz.html", subjects=subjects)


@app.route("/start_quiz", methods=["POST"])
def start_quiz():
    subject_id = request.form.get("subject_id")
    use_ai = request.form.get("use_ai") == "on"

    if not subject_id:
        return redirect(url_for("quiz"))

    conn = get_db()
    subject = conn.execute(
        "SELECT * FROM subjects WHERE id = ?",
        (subject_id,)
    ).fetchone()
    conn.close()

    if not subject:
        return redirect(url_for("quiz"))

    questions = None
    mode = "Random Question Bank"

    if use_ai:
        questions = generate_ai_quiz(subject["name"])

        if questions:
            mode = "AI Generated"
        else:
            flash(
                "Gemini AI mode was unavailable, so a random question bank was used.",
                "info"
            )

    if not questions:
        pool = get_question_set(subject["name"])
        questions = random.sample(pool, min(10, len(pool)))

    prepared = []

    for q in questions:
        options = list(q["options"])
        correct_text = options[q["answer"]]

        random.shuffle(options)
        new_answer = options.index(correct_text)

        prepared.append({
            "question": q["question"],
            "options": options,
            "answer": new_answer
        })

    return render_template(
        "quiz.html",
        subjects=get_subjects(),
        quiz_questions=prepared,
        subject_id=subject_id,
        subject_name=subject["name"],
        mode=mode
    )


@app.route("/submit_quiz", methods=["POST"])
def submit_quiz():
    subject_id = request.form.get("subject_id")
    questions_json = request.form.get("questions_json")

    if not subject_id or not questions_json:
        return redirect(url_for("quiz"))

    try:
        questions = json.loads(questions_json)
    except json.JSONDecodeError:
        return redirect(url_for("quiz"))

    score = 0

    for index, question in enumerate(questions):
        answer = request.form.get(f"q{index}")

        try:
            if answer is not None and int(answer) == question["answer"]:
                score += 1
        except (ValueError, TypeError, KeyError):
            pass

    total = len(questions)

    conn = get_db()

    conn.execute(
        """
        INSERT INTO quiz_results
        (subject_id, score, total, date)
        VALUES (?, ?, ?, ?)
        """,
        (
            subject_id,
            score,
            total,
            datetime.now().strftime("%Y-%m-%d %H:%M")
        )
    )

    conn.commit()
    conn.close()

    percentage = round(score / total * 100) if total else 0

    return render_template(
        "quiz.html",
        subjects=get_subjects(),
        result=True,
        score=score,
        total=total,
        percentage=percentage
    )


def get_subjects():
    conn = get_db()

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY name"
    ).fetchall()

    conn.close()

    return subjects


# ---------------- PDF NOTES ----------------

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route("/notes", methods=["GET", "POST"])
def notes():
    extracted_text = None
    filename = None
    summary = None

    if request.method == "POST":
        file = request.files.get("pdf")

        if not file or file.filename == "":
            flash("Please select a PDF file.", "error")
            return redirect(url_for("notes"))

        if not allowed_file(file.filename):
            flash("Only PDF files are supported.", "error")
            return redirect(url_for("notes"))

        if PdfReader is None:
            flash("PyPDF2 is not installed.", "error")
            return redirect(url_for("notes"))

        filename = secure_filename(file.filename)
        path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(path)

        try:
            reader = PdfReader(path)
            pages = []

            for page in reader.pages:
                pages.append(page.extract_text() or "")

            extracted_text = "\n".join(pages).strip()

            if not extracted_text:
                flash("No readable text was found in this PDF.", "error")
                extracted_text = None

            if extracted_text:
                prompt = f"""
Summarize these study notes clearly for a student.

Give:
1. Main ideas
2. Important formulas/facts
3. Five quick revision points

Notes:
{extracted_text[:12000]}
"""

                summary = generate_ai_text(prompt)

                if summary is None:
                    flash(
                        "The PDF was read successfully, but Gemini AI summary is unavailable.",
                        "info"
                    )

        except Exception as e:
            flash(f"Could not read the PDF: {e}", "error")

    return render_template(
        "notes.html",
        extracted_text=extracted_text,
        filename=filename,
        summary=summary
    )


# ---------------- PROGRESS ----------------

@app.route("/progress")
def progress():
    conn = get_db()

    subjects = conn.execute(
        "SELECT * FROM subjects ORDER BY name"
    ).fetchall()

    progress_data = []

    for subject in subjects:
        study = conn.execute(
            """
            SELECT COALESCE(SUM(minutes), 0)
            FROM study_sessions
            WHERE subject_id = ?
            """,
            (subject["id"],)
        ).fetchone()[0]

        score, total = conn.execute(
            """
            SELECT COALESCE(SUM(score), 0),
                   COALESCE(SUM(total), 0)
            FROM quiz_results
            WHERE subject_id = ?
            """,
            (subject["id"],)
        ).fetchone()

        percentage = round(score / total * 100) if total else 0

        progress_data.append({
            "name": subject["name"],
            "study": study,
            "percentage": percentage
        })

    conn.close()

    return render_template(
        "progress.html",
        progress_data=progress_data
    )


# ---------------- AI TUTOR ----------------

@app.route("/ai-tutor", methods=["GET", "POST"])
def ai_tutor():
    if "chat_history" not in session:
        session["chat_history"] = []

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if question:
            session["chat_history"].append({
                "role": "user",
                "content": question
            })
            session.modified = True

            client = get_ai_client()

            if client is None:
                answer = (
                    "⚠️ Gemini AI is not configured. "
                    "Please check your GEMINI_API_KEY in the .env file."
                )
            else:
                conversation = []

                for message in session["chat_history"]:
                    role = "Student" if message["role"] == "user" else "AI Tutor"
                    conversation.append(f"{role}: {message['content']}")

                conversation_text = "\n\n".join(conversation)

                prompt = f"""
You are an AI Study Tutor.

You are having a continuous conversation with a student.
Use previous messages to understand references such as
"this", "that", "it", and "the previous question".

Explain concepts clearly and step-by-step.
For mathematics, physics, electrical engineering, programming,
and technical questions, show working when appropriate.

Conversation so far:

{conversation_text}

Now answer the student's latest question.
"""

                answer = None

                for attempt in range(4):
                    try:
                        response = client.models.generate_content(
                            model="gemini-2.5-flash-lite",
                            contents=prompt
                        )

                        answer = (
                            response.text.strip()
                            if response.text
                            else "⚠️ Gemini returned an empty response."
                        )
                        break

                    except Exception as e:
                        error_text = str(e)
                        upper_error = error_text.upper()

                        if "503" in error_text or "UNAVAILABLE" in upper_error:
                            if attempt < 3:
                                time.sleep(2 ** attempt)
                                continue

                            answer = (
                                "⚠️ Gemini is temporarily overloaded right now. "
                                "I tried several times, but the service is still "
                                "unavailable. Please try again in a little while."
                            )
                        elif "429" in error_text or "RESOURCE_EXHAUSTED" in upper_error:
                            answer = (
                                "⚠️ Gemini's API quota or rate limit has been reached. "
                                "Please check your Gemini API usage and quota."
                            )
                        else:
                            answer = f"⚠️ Gemini AI error: {error_text}"

                        break

            session["chat_history"].append({
                "role": "assistant",
                "content": answer
            })
            session.modified = True

    return render_template(
        "ai_tutor.html",
        chat_history=session["chat_history"]
    )


@app.route("/clear-chat", methods=["POST"])
def clear_chat():
    session.pop("chat_history", None)
    return redirect(url_for("ai_tutor"))


# ---------------- ABOUT ----------------

@app.route("/about")
def about():
    return render_template("about.html")


# ---------------- START ----------------

init_db()

if __name__ == "__main__":
    app.run(debug=True)