import os

os.environ["DATABASE_URL"] = "sqlite:///./jobtrack_test.db"
os.environ["JWT_SECRET"] = "test-secret-value-long-enough-for-hmac"
os.environ["ALLOWED_ORIGINS"] = "http://localhost:5173"
