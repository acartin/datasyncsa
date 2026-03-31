import json
import os
import logging
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger("policy_loader")

DEFAULT_POLICY_PATH = "/app/schemas/chat_vertical_policy.v1.json"


class PolicyLoader:
    """
    Carga la política de chat desde el archivo JSON central.
    """

    _cache: Optional[Dict[str, Any]] = None

    @classmethod
    def load_policy(cls, path: Optional[str] = None) -> Dict[str, Any]:
        if cls._cache is not None:
            return cls._cache

        policy_path = path or os.getenv("CHAT_VERTICAL_POLICY_PATH", DEFAULT_POLICY_PATH)

        try:
            with open(policy_path, "r") as f:
                policy = json.load(f)
                cls._cache = policy
                logger.info(f"Loaded chat vertical policy from {policy_path}")
                return policy
        except FileNotFoundError:
            logger.error(f"Policy file not found: {policy_path}")
            raise
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in policy file: {e}")
            raise

    @classmethod
    def clear_cache(cls) -> None:
        cls._cache = None

    @classmethod
    def get_allowed_components(cls, vertical: str, channel: str) -> List[str]:
        policy = cls.load_policy()
        verticals = policy.get("verticals", {})
        fallback_vertical = policy.get("fallback", {}).get("unknown_vertical", "generic")
        vertical_config = verticals.get(vertical, {}) or verticals.get(fallback_vertical, {})
        channels = vertical_config.get("channels", {})

        if channel in channels:
            return channels[channel]

        fallback_channel = policy.get("fallback", {}).get("unknown_channel", "api")
        if channel != fallback_channel and fallback_channel in channels:
            return channels[fallback_channel]

        return vertical_config.get("allowed_components", ["chat_text"])

    @classmethod
    def get_fallback_component(cls) -> str:
        policy = cls.load_policy()
        return policy.get("fallback", {}).get("unsupported_component", "chat_text")


def load_policy(path: Optional[str] = None) -> Dict[str, Any]:
    return PolicyLoader.load_policy(path)


def get_allowed_components(vertical: str, channel: str) -> List[str]:
    return PolicyLoader.get_allowed_components(vertical, channel)
