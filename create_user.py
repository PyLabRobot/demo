import sys
from flask_bcrypt import generate_password_hash
from app import db, User

if __name__ == "__main__":
  db.create_all()

  email = input("email: ")
  password = input("Password: ")

  user = User(email=email, password_hash=generate_password_hash(password).decode('utf-8'))

  db.session.add(user)
  try:
    db.session.commit()
  except Exception as e:
    db.session.rollback()
    print("Error: " + str(e))
    sys.exit(1)
