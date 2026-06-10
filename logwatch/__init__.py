"""LogWatch — DevOps Log Monitoring Tool."""
import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

__version__ = "1.0.0"
__author__ = os.environ.get("LOGWATCH_AUTHOR", "LogWatch")
