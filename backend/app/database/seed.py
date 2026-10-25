from sqlalchemy.orm import Session
from app.database.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.models.profile import StudentProfile
from app.models.subject import Subject, Topic
from app.models.interview import Question


def seed_data(db: Session = None) -> None:
    should_close = False
    if db is None:
        db = SessionLocal()
        should_close = True

    try:
        # Check if test user already exists
        test_user = db.query(User).filter(User.email == "test@example.com").first()
        if not test_user:
            test_user = User(
                name="Test User",
                email="test@example.com",
                hashed_password=hash_password("Test@12345"),
            )
            db.add(test_user)
            db.flush()

            # Create student profile for test user
            profile = StudentProfile(
                user_id=test_user.id,
                college="National Institute of Technology",
                branch="Computer Science and Engineering",
                graduation_year=2025,
                cgpa=8.75,
                phone="+91-9876543210",
                linkedin="https://linkedin.com/in/testuser",
                github="https://github.com/testuser",
            )
            db.add(profile)

        # Seed Subjects and Topics if not present
        if db.query(Subject).count() == 0:
            subject_data = [
                {
                    "name": "Python",
                    "description": "Python programming concepts, syntax, data structures, and best practices.",
                    "topics": [
                        {"name": "OOP", "description": "Object-oriented programming concepts in Python."},
                        {"name": "Functions", "description": "Defining and using functions, decorators, and generators."},
                        {"name": "Exception Handling", "description": "Handling errors and custom exceptions."},
                        {"name": "File Handling", "description": "Reading, writing, and context managers."},
                    ],
                },
                {
                    "name": "DBMS",
                    "description": "Database management systems, relational concepts, and SQL.",
                    "topics": [
                        {"name": "SQL", "description": "Queries, joins, indexing, and aggregations."},
                        {"name": "Normalization", "description": "Database normalization forms (1NF, 2NF, 3NF, BCNF)."},
                        {"name": "Transactions", "description": "ACID properties, isolation levels, and concurrency."},
                    ],
                },
                {
                    "name": "Java",
                    "description": "Core Java concepts, OOP principles, and standard library.",
                    "topics": [
                        {"name": "Core Java", "description": "Basics, memory model, and JVM internals."},
                        {"name": "Collections", "description": "List, Set, Map, and Queue implementations."},
                    ],
                },
                {
                    "name": "DSA",
                    "description": "Data Structures and Algorithms for technical interviews.",
                    "topics": [
                        {"name": "Arrays & Strings", "description": "Array manipulation, two pointers, sliding window."},
                        {"name": "Linked Lists", "description": "Singly, doubly, and circular linked lists."},
                    ],
                },
            ]

            topic_map = {}
            for s_info in subject_data:
                subj = Subject(name=s_info["name"], description=s_info["description"])
                db.add(subj)
                db.flush()
                for t_info in s_info["topics"]:
                    topic = Topic(subject_id=subj.id, name=t_info["name"], description=t_info["description"])
                    db.add(topic)
                    db.flush()
                    topic_map[(subj.name, topic.name)] = (subj.id, topic.id)

            # Seed sample interview questions
            sample_questions = [
                ("Python", "OOP", "What is inheritance in Python and what are its types?", "EASY"),
                ("Python", "OOP", "Explain the concept of polymorphism and method overriding with an example.", "MEDIUM"),
                ("Python", "Functions", "What is a Python function and how do *args and **kwargs work?", "EASY"),
                ("Python", "Exception Handling", "How does the try-except-finally block work in Python?", "EASY"),
                ("DBMS", "SQL", "What is a primary key and how is it different from a unique key?", "EASY"),
                ("DBMS", "SQL", "What are the differences between WHERE and HAVING clauses in SQL?", "MEDIUM"),
                ("DBMS", "Normalization", "What is database normalization and why is 3NF important?", "MEDIUM"),
                ("DBMS", "Transactions", "Explain the ACID properties in database management systems.", "MEDIUM"),
                ("Java", "Core Java", "What are the key differences between JDK, JRE, and JVM?", "EASY"),
                ("DSA", "Arrays & Strings", "How do you check if a string has all unique characters?", "EASY"),
            ]

            for s_name, t_name, q_text, diff in sample_questions:
                if (s_name, t_name) in topic_map:
                    s_id, t_id = topic_map[(s_name, t_name)]
                    q = Question(
                        subject_id=s_id,
                        topic_id=t_id,
                        question_text=q_text,
                        difficulty=diff,
                    )
                    db.add(q)

        db.commit()
    except Exception as e:
        db.rollback()
        raise e
    finally:
        if should_close:
            db.close()


if __name__ == "__main__":
    seed_data()
    print("Database seeded successfully with test user and initial content.")

