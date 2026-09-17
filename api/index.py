# Vercel serverless entry point.
# Vercel's Python runtime imports the ASGI app named `app` from this module.
# We re-export the FastAPI app built in app.py.
from app import app  # noqa: F401  (expose ASGI app to Vercel runtime)
