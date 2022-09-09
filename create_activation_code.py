from audioop import getsample
import sys
from app import ActivationCode
from lib.db import get_session


if __name__ == "__main__":
  ac = ActivationCode()
  session = get_session()

  session.add(ac)
  try:
    session.commit()
    print(ac.id)
  except Exception as e:
    session.rollback()
    print("Error: " + str(e))
    sys.exit(1)
