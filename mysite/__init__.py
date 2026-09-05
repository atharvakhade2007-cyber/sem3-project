# Expose the Celery app when a worker/beat process starts (`celery -A mysite`).
# Guarded so plain Django management commands keep working even when Celery
# has not been installed yet — the daily quiz still generates lazily on demand.
try:
    from .celery import app as celery_app
    __all__ = ("celery_app",)
except ImportError:
    pass
