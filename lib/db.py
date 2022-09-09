import os

from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker

from lib.conf import PRODUCTION

db_host = os.environ["DB_HOST"]
db_user = os.environ["DB_USER"]
db_name = os.environ["DB_NAME"]
if "DB_PASS" in os.environ:
  db_pass = os.environ["DB_PASS"]
elif "DB_PASSWORD_FILE" in os.environ:
  with open(os.environ["DB_PASSWORD_FILE"]) as f:
    db_pass = f.read()
  if PRODUCTION: # NOTE: this only seems to happen in production
    db_pass = db_pass[:-1] # remove new line character
else:
  raise Exception("No database password specified")

dcs = f"postgresql://{db_user}:{db_pass}@{db_host}/{db_name}"
engine = create_engine(dcs)
Session = scoped_session(sessionmaker(autocommit=False, bind=engine))

def get_session():
  return Session#()

