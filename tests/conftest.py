import os
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

# Ensure dummy test keys for unit tests if not already set
os.environ.setdefault("GROQ_API_KEY", "gsk_test_dummy_key_mock")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-dummy-key-mock")
