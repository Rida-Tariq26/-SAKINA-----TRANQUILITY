"""
model_config.py — Centralized Google Gemini Model Configuration for Sakina

Provides centralized model identifiers for Sakina's conversational agent
and auxiliary AI features (guardrails judge, emotion resolution, farewell
detection, mood synthesis commentary).

Configurable via environment variables without modifying application logic.
Only currently available, free-tier eligible Google Gemini models are configured.
Never falls back to paid models.
"""

import os
from typing import List

# Primary conversational agent model (empathetic dialogue, tool calling, large context)
# Official Google AI Studio Free Tier: Active, high rate limits, multimodal reasoning
DEFAULT_PRIMARY_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.5-flash")

# Auxiliary lightweight model for fast classifications, JSON extraction, and commentary
# (LLM guardrail judge, emotion resolution, farewell detection, mood synthesis)
# Official Google AI Studio Free Tier: Ultra-low latency, fast reflections
DEFAULT_AUXILIARY_MODEL: str = os.environ.get("GEMINI_AUXILIARY_MODEL", "gemini-3.5-flash-lite")

# Configurable fallback model when the primary model experiences temporary 503, 429, or outage
DEFAULT_FALLBACK_MODEL: str = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash-lite")

# Supported free-tier eligible models for user selection & API key verification
FREE_TIER_CANDIDATE_MODELS: List[str] = [
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
]

def get_primary_model(override: str | None = None) -> str:
    """Returns the effective primary model for the conversational agent."""
    if override and override.strip():
        return override.strip()
    return os.environ.get("GEMINI_MODEL", DEFAULT_PRIMARY_MODEL)

def get_auxiliary_model(override: str | None = None) -> str:
    """Returns the effective auxiliary model for fast sub-tasks."""
    if override and override.strip():
        return override.strip()
    return os.environ.get("GEMINI_AUXILIARY_MODEL", DEFAULT_AUXILIARY_MODEL)

def get_fallback_model(override: str | None = None) -> str:
    """Returns the effective fallback model when primary encounters an outage or rate limit."""
    if override and override.strip():
        return override.strip()
    return os.environ.get("GEMINI_FALLBACK_MODEL", DEFAULT_FALLBACK_MODEL)

def get_candidate_models(primary: str | None = None) -> List[str]:
    """Returns ordered list of free-tier models to test for key verification and fallback."""
    target_primary = (primary or get_primary_model()).strip()
    candidates = [target_primary]
    
    # Add auxiliary model next
    aux = get_auxiliary_model().strip()
    if aux not in candidates:
        candidates.append(aux)

    # Add fallback model next
    fb = get_fallback_model().strip()
    if fb not in candidates:
        candidates.append(fb)

    # Add remaining free-tier eligible models
    for model_id in FREE_TIER_CANDIDATE_MODELS:
        if model_id not in candidates:
            candidates.append(model_id)
            
    return candidates
