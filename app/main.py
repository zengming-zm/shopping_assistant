import streamlit as st
import httpx
import json
import os
from datetime import datetime
from typing import Dict, Any, List

from .components import ChatInterface, AdminPanel, SourceViewer
from .utils import APIClient


st.set_page_config(
    page_title="ShopTalk - Shopping Assistant",
    page_icon="🛒",
    layout="wide"
)


def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "shop_id" not in st.session_state:
        st.session_state.shop_id = "demo"
    if "last_sources" not in st.session_state:
        st.session_state.last_sources = []
    if "tool_traces" not in st.session_state:
        st.session_state.tool_traces = []
    if "api_client" not in st.session_state:
        gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
        st.session_state.api_client = APIClient(gateway_url)


def main():
    initialize_session_state()
    
    st.title("🛒 ShopTalk - Shopping Assistant")
    
    tabs = st.tabs(["💬 Chat", "⚙️ Admin", "📊 Settings"])
    
    with tabs[0]:
        render_chat_tab()
    
    with tabs[1]:
        render_admin_tab()
    
    with tabs[2]:
        render_settings_tab()


def render_chat_tab():
    chat_interface = ChatInterface()
    
    col1, col2 = st.columns([3, 1])
    
    with col1:
        chat_interface.render_chat()
    
    with col2:
        chat_interface.render_sidebar()


def render_admin_tab():
    admin_panel = AdminPanel()
    admin_panel.render()


def render_settings_tab():
    st.header("Settings")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Shop Configuration")
        
        current_shop = st.text_input(
            "Current Shop ID",
            value=st.session_state.shop_id,
            help="Identifier for the current shop"
        )
        
        if current_shop != st.session_state.shop_id:
            st.session_state.shop_id = current_shop
            st.session_state.messages = []  # Clear conversation when switching shops
            st.success(f"Switched to shop: {current_shop}")
        
        st.subheader("API Configuration")
        gateway_url = os.getenv("GATEWAY_URL", "http://localhost:8000")
        st.info(f"Gateway URL: {gateway_url}")
        
        if st.button("Test Connection"):
            try:
                response = httpx.get(f"{gateway_url}/health", timeout=5.0)
                if response.status_code == 200:
                    st.success("✅ Connected to gateway successfully")
                else:
                    st.error(f"❌ Gateway returned status: {response.status_code}")
            except Exception as e:
                st.error(f"❌ Connection failed: {e}")
    
    with col2:
        st.subheader("Conversation Management")
        
        if st.button("Clear Conversation"):
            st.session_state.messages = []
            st.session_state.last_sources = []
            st.session_state.tool_traces = []
            st.success("Conversation cleared")
        
        if st.button("Export Conversation"):
            if st.session_state.messages:
                export_data = {
                    "shop_id": st.session_state.shop_id,
                    "timestamp": datetime.now().isoformat(),
                    "messages": st.session_state.messages,
                    "sources": st.session_state.last_sources,
                    "tool_traces": [trace.__dict__ if hasattr(trace, '__dict__') else trace for trace in st.session_state.tool_traces]
                }
                
                st.download_button(
                    label="Download JSON",
                    data=json.dumps(export_data, indent=2),
                    file_name=f"shoptalk_conversation_{st.session_state.shop_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json"
                )
            else:
                st.info("No conversation to export")
        
        st.subheader("Debug Information")
        if st.checkbox("Show Debug Info"):
            st.json({
                "messages_count": len(st.session_state.messages),
                "current_shop": st.session_state.shop_id,
                "sources_count": len(st.session_state.last_sources),
                "tool_traces_count": len(st.session_state.tool_traces)
            })


if __name__ == "__main__":
    main()