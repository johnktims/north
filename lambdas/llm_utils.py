import json
import logging

import requests

logger = logging.getLogger()

def query_ollama(prompt: str, url: str, model: str) -> str:
  """
  Query the Ollama API with a prompt and return the generated response.
  """
  payload = {
    "model": model,
    "prompt": prompt,
    "stream": False,
    "format": "json"
  }

  logger.debug("Ollama request details", extra={
    "url": url,
    "model": model,
    "prompt_preview": prompt[:500] + ("..." if len(prompt) > 500 else ""),
    "prompt_length": len(prompt)
  })

  logger.debug("Sending request to Ollama API", extra={"url": url, "model": model})
  response = requests.post(url, json=payload)
  logger.debug("Ollama API response received", extra={"status_code": response.status_code})

  response.raise_for_status()
  result = response.json()

  logger.debug("Ollama raw response", extra={"response": json.dumps(result)[:1000] + "..."})

  return result.get("response", "")

