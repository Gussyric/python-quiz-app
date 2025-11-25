from flask import Flask, render_template, request, session, jsonify, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import os
import json
import random
from openai import OpenAI
from api import API_KEY

# ============================
# Flask App Setup
# ============================
app = Flask(__name__)
app.secret_key = "your_secret_key"

# Ensure instance folder exists
basedir = os.path.abspath(os.path.dirname(__file__))
instance_path = os.path.join(basedir, "instance")
os.makedirs(instance_path, exist_ok=True)

# Database setup
db_path = os.path.join(instance_path, "users.db")
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ============================
# Database Models
# ============================
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

# ============================
# Initialize Database
# ============================
with app.app_context():
    db.create_all()

# ============================
# OpenAI Client
# ============================
client = OpenAI(api_key=API_KEY)

# ============================
# Utility Functions
# ============================

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

    except Exception as e:
        print("OpenAI API Error:", e)
        explanation = "No explanation available. Please try again."

    return explanation.strip()

def load_questions(language, num_questions=10):
    with open(f"questions/{language}.json") as f:
        all_questions = json.load(f)
    return random.sample(all_questions, min(num_questions, len(all_questions)))

# ============================
# ROUTES
# ============================
@app.route('/home')
def home():
    if 'user' not in session:
        return redirect(url_for('login'))

    quizzes = get_available_quizzes()
    return render_template('home.html', quizzes=quizzes)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        user_id = request.form.get("user_id")

        # Check if user exists
        user = User.query.filter_by(username=username, user_id=user_id).first()
        if not user:
            # Create new user if not found
            user = User(username=username, user_id=user_id)
            db.session.add(user)
            db.session.commit()

        # Store in session
        session["user"] = username
        session["user_id"] = user_id

        return redirect(url_for("home"))

    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


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

    return render_template("quiz_ajax.html", language=language)


@app.route("/quiz/<language>/get_question", methods=["GET"])
def get_question(language):
    if "user" not in session:
        return redirect(url_for("login"))

    index = session.get("index", 0)
    questions = session.get("questions", [])
    total_questions = len(questions)
    current_score = session.get("score", 0)

    # FINISHED CASE
    if index >= total_questions:
        user = User.query.filter_by(username=session['user'], user_id=session['user_id']).first()
        if user:
            attempt = QuizAttempt(
                score=current_score,
                total_questions=total_questions,
                language=language,
                user_id_fk=user.id
            )
            db.session.add(attempt)
            db.session.commit()

        return jsonify({
            "finished": True,
            "score": current_score,
            "total_questions": total_questions,
            "question_number": total_questions
        })

    # QUESTION CASE
    question = questions[index]
    options = question.get("options", [])

    return jsonify({
        "finished": False,
        "question_number": index + 1,
        "total_questions": total_questions,
        "question": question["question"],
        "options": options,
        "language": language,
        "score": current_score
    })


@app.route("/quiz/<language>/answer", methods=["POST"])
def submit_answer(language):
    if "user" not in session:
        return redirect(url_for("login"))

    data = request.get_json()
    selected = data.get("selected")

    index = session.get("index", 0)
    questions = session.get("questions", [])
    total_questions = len(questions)

    # FINISHED CASE
    if index >= total_questions:
        return jsonify({
            "finished": True,
            "score": session.get("score", 0),
            "total_questions": total_questions,
            "question_number": total_questions
        })

    question = questions[index]
    correct = question.get("answer")
    options = question.get("options", [])

    if selected == correct:
        session["score"] += 1

    explanation = generate_explanation(question["question"], selected, correct)

    session["index"] += 1

    return jsonify({
        "finished": False,
        "question_number": index + 1,
        "total_questions": total_questions,
        "score": session.get("score", 0),
        "question": question["question"],
        "options": options,
        "correct": correct,
        "selected": selected,          # ← **FIXED**
        "explanation": explanation,
        "feedback_msg": "Correct!" if selected == correct else "Incorrect!"
    })


@app.route("/dashboard")
def dashboard():
    if "user" not in session:
        return redirect(url_for("login"))

    user = User.query.filter_by(username=session['user'], user_id=session['user_id']).first()
    attempts = user.attempts if user else []
    return render_template("dashboard.html", attempts=attempts)

@app.route("/")
def index():
    return redirect(url_for("login"))

@app.route("/study/python")
def python_study():
    if "user" not in session:
        return redirect(url_for("login"))
    return render_template("python_study.html")

if __name__ == "__main__":
    app.run(debug=True)