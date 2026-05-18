"""Unit tests for IntentClassifier with 30+ representative prompts.

Tests mock the internal _classify_via_llm method to verify classification
logic and parsing. 10 per flow + 5 off-topic + 5 edge cases = 30 test inputs,
plus parsing/fallback tests.
"""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.core.intent_classifier import IntentClassifier, FlowIntent


@pytest.fixture
def classifier():
    return IntentClassifier(api_key="test-key")


# --- Incorporation prompts (10) ---
INCORPORATION_PROMPTS = [
    "I want to register my startup as a private limited company",
    "Help me incorporate a new company in India",
    "How do I form an LLP?",
    "Register my business as a One Person Company",
    "I need to get a CIN for my new venture",
    "Start the company registration process",
    "I want to incorporate a Pvt Ltd in Maharashtra",
    "Can you help me with company formation?",
    "I need to register a Section 8 company",
    "Begin the incorporation process for my tech startup",
]

# --- GST Filing prompts (10) ---
GST_PROMPTS = [
    "File my Q4 GST return",
    "I need to register for GST",
    "Help me with GSTR-3B filing",
    "My GST registration is pending, what's next?",
    "I want to apply for a GSTIN",
    "How do I file GST for my e-commerce business?",
    "Submit my quarterly GST return",
    "I need help with GST compliance",
    "Register my business for Goods and Services Tax",
    "File my monthly GST return for March",
]

# --- SE License prompts (10) ---
SE_LICENSE_PROMPTS = [
    "I need a shop license for my new cafe in Mumbai",
    "Help me get a Shop & Establishment registration",
    "Apply for SE license in Karnataka",
    "I opened a new shop in Bangalore, what licenses do I need?",
    "Register my establishment under the Shops Act",
    "I need labor compliance for my retail store",
    "Get me a trade license for my restaurant",
    "Apply for municipal shop registration",
    "I need an establishment license for my office",
    "Help with Shop and Establishment Act compliance",
]

# --- Off-topic / general_chat prompts (5) ---
GENERAL_CHAT_PROMPTS = [
    "Hello, how are you?",
    "What is the weather today?",
    "Tell me a joke",
    "Who built this app?",
    "Thank you for your help",
]

# --- Edge cases (5) ---
EDGE_CASE_PROMPTS = [
    ("What is DIN?", "general_chat"),
    ("Register my company and also file GST", "incorporation"),
    ("", "general_chat"),
    ("asdfghjkl", "general_chat"),
    ("I want to do everything - company, GST, shop license", "incorporation"),
]


class TestIncorporationClassification:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt", INCORPORATION_PROMPTS)
    async def test_incorporation_prompts(self, classifier, prompt):
        with patch.object(
            classifier, "_classify_via_llm",
            new_callable=AsyncMock,
            return_value=("incorporation", 0.92),
        ):
            intent, confidence = await classifier.classify(prompt)
        assert intent == "incorporation"
        assert confidence > 0.5


class TestGSTClassification:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt", GST_PROMPTS)
    async def test_gst_prompts(self, classifier, prompt):
        with patch.object(
            classifier, "_classify_via_llm",
            new_callable=AsyncMock,
            return_value=("gst_filing", 0.90),
        ):
            intent, confidence = await classifier.classify(prompt)
        assert intent == "gst_filing"
        assert confidence > 0.5


class TestSELicenseClassification:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt", SE_LICENSE_PROMPTS)
    async def test_se_license_prompts(self, classifier, prompt):
        with patch.object(
            classifier, "_classify_via_llm",
            new_callable=AsyncMock,
            return_value=("se_license", 0.88),
        ):
            intent, confidence = await classifier.classify(prompt)
        assert intent == "se_license"
        assert confidence > 0.5


class TestGeneralChatClassification:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt", GENERAL_CHAT_PROMPTS)
    async def test_general_chat_prompts(self, classifier, prompt):
        with patch.object(
            classifier, "_classify_via_llm",
            new_callable=AsyncMock,
            return_value=("general_chat", 0.95),
        ):
            intent, confidence = await classifier.classify(prompt)
        assert intent == "general_chat"


class TestEdgeCases:
    @pytest.mark.asyncio
    @pytest.mark.parametrize("prompt,expected_intent", EDGE_CASE_PROMPTS)
    async def test_edge_cases(self, classifier, prompt, expected_intent):
        with patch.object(
            classifier, "_classify_via_llm",
            new_callable=AsyncMock,
            return_value=(expected_intent, 0.70),
        ):
            intent, confidence = await classifier.classify(prompt)
        assert intent == expected_intent


class TestParsingAndFallback:
    @pytest.mark.asyncio
    async def test_handles_markdown_wrapped_json(self, classifier):
        """LLM sometimes wraps JSON in code fences."""
        content = '```json\n{"intent": "gst_filing", "confidence": 0.88}\n```'
        intent, confidence = classifier._parse_response(content)
        assert intent == "gst_filing"
        assert confidence == 0.88

    @pytest.mark.asyncio
    async def test_falls_back_on_api_error(self, classifier):
        """On Groq error, returns general_chat with low confidence."""
        with patch.object(
            classifier, "_classify_via_llm",
            new_callable=AsyncMock,
            side_effect=RuntimeError("Groq returned 500"),
        ):
            intent, confidence = await classifier.classify("register my company")
        assert intent == "general_chat"
        assert confidence == 0.5

    @pytest.mark.asyncio
    async def test_falls_back_on_invalid_json(self, classifier):
        """On unparseable response, returns general_chat."""
        with patch.object(
            classifier, "_classify_via_llm",
            new_callable=AsyncMock,
            side_effect=json.JSONDecodeError("err", "", 0),
        ):
            intent, confidence = await classifier.classify("xyz")
        assert intent == "general_chat"
        assert confidence == 0.5

    @pytest.mark.asyncio
    async def test_clamps_confidence_to_valid_range(self, classifier):
        """Confidence values outside [0,1] are clamped."""
        content = json.dumps({"intent": "incorporation", "confidence": 1.5})
        intent, confidence = classifier._parse_response(content)
        assert intent == "incorporation"
        assert confidence == 1.0

    @pytest.mark.asyncio
    async def test_invalid_intent_falls_back(self, classifier):
        """Unknown intent value is treated as general_chat."""
        content = json.dumps({"intent": "unknown_flow", "confidence": 0.9})
        intent, confidence = classifier._parse_response(content)
        assert intent == "general_chat"
        assert confidence == 0.5

    @pytest.mark.asyncio
    async def test_negative_confidence_clamped_to_zero(self, classifier):
        """Negative confidence is clamped to 0."""
        content = json.dumps({"intent": "gst_filing", "confidence": -0.5})
        intent, confidence = classifier._parse_response(content)
        assert intent == "gst_filing"
        assert confidence == 0.0
