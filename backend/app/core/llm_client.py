"""Groq streaming LLM client with retry and scripted fallback.

Implements:
- 3 retry attempts with exponential backoff (Req 5.6)
- 15-second timeout per request
- Scripted fallback narration when Groq is unreachable (Req 7.4)
"""

from __future__ import annotations

import asyncio
import logging
from typing import AsyncIterator

import httpx

from ..config import settings

logger = logging.getLogger(__name__)

# Timeout per Groq request (Req 5.6)
_REQUEST_TIMEOUT = 15.0
_MAX_RETRIES = 3


class GroqError(Exception):
    """Raised when Groq API returns a non-2xx response."""

    def __init__(self, status_code: int, detail: str = ""):
        self.status_code = status_code
        self.detail = detail
        super().__init__(f"Groq API error {status_code}: {detail}")


# ---------------------------------------------------------------------------
# Scripted fallback narration (per-flow, per-step canned text)
# Used when Groq is down so the demo still works (Req 7.4)
# ---------------------------------------------------------------------------

SCRIPTED_FALLBACK: dict[str, str] = {
    # Incorporation flow
    "name_reserve": (
        "Checking name availability with the Registrar of Companies... "
        "The proposed name has been reserved successfully under Section 4(4) "
        "of the Companies Act, 2013."
    ),
    "din_apply": (
        "Submitting Director Identification Number application via SPICe+ form... "
        "DIN has been allotted to the proposed directors."
    ),
    "dsc_issue": (
        "Requesting Digital Signature Certificates from a licensed Certifying Authority... "
        "DSCs issued and linked to the directors' Aadhaar."
    ),
    "moa_aoa": (
        "Drafting the Memorandum of Association and Articles of Association... "
        "Documents prepared with standard Table F clauses for a private limited company."
    ),
    "spice_b": (
        "Filing SPICe+ Part B with MCA portal... "
        "Form submitted. Awaiting registrar verification."
    ),
    "human_review": (
        "All documents are ready for your review. "
        "Please verify the details before final submission to the Registrar."
    ),
    "pan_tan": (
        "Allotting PAN and TAN via integrated CBDT linkage... "
        "PAN and TAN numbers generated for the new entity."
    ),
    "cin_gen": (
        "Generating Corporate Identity Number... "
        "Your company has been successfully incorporated!"
    ),
    # GST Filing flow
    "gst_eligibility": (
        "Checking GST registration eligibility based on turnover threshold... "
        "Your business exceeds the ₹40L threshold and requires GST registration."
    ),
    "gst_docs": (
        "Gathering required documents: PAN, Aadhaar, business address proof, "
        "bank statement... All documents verified."
    ),
    "gst_application": (
        "Submitting GST REG-01 application on the GST portal... "
        "Application reference number generated."
    ),
    "gst_verification": (
        "Application is under verification by the tax officer... "
        "No discrepancies found in the submitted documents."
    ),
    "gst_human_review": (
        "Your GST application details are ready for review. "
        "Please confirm the business details before final submission."
    ),
    "gst_certificate": (
        "GST registration certificate issued. "
        "Your GSTIN is now active and you can begin filing returns."
    ),
    # Shop & Establishment License flow
    "se_eligibility": (
        "Verifying eligibility under the state's Shops & Establishments Act... "
        "Your business type qualifies for registration."
    ),
    "se_docs": (
        "Collecting required documents: identity proof, address proof, "
        "rent agreement, photos... All documents in order."
    ),
    "se_application": (
        "Submitting application to the local municipal authority... "
        "Application accepted and acknowledgment number issued."
    ),
    "se_human_review": (
        "Application details are ready for your review. "
        "Please verify the establishment details before final submission."
    ),
    "se_certificate": (
        "Shop & Establishment license has been issued. "
        "Your business is now compliant with local labor regulations."
    ),
    # Generic fallback for unknown steps
    "_default": (
        "Processing this step... "
        "The operation completed successfully."
    ),
}


class LLMClient:
    """Streaming LLM client backed by Groq with retry + scripted fallback."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = _REQUEST_TIMEOUT,
        max_retries: int = _MAX_RETRIES,
    ):
        self._api_key = api_key or settings.groq_api_key
        self._model = model or settings.groq_model
        self._timeout = timeout
        self._max_retries = max_retries

    async def stream_narration(self, prompt: str, step_id: str = "") -> AsyncIterator[str]:
        """Stream narration tokens. Falls back to scripted text if Groq fails.

        Args:
            prompt: The narration prompt to send to the LLM.
            step_id: Used to look up scripted fallback text.

        Yields:
            Individual text tokens (words/chunks).
        """
        for attempt in range(self._max_retries):
            try:
                async for token in self._groq_stream(prompt):
                    yield token
                return
            except (asyncio.TimeoutError, httpx.TimeoutException, GroqError) as exc:
                wait = 2**attempt
                logger.warning(
                    "Groq attempt %d/%d failed (%s), retrying in %ds",
                    attempt + 1,
                    self._max_retries,
                    exc,
                    wait,
                )
                await asyncio.sleep(wait)

        # All retries exhausted → scripted fallback (Req 7.4)
        logger.warning("Groq unreachable after %d attempts, using scripted fallback", self._max_retries)
        async for token in self._scripted_fallback(step_id):
            yield token

    async def _groq_stream(self, prompt: str) -> AsyncIterator[str]:
        """Call Groq chat completions API with streaming."""
        if not self._api_key:
            raise GroqError(401, "No GROQ_API_KEY configured")

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            async with client.stream(
                "POST",
                "https://api.groq.com/openai/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a regulatory compliance narrator for Indian MSMEs. "
                                "Describe what is happening in the current step in 2-3 concise sentences. "
                                "Use professional but accessible language."
                            ),
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "stream": True,
                    "max_tokens": 256,
                    "temperature": 0.7,
                },
            ) as response:
                if response.status_code != 200:
                    body = await response.aread()
                    raise GroqError(response.status_code, body.decode(errors="replace"))

                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = line[6:]
                    if data == "[DONE]":
                        return
                    # Parse the SSE JSON chunk
                    import json

                    try:
                        chunk = json.loads(data)
                    except json.JSONDecodeError:
                        continue
                    delta = chunk.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content")
                    if content:
                        yield content

    async def _scripted_fallback(self, step_id: str) -> AsyncIterator[str]:
        """Yield scripted narration word-by-word with small delays to simulate streaming."""
        text = SCRIPTED_FALLBACK.get(step_id, SCRIPTED_FALLBACK["_default"])
        words = text.split()
        for i, word in enumerate(words):
            token = word if i == 0 else f" {word}"
            yield token
            # Small delay to simulate streaming feel
            await asyncio.sleep(0.03)
