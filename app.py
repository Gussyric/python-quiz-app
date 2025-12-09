from flask import Flask, render_template, request, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from openai import OpenAI
from importlib import reload
import os
import json
import random
import logging
import difflib
import time
import sys

app = Flask(__name__)
app.secret_key = "your_secret_key"

# ---------------------------
# Logging Setup
# ---------------------------
logging.basicConfig(
    filename='error.log',
    level=logging.ERROR,
    format='%(asctime)s %(levelname)s:%(message)s'
)

# ---------------------------
# Flask App Setup
# ---------------------------
# OpenAI
from api import API_KEY
client = OpenAI(api_key=API_KEY)

# Ensure instance folder exists
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, "instance")
os.makedirs(instance_path, exist_ok=True)

# Database setup
db_path = os.path.join(instance_path, "users.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ---------------------------
# Database Models (still used)
# ---------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=True)
    user_id = db.Column(db.String(20), nullable=True)
    attempts = db.relationship('QuizAttempt', backref='user', lazy=True)

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    language = db.Column(db.String(50), nullable=False)
    user_id_fk = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)

with app.app_context():
    db.create_all()

# ---------------------------
# Utility Functions
# ---------------------------
def get_available_quizzes():
    quiz_folder = os.path.join(os.getcwd(), "questions")
    return [f.replace(".json", "") for f in os.listdir(quiz_folder) if f.endswith(".json")]

def generate_explanation(question_text, user_answer, correct_answer, all_options):
    """
    Generate a detailed explanation for a multiple-choice question.
    The explanation will describe:
    - Why the correct answer is correct
    - Why each incorrect option is wrong
    - Why the user's selected answer may be incorrect
    """
    prompt = f"""
    Question: {question_text}
    Options: {all_options}
    Correct Answer: {correct_answer}
    User Selected: {user_answer}

    Explain in detail:
    1. Why the correct answer is correct.
    2. For each incorrect option, explain why it is wrong.
    3. Why the user's selected answer may be incorrect (if not correct).

    Format the explanation using plain text headings like:
    1. Why the correct answer is correct:
    2. For each incorrect option, explain why it is wrong:
    3. Why the user's selected answer may be incorrect:

    Do NOT use any asterisks or Markdown formatting.
    Keep it clean and readable.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=500
        )
        explanation = getattr(response.choices[0].message, "content", "No explanation returned.")
    except Exception:
        explanation = "No explanation available. Please try again."

    return explanation.strip()

def load_questions(language, num_questions=10):
    with open(f"questions/{language}.json") as f:
        all_questions = json.load(f)
    return random.sample(all_questions, min(num_questions, len(all_questions)))

# ---------------------------
# Admin: Apply Patch
# ---------------------------
@app.route("/admin/apply_patch", methods=["POST"])
def apply_patch():
    patch_text = request.form["patch"]
    file_path = request.form["file"]

    with open(file_path, "r") as f:
        original = f.readlines()

    with open(file_path, "w") as f:
        f.writelines(difflib.restore(patch_text.splitlines(), 1))

    return "<h1>Patch Applied!</h1><p>Your code has been updated.</p>"

# ---------------------------
# Admin: Auto Fix
# ---------------------------
@app.route("/admin/auto_fix", methods=["POST"])
def auto_fix():

    if request.is_json:
        file_path = request.json.get("file")
    else:
        file_path = request.form.get("file")

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Invalid file path"}), 400

    with open(file_path, "r") as f:
        code = f.read()

    try:
        with open("error.log", "r") as f:
            error_log = f.read()[-5000:]
    except:
        error_log = "No error logs available."

    prompt = f"""
    You are an expert software engineer.
    Based on the following Python/Flask code and error logs,
    produce ONLY a unified diff patch.

    Code:
    {code}

    Errors:
    {error_log}

    Output only the patch.
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=500
        )
        patch = getattr(response.choices[0].message, "content", "No patch returned.")
        print("\n=== PATCH GENERATED ===\n", patch, "\n======================\n")
    except Exception as e:
        return jsonify({"error": f"OpenAI failure: {e}"}), 500

    # Validate
    if not patch.startswith(f"--- {file_path}"):
        return jsonify({"error": "Patch missing correct header", "patch": patch}), 400

    if "@@" not in patch:
        return jsonify({"error": "Patch missing hunk (@@)", "patch": patch}), 400

    original = open(file_path).read().splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)

    try:
        patched = difflib.patch_from_unified_diff(patch_lines, original)
    except Exception as e:
        return jsonify({"error": f"Patch error: {e}", "patch": patch}), 500

    with open(file_path, "w") as f:
        f.writelines(patched)

    # Reload
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    if module_name in sys.modules:
        try:
            reload(sys.modules[module_name])
        except Exception as e:
            print("Reload failed:", e)

    return jsonify({"patch": patch, "status": "Patch applied"})

