from flask import Flask, render_template, request, session, jsonify, redirect, url_for
import json
import random
from openai import OpenAI
from api import API_KEY

app = Flask(__name__)
app.secret_key = "your_secret_key"

client = OpenAI(api_key = API_KEY)

def generate_explanation(question_text, user_answer, correct_answer):
    prompt = f"""
    Question: {question_text}
    Correct Answer: {correct_answer}
    User Selected: {user_answer}

    Explain in detail why the correct answer is correct and why the user's choice may be incorrect.
    """
    try:
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            max_completion_tokens=150  # updated parameter
        )
        explanation = response.choices[0].message.content.strip()
    except Exception as e:
        explanation = "No explanation available. Please try again."
        print("OpenAI API Error:", e)
    
    return explanation

def load_questions(language, num_questions=10):
    with open(f"questions/{language}.json") as f:
        all_questions = json.load(f)
    return random.sample(all_questions, min(num_questions, len(all_questions)))

@app.route("/")
def home():
    return render_template("home.html")

# ============================
# Quiz Page – Serve AJAX Template
# ============================
@app.route("/quiz/<language>")
def quiz_page(language):
    # Reset quiz if requested or first time
    reset = request.args.get("reset")
    if reset == "1" or "questions" not in session or session.get("language") != language:
        session["questions"] = load_questions(language)
        session["index"] = 0
        session["score"] = 0
        session["language"] = language

    return render_template("quiz_ajax.html", language=language)

# ============================
# AJAX GET Question
# ============================
@app.route("/quiz/<language>/get_question", methods=["GET"])
def get_question(language):
    index = session.get("index", 0)
    questions = session.get("questions", [])

    if index >= len(questions):
        return jsonify({"finished": True, "score": session.get("score",0), "total": len(questions)})

    question = questions[index]
    return jsonify({
        "finished": False,
        "question_number": index + 1,
        "total_questions": len(questions),
        "question": question["question"],
        "options": question["options"],
        "language": language
    })

# ============================
# AJAX Submit Answer
# ============================
@app.route("/quiz/<language>/answer", methods=["POST"])
def submit_answer(language):
    data = request.get_json()
    selected = data.get("selected")
    index = session.get("index", 0)
    questions = session.get("questions", [])

    if index >= len(questions):
        return jsonify({"finished": True})

    question = questions[index]
    correct = question["answer"]

    if selected == correct:
        session["score"] += 1

    explanation = generate_explanation(question["question"], selected, correct)

    session["index"] += 1

    return jsonify({
        "selected": selected,
        "correct": correct,
        "feedback_msg": "Correct!" if selected==correct else "Incorrect!",
        "explanation": explanation
    })

if __name__ == "__main__":
    app.run(debug=True)