"""Shared test setup.

The unit tests check the parts of CityAssist that follow fixed rules. They never call
Groq, Gemini or Meta, so they need no internet and no real keys. Dummy keys are set here,
before the app is imported, because config.py stops the app if a key is missing.
"""
import os

os.environ.setdefault("GEMINI_API_KEY", "test-key")
os.environ.setdefault("GROQ_API_KEY", "test-key")
os.environ.setdefault("WHATSAPP_TOKEN", "test-token")
os.environ.setdefault("WHATSAPP_PHONE_ID", "123")
os.environ.setdefault("WHATSAPP_APP_SECRET", "test-secret")
os.environ.setdefault("WHATSAPP_VERIFY_TOKEN", "test-verify")