# ---------------------------
# Admin Dashboard + State
# ---------------------------
STATE_FILE = "auto_maintain_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        return json.load(open(STATE_FILE))
    return {"patches": [], "restarts": 0}

def save_state(state):
    json.dump(state, open(STATE_FILE, "w"), indent=2)

@app.route("/admin/auto_dashboard")
def auto_dashboard():
    state = load_state()
    patches = state.get("patches", [])
    restarts = state.get("restarts", 0)

    errors = []
    if os.path.exists("error.log"):
        errors = open("error.log").readlines()[-50:]

    return render_template(
        "admin/auto_dashboard.html",
        errors=errors[::-1],
        patches=patches[::-1],
        restarts=restarts,
        health_score=100
    )

# ---------------------------
# Diagnostics
# ---------------------------
@app.route("/admin/diagnostics")
def diagnostics():

    logs = open("error.log", "r").read()[-5000:] if os.path.exists("error.log") else "No logs."

    prompt = f"""
    Analyze these logs and explain:
    - What caused the errors
    - Where they happen in code
    - How to fix them
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=500
        )
        analysis = res.choices[0].message.content
    except:
        analysis = "OpenAI diagnostic failed."

    return render_template("admin/diagnostics.html", logs=logs, analysis=analysis)

# ---------------------------
# Health Endpoint
# ---------------------------
@app.route("/health")
def health():
    return jsonify({"status": "healthy"}), 200

# ---------------------------
# QUIZ ROUTES (NO LOGIN)
# ---------------------------
@app.route("/")
def home():
    quizzes = get_available_quizzes()
    intro = (
        "Welcome to the Programming Language Quiz App! "
        "Take quizzes on Python, Java, and C++, "
        "review study guides, and track your progress."
    )
    return render_template("quiz/home.html", quizzes=quizzes, intro_paragraph=intro)

@app.route("/quiz/<language>")
def quiz_page(language):
    questions = load_questions(language)
    index = 0
    score = 0
    return render_template("quiz/quiz_ajax.html", language=language, questions=questions, index=index, score=score)

@app.route("/dashboard")
def dashboard():
    attempts = QuizAttempt.query.all()
    return render_template("dashboard.html", attempts=attempts)

@app.route("/log_click", methods=["POST"])
def log_click():
    data = request.get_json()
    option = data.get("option")
    print(f"[CLICK] Option clicked: {option}")  # terminal output
    return jsonify({"status": "ok"})

@app.route("/quiz/<language>/get_question")
def get_question(language):
    index = int(request.args.get("i", 0))
    questions = load_questions(language)

    if index >= len(questions):
        return jsonify({"finished": True})

    q = questions[index]

    return jsonify({
        "finished": False,
        "question_number": index + 1,
        "total_questions": len(questions),
        "question": q["question"],
        "options": q.get("options", []),
    })

@app.route("/quiz/<language>/answer", methods=["POST"])
def answer(language):
    data = request.get_json()
    question_text = data.get("question")
    selected = data.get("selected")
    correct = data.get("correct")
    options = data.get("options", [])

    explanation = generate_explanation(question_text, selected, correct, options)
    # Remove leading/trailing whitespace and normalize line starts
    lines = explanation.splitlines()
    lines = [line.lstrip() for line in lines]  # remove indentation
    explanation = "\n".join(lines)

    return jsonify({
        "correct": correct,
        "selected": selected,
        "explanation": explanation,
        "feedback_msg": "Correct!" if selected == correct else "Incorrect!"
    })

# ---------------------------
# Study Pages
# ---------------------------
@app.route("/study/python")
def study_py():
    return render_template("study/python_study.html")

@app.route("/study/cpp")
def study_cpp():
    return render_template("study/cpp_study.html")

@app.route("/study/java")
def study_java():
    return render_template("study/java_study.html")

# ---------------------------
# Trigger Error
# ---------------------------
@app.route("/trigger_error")
def trigger_error():
    raise ValueError("This is a test error for auto-maintain")

# ---------------------------
# Start App
# ---------------------------
if __name__ == "__main__":
    port = 5001
    print(f"Starting server on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)