from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from api import API_KEY
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
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY not found in environment!")
client = OpenAI(api_key=api_key)

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
# Database Models
# ---------------------------
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), nullable=False)
    user_id = db.Column(db.String(20), nullable=False)
    attempts = db.relationship('QuizAttempt', backref='user', lazy=True)

class QuizAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    score = db.Column(db.Integer, nullable=False)
    total_questions = db.Column(db.Integer, nullable=False)
    language = db.Column(db.String(50), nullable=False)
    user_id_fk = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Initialize DB
with app.app_context():
    db.create_all()

# ---------------------------
# OpenAI Client
# ---------------------------
# client = OpenAI(api_key=API_KEY)

# ---------------------------
# Utility Functions
# ---------------------------
def get_available_quizzes():
    quiz_folder = os.path.join(os.getcwd(), "questions")
    return [f.replace(".json", "") for f in os.listdir(quiz_folder) if f.endswith(".json")]

def generate_explanation(question_text, user_answer, correct_answer):
    prompt = f"""
    Question: {question_text}
    Correct Answer: {correct_answer}
    User Selected: {user_answer}

    Explain briefly why the correct answer is correct and why the user's choice may be incorrect.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=120,
            stream=True
        )
        explanation = ""
        for event in response:
            if hasattr(event.choices[0].delta, "content") and event.choices[0].delta.content:
                explanation += event.choices[0].delta.content
    except Exception:
        explanation = "No explanation available. Please try again."

    return explanation.strip()

def load_questions(language, num_questions=10):
    with open(f"questions/{language}.json") as f:
        all_questions = json.load(f)
    return random.sample(all_questions, min(num_questions, len(all_questions)))

# ---------------------------
# Admin Routes
# ---------------------------

@app.route("/admin/apply_patch", methods=["POST"])
def apply_patch():
    if "user" not in session:
        return redirect(url_for("login"))

    patch_text = request.form["patch"]
    file_path = request.form["file"]

    with open(file_path, "r") as f:
        original = f.readlines()

    with open(file_path, "w") as f:
        f.writelines(difflib.restore(patch_text.splitlines(), 1))

    return "<h1>Patch Applied!</h1><p>Your code has been updated.</p>"


@app.route("/admin/auto_fix", methods=["POST"])
def auto_fix():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    # Support both JSON and form requests
    if request.is_json:
        file_path = request.json.get("file")
    else:
        file_path = request.form.get("file")

    if not file_path or not os.path.exists(file_path):
        return jsonify({"error": "Invalid file path"}), 400

    # --- Read the target source file ---
    try:
        with open(file_path, "r") as f:
            code = f.read()
    except Exception as e:
        return jsonify({"error": f"Error reading file: {e}"}), 500

    # --- Read last 5k of error.log for context ---
    try:
        with open("error.log", "r") as f:
            error_log = f.read()[-5000:]
    except:
        error_log = "No error logs available."

    # --- OpenAI prompt ---
    prompt = f"""
    You are an expert software engineer.

    Based on the following Python/Flask code and error logs,
    produce ONLY a unified diff patch. The patch must follow
    standard 'diff -u' format and must not include explanations.

    Code:
    {code}

    Errors:
    {error_log}

    Output only the patch.
    """

    # --- Generate patch from OpenAI ---
    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=400
        )
        patch = getattr(response.choices[0].message, "content", "No patch returned.")
        print("\n=== AUTO FIX GENERATED PATCH ===\n", patch, "\n=== END PATCH ===\n")
    except Exception as e:
        patch = f"OpenAI Error: {e}"
        return jsonify({"error": patch}), 500

    # ==========================================================
    #                  PATCH VALIDATION + APPLY
    # ==========================================================

    # Patch MUST start with correct header
    if not patch.startswith(f"--- {file_path}"):
        return jsonify({
            "error": "Patch rejected: invalid diff header.",
            "patch": patch
        }), 400

    # Must contain @@ hunk unless empty diff
    if "@@" not in patch and patch.strip() != f"--- {file_path}\n+++ {file_path}":
        return jsonify({
            "error": "Patch rejected: missing @@ diff hunk.",
            "patch": patch
        }), 400

    import difflib

    original_lines = open(file_path).read().splitlines(keepends=True)
    patch_lines = patch.splitlines(keepends=True)

    # Apply patch
    try:
        patched_lines = difflib.patch_from_unified_diff(patch_lines, original_lines)
    except Exception as e:
        return jsonify({
            "error": f"Patch parsing failed: {e}",
            "patch": patch
        }), 500

    if patched_lines is None:
        return jsonify({
            "error": "Failed to apply patch (patch returned None).",
            "patch": patch
        }), 500

    # Write patched file
    try:
        with open(file_path, "w") as f:
            f.writelines(patched_lines)
        apply_status = "ok"
    except Exception as e:
        apply_status = f"Failed to write patched file: {e}"

    # ==========================================================
    #                      MODULE RELOAD
    # ==========================================================
    module_name = os.path.splitext(os.path.basename(file_path))[0]

    if apply_status == "ok":
        if module_name in sys.modules:
            try:
                reload(sys.modules[module_name])
                reload_status = f"Module {module_name} reloaded successfully."
            except Exception as e:
                reload_status = f"Failed to reload module {module_name}: {e}"
        else:
            reload_status = f"Module {module_name} not imported yet, will load on first import."
    else:
        reload_status = "Module reload skipped due to patch failure."

    # ==========================================================
    #                 SAVE PATCH TO STATE HISTORY
    # ==========================================================
    state = load_state()
    patches = state.get("patches", [])

    patches.append({
        "file": file_path,
        "time": time.strftime('%Y-%m-%d %H:%M:%S'),
        "patch": patch
    })

    state["patches"] = patches[-50:]
    save_state(state)

    return jsonify({
        "file": file_path,
        "patch": patch,
        "apply_status": apply_status,
        "reload_status": reload_status
    })

# ---------------------------
# Dashboard State
# ---------------------------
STATE_FILE = "auto_maintain_state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r") as f:
                return json.load(f)
        except:
            return {"patches": [], "restarts": 0}
    return {"patches": [], "restarts": 0}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)

@app.route("/admin/auto_dashboard")
def auto_dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    state = load_state()
    patches = state.get("patches", [])
    restarts = state.get("restarts", 0)

    errors = []
    if os.path.exists("error.log"):
        with open("error.log", "r") as f:
            errors = f.readlines()[-50:]

    logs = []
    if os.path.exists("auto_maintain.log"):
        with open("auto_maintain.log", "r") as f:
            logs = f.readlines()[-200:]

    for line in logs:
        if "Patch applied" in line and line not in patches:
            patches.append(line)
        if "Flask started with PID" in line:
            restarts += 1

    state["patches"] = patches[-50:]
    state["restarts"] = restarts
    save_state(state)

    health_score = 100
    if any("Traceback" in line for line in errors):
        health_score -= 30
    if restarts > 2:
        health_score -= 20
    if len(patches) > 5:
        health_score -= 10

    return render_template(
        "admin/auto_dashboard.html",
        errors=errors[::-1],
        patches=patches[::-1],
        restarts=restarts,
        health_score=health_score
    )

# ---------------------------
# Auto-Maintain JSON State Endpoint
# ---------------------------
@app.route("/admin/auto_dashboard_state")
def auto_dashboard_state():
    if "user" not in session:
        return jsonify({"error": "Unauthorized"}), 401

    state = load_state()
    patches = state.get("patches", [])
    restarts = state.get("restarts", 0)

    # Get last 50 errors
    errors = []
    if os.path.exists("error.log"):
        with open("error.log", "r") as f:
            errors = f.readlines()[-50:]

    # Calculate health score
    health_score = 100
    if any("Traceback" in line for line in errors):
        health_score -= 30
    if restarts > 2:
        health_score -= 20
    if len(patches) > 5:
        health_score -= 10

    return jsonify({
        "patches": patches[-50:],
        "restarts": restarts,
        "errors": errors[::-1],  # newest first
        "health_score": health_score
    })


@app.route("/admin/diagnostics")
def diagnostics():
    if "user" not in session:
        return redirect(url_for("login"))

    logs = "No logs found."
    try:
        with open("error.log", "r") as f:
            logs = f.read()[-5000:]
    except:
        pass

    prompt = f"""
    You are an expert Python/Flask debugging assistant.

    Analyze these logs and explain:
    - What caused the errors
    - Where in the code they originate
    - How to fix them
    - Security/performance risks
    """

    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=300
        )
        analysis = getattr(res.choices[0].message, "content", "No analysis available.")
    except Exception as e:
        analysis = f"OpenAI Error: {e}"

    return render_template("admin/diagnostics.html", logs=logs, analysis=analysis)

@app.route("/health")
def health():
    # Always returns 200 OK
    return "OK", 200

# Keep your existing /admin/health if needed for admin dashboard
@app.route("/admin/health")
def admin_health():
    if "user" not in session:
        return redirect(url_for("login"))
    size = os.path.getsize("error.log") if os.path.exists("error.log") else 0
    stats = {
        "error_file_size": size,
        "recent_errors": size > 20000,
        "status": "healthy" if size < 5000 else "unhealthy",
    }
    prompt = f"Rate the app health from 1–100 based on:\n{stats}"
    try:
        res = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=200
        )
        report = getattr(res.choices[0].message, "content", "No report produced.")
    except Exception as e:
        report = f"Error generating report: {e}"
    return report

@app.route("/admin/pending_patches")
def pending():
    if "user" not in session:
        return redirect(url_for("login"))

    text = ""
    if os.path.exists("pending_patch.diff"):
        with open("pending_patch.diff", "r") as f:
            text = f.read()

    return render_template("admin/pending_patches.html", patch_text=text)

# ---------------------------
# Quiz / Study Routes
# ---------------------------

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        user_id = request.form.get("user_id")

        user = User.query.filter_by(username=username, user_id=user_id).first()
        if not user:
            user = User(username=username, user_id=user_id)
            db.session.add(user)
            db.session.commit()

        session["user"] = username
        session["user_id"] = user_id
        return redirect(url_for("home"))

    return render_template("auth/login.html")

@app.route("/home")
def home():
    quizzes = get_available_quizzes()
    intro = ("Welcome to the Programming Language Quiz App! "
             "Here you can take quizzes on Python, Java, and C++, "
             "review study guides, and track your progress on the dashboard.")
    return render_template("quiz/home.html", quizzes=quizzes, intro_paragraph=intro)

@app.route("/quiz/<language>")
def quiz_page(language):
    if "user" not in session:
        return redirect(url_for("login"))

    reset = request.args.get("reset")
    if reset == "1" or "questions" not in session or session.get("language") != language:
        session["questions"] = load_questions(language)
        session["index"] = 0
        session["score"] = 0
        session["language"] = language

    return render_template("quiz/quiz_ajax.html", language=language)

@app.route("/quiz/<language>/get_question")
def get_question(language):
    if "user" not in session:
        return redirect(url_for("login"))

    index = session.get("index", 0)
    questions = session.get("questions", [])
    total = len(questions)
    score = session.get("score", 0)

    if index >= total:
        user = User.query.filter_by(username=session["user"], user_id=session["user_id"]).first()
        if user:
            attempt = QuizAttempt(score=score, total_questions=total,
                                  language=language, user_id_fk=user.id)
            db.session.add(attempt)
            db.session.commit()

        return jsonify({"finished": True, "score": score,
                        "total_questions": total, "question_number": total})

    q = questions[index]
    return jsonify({
        "finished": False,
        "question_number": index + 1,
        "total_questions": total,
        "question": q["question"],
        "options": q.get("options", []),
        "language": language,
        "score": score
    })

@app.route("/quiz/<language>/answer", methods=["POST"])
def answer(language):
    if "user" not in session:
        return redirect(url_for("login"))

    data = request.get_json()
    selected = data.get("selected")

    index = session.get("index", 0)
    questions = session.get("questions", [])
    total = len(questions)

    if index >= total:
        return jsonify({"finished": True,
                        "score": session.get("score", 0),
                        "total_questions": total,
                        "question_number": total})

    q = questions[index]
    correct = q.get("answer")

    if selected == correct:
        session["score"] += 1

    explanation = generate_explanation(q["question"], selected, correct)
    session["index"] += 1

    return jsonify({
        "finished": False,
        "question_number": index + 1,
        "total_questions": total,
        "score": session.get("score", 0),
        "question": q["question"],
        "options": q.get("options", []),
        "correct": correct,
        "selected": selected,
        "explanation": explanation,
        "feedback_msg": "Correct!" if selected == correct else "Incorrect!"
    })

@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))
    user = User.query.filter_by(username=session["user"], user_id=session["user_id"]).first()
    atts = user.attempts if user else []
    return render_template("quiz/dashboard.html", attempts=atts)


@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/study/python")
def study_py():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("study/python_study.html")

@app.route("/study/cpp")
def study_cpp():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("study/cpp_study.html")

@app.route("/study/java")
def study_java():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("study/java_study.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/trigger_error")
def trigger_error():
    raise ValueError("This is a test error for auto-maintain")

# Lazy import — safe even if broken
try:
    import broken_module
except Exception as e:
    print("Lazy import failed:", e)

# ---------------------------
# Run App
# ---------------------------
if __name__ == "__main__":
    port = 5001
    print(f"Starting server on http://127.0.0.1:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)