"""
Celery Application Configuration

Initializes the Celery app with Redis as the broker and backend.
"""

import os
from celery import Celery
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery_app = Celery(
    "axiom_worker",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks.ml_worker"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
)
