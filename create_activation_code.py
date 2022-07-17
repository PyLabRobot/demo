import sys
from app import db, ActivationCode

if __name__ == "__main__":
  ac = ActivationCode()

  db.session.add(ac)
  try:
    db.session.commit()
    print(ac.id)
  except Exception as e:
    db.session.rollback()
    print("Error: " + str(e))
    sys.exit(1)
