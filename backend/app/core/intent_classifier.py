"""Intent classifier using Groq LLM with structured few-shot prompting.

Classifies user messages into one of 3 regulatory flows or general_chat.
Requirements: 1.4, 1.5
"""

from __future__ import annotations

import json
import logging
from typing import Literal

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

FlowIntent = Literal["incorporation", "gst_filing", "se_license", "general_chat"]

_CLASSIFICATION_PROMPT = """\
You are an intent classifier for an Indian MSME regulatory compliance assistant.

Classify the user's message into exactly ONE of these categories:
- "incorporation" — user wants to register/incorporate a company (private limited, LLP, OPC, etc.)
- "gst_filing" — user wants to register for GST, file GST returns, or handle GST compliance
- "se_license" — user wants a Shop & Establishment license, labor compliance, or local municipal registration
- "general_chat" — anything else (greetings, questions about the app, off-topic, etc.)

Respond with ONLY a JSON object: {"intent": "<category>", "confidence": <0.0-1.0>}

Examples:
User: "I want to register my startup as a private limited company"
{"intent": "incorporation", "confidence": 0.95}

User: "Help me file my quarterly GST return"
{"intent": "gst_filing", "confidence": 0.92}

User: "I need a shop license for my new cafe in Mumbai"
{"intent": "se_license", "confidence": 0.90}

User: "What is DIN?"
{"intent": "general_chat", "confidence": 0.85}

User: "Hello, how are you?"
{"intent": "general_chat", "confidence": 0.98}

User: "Register my company and also file GST"
{"intent": "incorporation", "confidence": 0.70}

User: "I opened a new shop in Bangalore, what licenses do I need?"
{"intent": "se_license", "confidence": 0.88}

User: "File my Q4 GST"
{"intent": "gst_filing", "confidence": 0.95}

Now classify this message:
User: "{message}"
"""


class IntentClassifier:
    """Classifies user messages into regulatory flow intents."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key or settings.groq_api_key
        self._model = model or settings.groq_model

    async def classify(self, message: str) -> tuple[FlowIntent, float]:
        """Classify a user message into a flow intent.

        Returns:
            Tuple of (intent, confidence).
            Falls back to ("general_chat", 0.5) on any error.
        """
        try:
            return await self._classify_via_llm(message)
        except Exception as exc:
            logger.warning("Intent classification failed (%s), falling back to general_chat", exc)
            return ("general_chat", 0.5)

    async def _classify_via_llm(self, message: str) -> tuple[FlowIntent, float]:
        """Call Groq to classify the message."""
        prompt = _CLASSIFICATION_PROMPT.format(message=message.replace('"', '\\"'))

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 64,
                    "temperature": 0.1,
                },
            )

            if response.status_code != 200:
                raise RuntimeError(f"Groq returned {response.status_code}")

            data = response.json()
            content = data["choices"][0]["message"]["content"].strip()
            return self._parse_response(content)

    def _parse_response(self, content: str) -> tuple[FlowIntent, float]:
        """Parse the JSON response from the LLM.

        Handles cases where the LLM wraps JSON in markdown code blocks.
        """
        # Strip markdown code fences if present
        if content.startswith("```"):
            lines = content.split("\n")
            content = "\n".join(
                line for line in lines if not line.startswith("```")
            ).strip()

        parsed = json.loads(content)
        intent = parsed.get("intent", "general_chat")
        confidence = float(parsed.get("confidence", 0.5))

        # Validate intent is one of the known values
        valid_intents: set[FlowIntent] = {"incorporation", "gst_filing", "se_license", "general_chat"}
        if intent not in valid_intents:
            intent = "general_chat"
            confidence = 0.5

        return (intent, min(max(confidence, 0.0), 1.0))
