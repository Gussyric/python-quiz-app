from flask import Flask, render_template, request, redirect, url_for, session
import random
import json

app = Flask(__name__)
app.secret_key = "your_secret_key"

with open("questions.json", "r") as f:
    all_questions = json.load(f)

@app.route("/", methods=["GET"])
def start():

    selected_questions = random.sample(all_questions, 15)

    session["questions"] = selected_questions
    session["current_question"] = 0
    session["score"] = 0
    session["show_feedback"] = False

    return redirect(url_for("quiz"))

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if "questions" not in session:
        return redirect(url_for("start"))
    
    questions = session["questions"]
    total_questions = len(questions)
    current = session["current_question"]

    if request.method == "POST":
        if not session.get("show_feedback"):
            selected = request.form.get("option")
            session["selected"] = selected
            session["show_feedback"] = True
            if selected == questions[current]["answer"]:
                session["score"] += 1
            return redirect(url_for("quiz"))
        else:
            session["current_question"] += 1
            session["show_feedback"] = False
            session.pop("selected", None)
            current += 1
            if current >= total_questions:
                return redirect(url_for("result"))

    question = questions[current]
    selected = session.get("selected")
    show_feedback = session.get("show_feedback", False)
    correct = question["answer"]

    return render_template(
        "quiz_feedback.html",
        question=question,
        question_number=current+1,
        total_questions=total_questions,
        selected=selected,
        show_feedback=show_feedback,
        correct=correct
    )

@app.route("/result")
def result():
    score = session.get("score", 0)
    total_questions = len(session.get("questions", []))

    # Clear session to fully reset before restart
    session.clear()

    return f"""
    <div style='text-align:center; font-family:Arial; margin-top:50px;'>
        <h2>Quiz Completed!</h2>
        <h3>Your score: {score}/{total_questions}</h3>
        <br>
        <a href='/' style='text-decoration:none;'>
            <button style='padding:10px 20px; background-color:#4CAF50; color:white; border:none; border-radius:8px; cursor:pointer; font-size:16px;'>
                Restart Quiz
            </button>
        </a>
    </div>
    """

if __name__ == "__main__":
    app.run(debug=True)