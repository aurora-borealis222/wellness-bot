import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
OWM_API_KEY = os.getenv("OWM_API_KEY")
NTX_APP_ID = os.getenv("NTX_APP_ID")
NTX_APP_KEY = os.getenv("NTX_APP_KEY")
