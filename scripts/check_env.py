"""Sanity check: confirms Python version and that core libraries import."""
import importlib
import sys

REQUIRED = ["pydantic", "pdfplumber", "pypdf", "requests", "dotenv", "tqdm", "pytest"]

print(f"Python {sys.version.split()[0]} at {sys.executable}")
ok = True
for name in REQUIRED:
    try:
        mod = importlib.import_module(name)
        print(f"  [OK]      {name} {getattr(mod, '__version__', '')}")
    except ImportError:
        print(f"  [MISSING] {name}")
        ok = False

in_venv = sys.prefix != sys.base_prefix
print(f"Virtual env active: {in_venv}")
sys.exit(0 if ok and in_venv else 1)
