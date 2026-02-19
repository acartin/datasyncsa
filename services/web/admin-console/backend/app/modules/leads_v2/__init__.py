"""
Leads v2 module for dynamic scoring.
This module provides endpoints and services for leads with dynamic scoring v2.
"""

from .router import router
from .service import service

__all__ = ["router", "service"]