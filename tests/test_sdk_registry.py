"""Unit tests for services/sdk_registry.py — SDK map and get_sdk."""

import pytest

from services.sdk_registry import _SDK_MAP, MODEL_OPTIONS, SDK_OPTIONS, get_sdk


class TestSDKMap:
    def test_has_four_sdks(self):
        assert len(_SDK_MAP) == 4

    def test_known_sdk_keys(self):
        assert set(_SDK_MAP.keys()) == {"openai", "anthropic", "litellm", "langchain"}


class TestSDKOptions:
    def test_has_entries(self):
        assert len(SDK_OPTIONS) >= 4

    def test_each_has_id_name_description(self):
        for opt in SDK_OPTIONS:
            assert "id" in opt
            assert "name" in opt
            assert "description" in opt


class TestModelOptions:
    def test_has_entries(self):
        assert len(MODEL_OPTIONS) >= 4

    def test_each_has_required_fields(self):
        for opt in MODEL_OPTIONS:
            assert "id" in opt
            assert "name" in opt
            assert "provider" in opt
            assert "description" in opt

    def test_providers_are_known(self):
        for opt in MODEL_OPTIONS:
            assert opt["provider"] in ("openai", "anthropic")


class TestGetSDK:
    def test_get_litellm(self):
        sdk = get_sdk("litellm")
        assert sdk is not None

    def test_get_openai(self):
        sdk = get_sdk("openai")
        assert sdk is not None

    def test_get_anthropic(self):
        sdk = get_sdk("anthropic")
        assert sdk is not None

    def test_get_langchain(self):
        sdk = get_sdk("langchain")
        assert sdk is not None

    def test_unknown_sdk_raises(self):
        with pytest.raises(ValueError, match="Unknown SDK"):
            get_sdk("nonexistent")

    def test_default_sdk(self):
        sdk = get_sdk(None)
        assert sdk is not None
