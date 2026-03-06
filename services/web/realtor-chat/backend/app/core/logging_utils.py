"""
Logging estructurado para el Chat Multi-Canal

Provee contexto de logging con los campos requeridos:
- client_id, channel, vertical, conversation_id, latency_ms
"""

import logging
import time
import json
from typing import Optional, Any, Dict
from contextvars import ContextVar
from functools import wraps
from uuid import UUID

chat_context: ContextVar[Dict[str, Any]] = ContextVar("chat_context", default={})


class StructuredLogger:
    """
    Logger con contexto estructurado para chat multi-canal.
    """
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def _build_context(self, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        context = dict(chat_context.get({}))
        if extra:
            context.update(extra)
        return context
    
    def set_context(
        self,
        client_id: Optional[str] = None,
        channel: Optional[str] = None,
        vertical: Optional[str] = None,
        conversation_id: Optional[str] = None,
    ) -> None:
        """Set the context for the current request."""
        current = dict(chat_context.get({}))
        if client_id:
            current["client_id"] = str(client_id)
        if channel:
            current["channel"] = channel
        if vertical:
            current["vertical"] = vertical
        if conversation_id:
            current["conversation_id"] = str(conversation_id)
        chat_context.set(current)
    
    def clear_context(self) -> None:
        """Clear the context."""
        chat_context.set({})
    
    def log(
        self,
        level: str,
        message: str,
        extra: Optional[Dict[str, Any]] = None,
        latency_ms: Optional[float] = None,
    ) -> None:
        """Log with structured context."""
        context = self._build_context(extra)
        
        if latency_ms is not None:
            context["latency_ms"] = round(latency_ms, 2)
        
        log_data = {
            "message": message,
            **context,
        }
        
        self.logger.log(
            getattr(logging, level.upper()),
            json.dumps(log_data),
        )
    
    def info(self, message: str, extra: Optional[Dict[str, Any]] = None, latency_ms: Optional[float] = None):
        self.log("INFO", message, extra, latency_ms)
    
    def warning(self, message: str, extra: Optional[Dict[str, Any]] = None, latency_ms: Optional[float] = None):
        self.log("WARNING", message, extra, latency_ms)
    
    def error(self, message: str, extra: Optional[Dict[str, Any]] = None, latency_ms: Optional[float] = None):
        self.log("ERROR", message, extra, latency_ms)
    
    def debug(self, message: str, extra: Optional[Dict[str, Any]] = None, latency_ms: Optional[float] = None):
        self.log("DEBUG", message, extra, latency_ms)


def log_chat_interaction(func):
    """
    Decorator para logging automático de interacciones de chat.
    """
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger = StructuredLogger(func.__module__)
        start_time = time.time()
        
        context = chat_context.get({})
        
        try:
            result = await func(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            
            logger.info(
                f"Chat interaction completed: {func.__name__}",
                extra={
                    "function": func.__name__,
                    "status": "success",
                },
                latency_ms=latency_ms,
            )
            
            return result
            
        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            
            logger.error(
                f"Chat interaction failed: {func.__name__}",
                extra={
                    "function": func.__name__,
                    "status": "error",
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                latency_ms=latency_ms,
            )
            raise
    
    return wrapper


chat_logger = StructuredLogger("chat")
