import httpx
import json
from typing import Dict, Any, List, Optional
import streamlit as st


class APIClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.timeout = 30.0
    
    async def chat(self, shop_id: str, message: str, conversation_history: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat",
                json={
                    "shop_id": shop_id,
                    "message": message,
                    "conversation_history": conversation_history or []
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_shop_info(self, shop_id: str) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{self.base_url}/shops/{shop_id}/info")
            response.raise_for_status()
            return response.json()
    
    async def start_crawl(self, shop_id: str, shop_url: str, include: List[str] = None, exclude: List[str] = None) -> Dict[str, Any]:
        crawler_url = self.base_url.replace("8000", "8001")  # Assuming crawler runs on 8001
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                f"{crawler_url}/crawl/start",
                json={
                    "shop_id": shop_id,
                    "shop_url": shop_url,
                    "include": include or [],
                    "exclude": exclude or []
                }
            )
            response.raise_for_status()
            return response.json()
    
    async def get_crawl_status(self, shop_id: str) -> Dict[str, Any]:
        crawler_url = self.base_url.replace("8000", "8001")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.get(f"{crawler_url}/crawl/status?shop_id={shop_id}")
            response.raise_for_status()
            return response.json()


def format_message_time(timestamp: str = None) -> str:
    from datetime import datetime
    if timestamp:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%H:%M")
    else:
        return datetime.now().strftime("%H:%M")


def truncate_text(text: str, max_length: int = 200) -> str:
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def format_tool_trace(trace: Dict[str, Any]) -> str:
    name = trace.get("name", "Unknown")
    latency = trace.get("latency_ms", 0)
    
    input_str = json.dumps(trace.get("input", {}), indent=2)
    output_str = json.dumps(trace.get("output", {}), indent=2)
    
    return f"""**{name}** ({latency}ms)
    
**Input:**
```json
{input_str}
```

**Output:**
```json
{output_str}
```
"""


def extract_urls_from_text(text: str) -> List[str]:
    import re
    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
    return re.findall(url_pattern, text)


class StreamlitCallback:
    def __init__(self):
        self.placeholder = None
        self.current_text = ""
    
    def on_llm_start(self, *args, **kwargs):
        if not self.placeholder:
            self.placeholder = st.empty()
        self.placeholder.markdown("🤔 Thinking...")
    
    def on_llm_new_token(self, token: str, *args, **kwargs):
        self.current_text += token
        if self.placeholder:
            self.placeholder.markdown(self.current_text + "▌")
    
    def on_llm_end(self, *args, **kwargs):
        if self.placeholder:
            self.placeholder.markdown(self.current_text)


def display_error(error_message: str, error_type: str = "error"):
    if error_type == "error":
        st.error(f"❌ {error_message}")
    elif error_type == "warning":
        st.warning(f"⚠️ {error_message}")
    elif error_type == "info":
        st.info(f"ℹ️ {error_message}")


def create_message_dict(role: str, content: str, sources: List[Dict] = None, tool_traces: List[Dict] = None) -> Dict[str, Any]:
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.now().isoformat()
    }
    
    if sources:
        message["sources"] = sources
    
    if tool_traces:
        message["tool_traces"] = tool_traces
    
    return message