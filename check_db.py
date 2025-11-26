from app import app, db, User, QuizAttempt
from sqlalchemy import inspect

with app.app_context():
    inspector = inspect(db.engine)
    print("Tables:", inspector.get_table_names())

    print("\nUsers:")
    for u in User.query.all():
        print(u.id, u.username, u.user_id)

    print("\nQuiz Attempts:")
    for a in QuizAttempt.query.all():
        print(a.id, a.user_id_fk, a.language, a.score, a.total_questions)