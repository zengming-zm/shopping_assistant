import logging
from typing import Dict, Any, Optional
from datetime import datetime
from langfuse import Langfuse
from langfuse.decorators import observe, langfuse_context

from shared.config import env_config


logger = logging.getLogger(__name__)


class ObservabilityService:
    def __init__(self):
        self.langfuse_client = None
        self._initialize_langfuse()
    
    def _initialize_langfuse(self):
        if all([env_config.LANGFUSE_PUBLIC_KEY, env_config.LANGFUSE_SECRET_KEY]):
            try:
                self.langfuse_client = Langfuse(
                    public_key=env_config.LANGFUSE_PUBLIC_KEY,
                    secret_key=env_config.LANGFUSE_SECRET_KEY,
                    host=env_config.LANGFUSE_HOST
                )
                logger.info("Langfuse observability initialized")
            except Exception as e:
                logger.warning(f"Failed to initialize Langfuse: {e}")
        else:
            logger.info("Langfuse credentials not provided, observability disabled")
    
    @observe()
    def trace_chat_request(self, shop_id: str, user_message: str, metadata: Dict[str, Any] = None):
        if not self.langfuse_client:
            return None
        
        trace = self.langfuse_client.trace(
            name="chat_request",
            metadata={
                "shop_id": shop_id,
                "user_message_length": len(user_message),
                "timestamp": datetime.utcnow().isoformat(),
                **(metadata or {})
            }
        )
        return trace
    
    @observe()
    def trace_rag_query(self, shop_id: str, question: str, sources_count: int, metadata: Dict[str, Any] = None):
        if not self.langfuse_client:
            return None
        
        span = langfuse_context.get_current_trace().span(
            name="rag_query",
            input={"shop_id": shop_id, "question": question},
            metadata={
                "sources_count": sources_count,
                **(metadata or {})
            }
        )
        return span
    
    @observe()
    def trace_llm_call(
        self, 
        model: str, 
        messages: list, 
        response: str, 
        usage: Dict[str, int] = None,
        metadata: Dict[str, Any] = None
    ):
        if not self.langfuse_client:
            return None
        
        span = langfuse_context.get_current_trace().generation(
            name="llm_call",
            model=model,
            input=messages,
            output=response,
            usage=usage,
            metadata=metadata or {}
        )
        return span
    
    @observe()
    def trace_tool_execution(
        self, 
        tool_name: str, 
        input_args: Dict[str, Any], 
        output: Dict[str, Any],
        latency_ms: int,
        metadata: Dict[str, Any] = None
    ):
        if not self.langfuse_client:
            return None
        
        span = langfuse_context.get_current_trace().span(
            name="tool_execution",
            input={"tool": tool_name, "args": input_args},
            output=output,
            metadata={
                "tool_name": tool_name,
                "latency_ms": latency_ms,
                **(metadata or {})
            }
        )
        return span
    
    def log_error(self, error: Exception, context: Dict[str, Any] = None):
        if self.langfuse_client:
            try:
                langfuse_context.get_current_trace().update(
                    level="ERROR",
                    status_message=str(error),
                    metadata=context or {}
                )
            except Exception as e:
                logger.error(f"Failed to log error to Langfuse: {e}")
        
        logger.error(f"Error: {error}", extra=context)
    
    def log_feedback(self, trace_id: str, score: float, comment: str = None):
        if not self.langfuse_client:
            return
        
        try:
            self.langfuse_client.score(
                trace_id=trace_id,
                name="user_feedback",
                value=score,
                comment=comment
            )
        except Exception as e:
            logger.error(f"Failed to log feedback: {e}")
    
    def flush(self):
        if self.langfuse_client:
            self.langfuse_client.flush()


# Global observability instance
observability = ObservabilityService()


# Decorator for automatic tracing
def trace_function(name: str = None):
    def decorator(func):
        if observability.langfuse_client:
            return observe(name=name or func.__name__)(func)
        else:
            return func
    return decorator


# Context manager for manual tracing
class TraceContext:
    def __init__(self, name: str, metadata: Dict[str, Any] = None):
        self.name = name
        self.metadata = metadata or {}
        self.trace = None
    
    def __enter__(self):
        if observability.langfuse_client:
            self.trace = observability.langfuse_client.trace(
                name=self.name,
                metadata=self.metadata
            )
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.trace and exc_type:
            self.trace.update(
                level="ERROR",
                status_message=str(exc_val)
            )
        if observability.langfuse_client:
            observability.langfuse_client.flush()