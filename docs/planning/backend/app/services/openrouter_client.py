"""
OpenRouter LLM client for AI-powered recommendations.

OpenRouter provides unified access to multiple LLMs including:
- Claude (Anthropic)
- GPT-4 (OpenAI)
- Llama, Mistral, etc.

Used for:
- Generating preference profile summaries
- Explaining why a fragrance matches someone's taste
- Analyzing evaluation notes for sentiment
- Suggesting new fragrances to try
"""
import httpx
from typing import Optional, List, Dict, Any
import json

from app.core.config import settings


class OpenRouterClient:
    """
    Client for OpenRouter API.

    Docs: https://openrouter.ai/docs
    """

    BASE_URL = "https://openrouter.ai/api/v1"

    # Default model - good balance of quality/cost
    # Can be overridden per-request
    DEFAULT_MODEL = "anthropic/claude-3.5-sonnet"

    # Cheaper alternatives for less critical tasks
    FAST_MODEL = "anthropic/claude-3-haiku"

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.app_name = settings.APP_NAME

    @property
    def is_configured(self) -> bool:
        return bool(self.api_key)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3000",  # Required by OpenRouter
            "X-Title": self.app_name,
        }

    def chat(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """
        Send a chat completion request.

        Args:
            messages: List of {"role": "user"|"assistant"|"system", "content": "..."}
            model: Model to use (defaults to DEFAULT_MODEL)
            max_tokens: Maximum response length
            temperature: Creativity (0-1)

        Returns:
            The assistant's response text
        """
        if not self.is_configured:
            raise ValueError("OpenRouter API key not configured")

        payload = {
            "model": model or self.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

            data = response.json()
            return data["choices"][0]["message"]["content"]

    async def chat_async(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1024,
        temperature: float = 0.7,
    ) -> str:
        """Async version of chat()."""
        if not self.is_configured:
            raise ValueError("OpenRouter API key not configured")

        payload = {
            "model": model or self.DEFAULT_MODEL,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{self.BASE_URL}/chat/completions",
                headers=self._get_headers(),
                json=payload,
            )

            if response.status_code != 200:
                raise Exception(f"OpenRouter API error: {response.status_code} - {response.text}")

            data = response.json()
            return data["choices"][0]["message"]["content"]

    def chat_json(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        max_tokens: int = 1024,
    ) -> Dict[str, Any]:
        """
        Chat with JSON response parsing.
        Appends instruction to return valid JSON.
        """
        # Add JSON instruction to last user message
        messages = messages.copy()
        if messages and messages[-1]["role"] == "user":
            messages[-1] = {
                "role": "user",
                "content": messages[-1]["content"] + "\n\nRespond with valid JSON only, no markdown."
            }

        response = self.chat(messages, model=model, max_tokens=max_tokens, temperature=0.3)

        # Clean up response if wrapped in markdown
        response = response.strip()
        if response.startswith("```"):
            lines = response.split("\n")
            response = "\n".join(lines[1:-1])

        return json.loads(response)


# Singleton instance
openrouter = OpenRouterClient()
