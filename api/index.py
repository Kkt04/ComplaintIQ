import sys
from pathlib import Path

# Add project root and src/ directory to Python path
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR / "src"))
sys.path.insert(0, str(ROOT_DIR))

from complaintiq.serving.app import app
