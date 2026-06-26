"""Proxy residencial BrightData para rotación de IPs en scrappers."""

from .brightdata import BrightDataConfig, config_from_env

__all__ = ["BrightDataConfig", "config_from_env"]
