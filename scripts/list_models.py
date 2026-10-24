"""List model IDs available from a provider.  Run:  python scripts/list_models.py groq"""
import sys

from nyayasetu.generation.llm import list_models

for model_id in list_models(sys.argv[1]):
    print(model_id)
