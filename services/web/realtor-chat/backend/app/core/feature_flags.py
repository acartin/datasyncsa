"""
Feature Flags para el Chat Multi-Canal

Estos flags controlan el rollout gradual de nuevas funcionalidades.
"""

from typing import Optional
import os


class FeatureFlags:
    """Feature flags configurables via environment variables."""
    
    CHANNEL_GATEWAY_ENABLED: bool = os.getenv("CHANNEL_GATEWAY_ENABLED", "true").lower() == "true"
    VERTICAL_ROUTING_ENABLED: bool = os.getenv("VERTICAL_ROUTING_ENABLED", "true").lower() == "true"
    META_ADAPTER_ENABLED: bool = os.getenv("META_ADAPTER_ENABLED", "false").lower() == "true"
    EXTERNAL_API_V1_ENABLED: bool = os.getenv("EXTERNAL_API_V1_ENABLED", "false").lower() == "true"

    SESSION_MULTICHANNEL_ENABLED: bool = os.getenv("SESSION_MULTICHANNEL_ENABLED", "false").lower() == "true"
    
    @classmethod
    def is_enabled(cls, flag_name: str) -> bool:
        """Check if a specific feature flag is enabled."""
        return getattr(cls, flag_name.upper(), False)
    
    @classmethod
    def all_flags(cls) -> dict:
        """Return all feature flags as a dictionary."""
        return {
            "CHANNEL_GATEWAY_ENABLED": cls.CHANNEL_GATEWAY_ENABLED,
            "VERTICAL_ROUTING_ENABLED": cls.VERTICAL_ROUTING_ENABLED,
            "META_ADAPTER_ENABLED": cls.META_ADAPTER_ENABLED,
            "EXTERNAL_API_V1_ENABLED": cls.EXTERNAL_API_V1_ENABLED,
            "SESSION_MULTICHANNEL_ENABLED": cls.SESSION_MULTICHANNEL_ENABLED,
        }


feature_flags = FeatureFlags()
