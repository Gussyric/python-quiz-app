from flask import Flask, render_template, request, session, redirect, url_for
import json
import random

app = Flask(__name__)
app.secret_key = "your_secret_key"

def load_questions(language, num_questions=10):
    # Load all questions for the chosen language
    with open(f"questions/{language}.json") as f:
        all_questions = json.load(f)
    # Pick 10 random questions
    return random.sample(all_questions, min(num_questions, len(all_questions)))

@app.route("/")
def home():
    return render_template("home.html")

# ============================
# HOME PAGE – Language Select
# ============================
@app.route("/quiz/<language>", methods=["GET", "POST"])
def quiz(language):
    # Load questions if starting new quiz or switching language
    if "questions" not in session or session.get("language") != language:
        session["questions"] = load_questions(language)
        session["index"] = 0
        session["score"] = 0
        session["language"] = language

    # Reset quiz if requested
    if request.args.get("reset") == "1":
        session["questions"] = load_questions(language)
        session["index"] = 0
        session["score"] = 0
        return redirect(url_for("quiz", language=language))

    questions = session["questions"]
    index = session["index"]

    # Quiz finished
    if index >= len(questions):
        return render_template(
            "quiz_feedback.html",
            finished=True,
            score=session["score"],
            total=len(questions),
            language=language
        )

    question = questions[index]
    options = question["options"]

    # Handle POST
    if request.method == "POST":
        # If coming from Next Question button
        if "next_question" in request.form:
            session["index"] += 1
            return redirect(url_for("quiz", language=language))

        # Otherwise, handle answer submission
        selected = request.form.get("option")
        correct = question["answer"]

        if selected == correct:
            session["score"] += 1

        session["selected"] = selected
        session["correct"] = correct

        feedback_msg = "Correct!" if selected == correct else "Incorrect!"

        return render_template(
            "quiz_feedback.html",
            question=question,
            options=options,
            question_number=index + 1,
            total_questions=len(questions),
            selected=selected,
            correct=correct,
            show_feedback=True,
            feedback_msg=feedback_msg,
            language=language,
            finished=False
        )

    # GET → show question normally
    return render_template(
        "quiz_feedback.html",
        question=question,
        options=options,
        question_number=index + 1,
        total_questions=len(questions),
        show_feedback=False,
        language=language,
        finished=False
    )
if __name__ == "__main__":
    app.run(debug=True)