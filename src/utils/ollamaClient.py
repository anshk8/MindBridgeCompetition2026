"""
Shared Ollama client instance.

Import `ollamaClient`, `OLLAMA_MODEL`, and `OLLAMA_REACT_MODEL` from here
instead of constructing a client in each module.
"""

import os
import ollama
from dotenv import load_dotenv

load_dotenv()

OLLAMA_MODEL       = os.getenv('OLLAMA_MODEL',       'qwen3-coder-next:q8_0')
OLLAMA_REACT_MODEL = os.getenv('OLLAMA_REACT_MODEL', 'llama3.2:latest')

_api_key = os.getenv('OLLAMA_API_KEY', '')
_headers = {"x-api-key": _api_key} if _api_key else {}

ollamaClient = ollama.Client(
    host=os.getenv('OLLAMA_HOST', 'http://localhost:11434'),
    headers=_headers,
)
