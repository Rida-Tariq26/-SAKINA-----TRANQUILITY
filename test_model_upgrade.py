"""
test_model_upgrade.py — Tests for Gemini Model Upgrade and Spotify Content Replacements

Verifies:
1. Centralized model configuration (model_config.py)
2. Free-tier model eligibility and absence of retired/obsolete models
3. Legacy model sanitization and fallback
4. Runner instantiation with current models in google-adk
5. Exact Spotify track and playlist replacements
"""

import os
import pytest
from unittest.mock import patch

from model_config import (
    DEFAULT_PRIMARY_MODEL,
    DEFAULT_AUXILIARY_MODEL,
    FREE_TIER_CANDIDATE_MODELS,
    get_primary_model,
    get_auxiliary_model,
    get_candidate_models,
)
from FrontendAPI import (
    create_llm_instance,
    create_chat_runner,
    create_mood_runner,
    DEFAULT_MODEL,
)


class TestModelConfiguration:
    def test_default_models_are_active_free_tier(self):
        """Ensure default models are the verified, active free-tier models."""
        assert get_primary_model() == "gemini-2.5-flash"
        assert get_auxiliary_model() == "gemini-3.5-flash-lite"

    def test_no_obsolete_models_in_candidates(self):
        """Ensure no retired models (1.5, 2.0, 2.5-flash-lite) are in candidate list."""
        candidates = get_candidate_models()
        for c in candidates:
            assert "gemini-1.5" not in c
            assert "gemini-2.0" not in c
            assert c != "gemini-2.5-flash-lite"

    def test_environment_variable_override_primary(self):
        """Ensure GEMINI_MODEL env var dynamically overrides primary model."""
        with patch.dict(os.environ, {"GEMINI_MODEL": "gemini-3.5-flash"}):
            assert get_primary_model() == "gemini-3.5-flash"
            candidates = get_candidate_models()
            assert candidates[0] == "gemini-3.5-flash"

    def test_environment_variable_override_auxiliary(self):
        """Ensure GEMINI_AUXILIARY_MODEL env var dynamically overrides auxiliary model."""
        with patch.dict(os.environ, {"GEMINI_AUXILIARY_MODEL": "gemini-3.5-flash-lite"}):
            assert get_auxiliary_model() == "gemini-3.5-flash-lite"

    def test_legacy_model_sanitization(self):
        """Ensure legacy/retired models passed to create_llm_instance are sanitized to DEFAULT_MODEL."""
        retired_models = ["gemini-1.5-flash", "gemini-1.5-pro", "gemini-2.0-flash", "gemini-2.5-flash-lite"]
        for old_model in retired_models:
            llm = create_llm_instance(old_model)
            assert llm.model == DEFAULT_MODEL

    def test_valid_models_preserved(self):
        """Ensure active free-tier models are preserved as-is."""
        valid_models = ["gemini-2.5-flash", "gemini-3.5-flash-lite", "gemini-3.5-flash"]
        for valid in valid_models:
            llm = create_llm_instance(valid)
            assert llm.model == valid

    def test_chat_and_mood_runners_created_successfully(self):
        """Ensure chat and mood runners instantiate with proper models."""
        chat_runner = create_chat_runner(user_id="test_user")
        assert chat_runner is not None
        assert chat_runner.agent.model.model == "gemini-2.5-flash"

        mood_runner = create_mood_runner(user_id="test_user")
        assert mood_runner is not None
        assert mood_runner.agent.model.model == "gemini-3.5-flash-lite"


class TestSpotifyReplacements:
    def test_spotify_content_replacement_in_source(self):
        """Verify that src/AudioPlayer.jsx contains new IDs and none of the obsolete IDs."""
        with open("src/AudioPlayer.jsx", "r", encoding="utf-8") as f:
            content = f.read()

        # Obsolete IDs must not exist
        assert "4Pj781V1h4r50w1x2zK36p" not in content
        assert "37i9dQZF1DX3O4uV0kGj9G" not in content

        # Replacement IDs must exist exactly
        assert "5BSTgtxKKHLQ1zPO1kOvkN" in content
        assert "6q7ofexPqWKonfQVUfM3Y7" in content

        # Check full URLs
        assert "https://open.spotify.com/track/5BSTgtxKKHLQ1zPO1kOvkN" in content
        assert "https://open.spotify.com/playlist/6q7ofexPqWKonfQVUfM3Y7" in content

    def test_spotify_content_replacement_in_built_assets(self):
        """Verify that the built frontend bundle in dist/assets contains the new IDs."""
        dist_assets = os.listdir("dist/assets")
        js_files = [f for f in dist_assets if f.endswith(".js")]
        assert len(js_files) > 0, "Built JS file should exist in dist/assets"

        found_track = False
        found_playlist = False
        for js_file in js_files:
            with open(os.path.join("dist/assets", js_file), "r", encoding="utf-8") as f:
                js_content = f.read()
                assert "4Pj781V1h4r50w1x2zK36p" not in js_content
                assert "37i9dQZF1DX3O4uV0kGj9G" not in js_content
                if "5BSTgtxKKHLQ1zPO1kOvkN" in js_content:
                    found_track = True
                if "6q7ofexPqWKonfQVUfM3Y7" in js_content:
                    found_playlist = True

        assert found_track, "New Spotify track must be embedded in built asset"
        assert found_playlist, "New Spotify playlist must be embedded in built asset"
