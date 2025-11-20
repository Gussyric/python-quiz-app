from flask import Flask, render_template, request, session, redirect, url_for
import json
import os

app = Flask(__name__)
app.secret_key = 'super-secret-key-123'  # Change this in production!

QUESTIONS_FOLDER = 'questions'

def load_questions(lang):
    path = os.path.join(QUESTIONS_FOLDER, f"{lang}.json")
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

# Pre-load all quizzes at startup
QUESTIONS = {
    'python': load_questions('python'),
    'cpp': load_questions('cpp'),
    'java': load_questions('java')
}

@app.route('/')
def home():
    return render_template('home.html')

@app.route('/start/<lang>')
def start_quiz(lang):
    lang = lang.lower()  # Safety: ensure case doesn't matter
    if lang not in QUESTIONS or not QUESTIONS[lang]:
        return "Quiz not found!", 404

    session.clear()
    session['lang'] = lang
    session['question_number'] = 1
    session['score'] = 0
    session['total_questions'] = len(QUESTIONS[lang])

    return redirect(url_for('quiz'))

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    lang = session.get('lang')
    if not lang or lang not in QUESTIONS or not QUESTIONS[lang]:
        return redirect(url_for('home'))

    questions = QUESTIONS[lang]
    q_idx = session['question_number'] - 1
    total = session['total_questions']

    # === Quiz Finished ===
    if q_idx >= total:
        final_score = session['score']
        session.clear()  # Optional: clean up session after quiz
        return render_template('quiz_feedback.html',
                               finished=True,
                               score=final_score,
                               total=total,
                               language=lang.capitalize())

    current_question = questions[q_idx]

    if request.method == 'POST':
        # Next button pressed
        if 'next_question' in request.form:
            session['question_number'] += 1
            return redirect(url_for('quiz'))

        # Answer submitted
        selected = request.form.get('option')
        if not selected:
            # Prevent submission without selecting (though HTML required helps)
            selected = None

        correct = current_question['answer']
        is_correct = selected == correct

        # Only increment score on first correct attempt (prevents cheating by resubmitting)
        if is_correct and session.get('answered_correctly', True):
            session['score'] += 1
        session['answered_correctly'] = False  # Mark this question as processed

        return render_template('quiz_feedback.html',
                               language=lang.capitalize(),
                               question=current_question,
                               options=current_question['options'],
                               correct=correct,
                               selected=selected,
                               is_correct=is_correct,
                               feedback_msg="Correct!" if is_correct else "Incorrect!",
                               show_feedback=True,
                               question_number=session['question_number'],
                               total_questions=total,
                               score=session['score'])

    # === Fresh Question Load (GET) ===
    session['answered_correctly'] = True  # Reset for new question
    return render_template('quiz_feedback.html',
                           language=lang.capitalize(),
                           question=current_question,
                           options=current_question['options'],
                           show_feedback=False,
                           question_number=session['question_number'],
                           total_questions=total)

if __name__ == '__main__':
    app.run(debug=True)