import os

PRODUCTION = os.getenv("PRODUCTION") in ["1", "True", "true"]
PRINT = not PRODUCTION
