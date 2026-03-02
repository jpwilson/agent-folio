import os

from dotenv import load_dotenv

load_dotenv()

GHOSTFOLIO_URL = os.getenv("GHOSTFOLIO_URL", "http://localhost:3333")
GHOSTFOLIO_PUBLIC_URL = os.getenv("GHOSTFOLIO_PUBLIC_URL", GHOSTFOLIO_URL)
JWT_SECRET = os.getenv("JWT_SECRET", "")
DEFAULT_SDK = os.getenv("DEFAULT_SDK", "litellm")
DEFAULT_MODEL = os.getenv("DEFAULT_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8000"))
DATABASE_URL = os.getenv("DATABASE_URL", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
GRADER_TOKEN = os.getenv("GRADER_TOKEN", "")
INVEST_INSIGHT_URL = os.environ.get("INVEST_INSIGHT_URL", "http://host.docker.internal:8007")
INVEST_INSIGHT_TOKEN = os.environ.get("INVEST_INSIGHT_TOKEN", "")
