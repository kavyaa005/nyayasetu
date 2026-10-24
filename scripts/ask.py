"""Ask an LLM one question WITHOUT our legal dataset (no RAG).

Run:  python scripts/ask.py <provider> <model> "your question"
"""
import sys

from nyayasetu.generation.llm import chat

provider, model, question = sys.argv[1], sys.argv[2], sys.argv[3]
messages = [
    {"role": "system", "content": (
        "You are a legal research assistant for Indian criminal law. India's new laws, "
        "the Bharatiya Nyaya Sanhita 2023 (BNS), Bharatiya Nagarik Suraksha Sanhita 2023 (BNSS) and "
        "Bharatiya Sakshya Adhiniyam 2023 (BSA), are in force. Answer briefly and cite exact section numbers."
    )},
    {"role": "user", "content": question},
]
result = chat(provider, model, messages, max_tokens=3000)
print(result.text)
print("-" * 70)
print(f"{result.provider}/{result.model} | prompt tokens: {result.prompt_tokens} | "
      f"answer tokens: {result.completion_tokens} | {result.latency_s}s")
