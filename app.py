from flask import Flask, render_template, request, redirect, url_for, session
import json

app = Flask(__name__)
app.secret_key = "your_secret_key"

with open("questions.json", "r") as f:
    questions = json.load(f)
total_questions = len(questions)

@app.route("/", methods=["GET"])
def start():
    session["current_question"] = 0
    session["score"] = 0
    session["show_feedback"] = False
    return redirect(url_for("quiz"))

@app.route("/quiz", methods=["GET", "POST"])
def quiz():
    if "current_question" not in session:
        return redirect(url_for("start"))

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
    session.clear()
    return f"<h2>Quiz Completed! Your score: {score}/{total_questions}</h2>"

if __name__ == "__main__":
    app.run(debug=True)