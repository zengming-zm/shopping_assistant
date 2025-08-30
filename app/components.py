import streamlit as st
import asyncio
import json
from typing import Dict, Any, List
from datetime import datetime

from .utils import APIClient, format_message_time, truncate_text, format_tool_trace, display_error, create_message_dict


class ChatInterface:
    def __init__(self):
        self.api_client = st.session_state.api_client
    
    def render_chat(self):
        st.header("💬 Chat with ShopTalk")
        
        # Display conversation
        chat_container = st.container()
        
        with chat_container:
            for message in st.session_state.messages:
                self._render_message(message)
        
        # Input area
        self._render_input_area()
    
    def _render_message(self, message: Dict[str, Any]):
        role = message["role"]
        content = message["content"]
        timestamp = message.get("timestamp", "")
        sources = message.get("sources", [])
        tool_traces = message.get("tool_traces", [])
        
        time_str = format_message_time(timestamp)
        
        if role == "user":
            with st.chat_message("user"):
                st.write(f"**You** *({time_str})*")
                st.write(content)
        else:
            with st.chat_message("assistant"):
                st.write(f"**ShopTalk** *({time_str})*")
                st.write(content)
                
                # Show sources if available
                if sources:
                    with st.expander(f"📚 Sources ({len(sources)})", expanded=False):
                        for i, source in enumerate(sources):
                            st.write(f"**{i+1}. {source.get('title', 'Unknown')}**")
                            st.write(f"🔗 [{source.get('url', '#')}]({source.get('url', '#')})")
                            if 'snippet' in source:
                                st.write(f"*{truncate_text(source['snippet'], 150)}*")
                            st.write("---")
                
                # Show tool traces if available
                if tool_traces:
                    with st.expander(f"🔧 Tool Usage ({len(tool_traces)})", expanded=False):
                        for trace in tool_traces:
                            st.markdown(format_tool_trace(trace))
    
    def _render_input_area(self):
        with st.form("chat_form", clear_on_submit=True):
            col1, col2 = st.columns([4, 1])
            
            with col1:
                user_input = st.text_input(
                    "Ask about products, policies, shipping, or anything else...",
                    placeholder="What can I help you find today?",
                    label_visibility="collapsed"
                )
            
            with col2:
                submit = st.form_submit_button("Send", use_container_width=True)
            
            if submit and user_input:
                self._handle_user_input(user_input)
    
    def _handle_user_input(self, user_input: str):
        user_message = create_message_dict("user", user_input)
        st.session_state.messages.append(user_message)
        
        with st.spinner("ShopTalk is thinking..."):
            try:
                conversation_history = [
                    {"role": msg["role"], "content": msg["content"]}
                    for msg in st.session_state.messages[-5:]  # Last 5 messages for context
                ]
                
                response = asyncio.run(
                    self.api_client.chat(
                        shop_id=st.session_state.shop_id,
                        message=user_input,
                        conversation_history=conversation_history
                    )
                )
                
                assistant_message = create_message_dict(
                    "assistant",
                    response["answer"],
                    sources=response.get("sources", []),
                    tool_traces=response.get("tool_traces", [])
                )
                
                st.session_state.messages.append(assistant_message)
                st.session_state.last_sources = response.get("sources", [])
                st.session_state.tool_traces = response.get("tool_traces", [])
                
                # Display followup suggestions
                followups = response.get("followups", [])
                if followups:
                    self._render_followup_buttons(followups)
                
                st.rerun()
                
            except Exception as e:
                display_error(f"Failed to get response: {e}")
    
    def _render_followup_buttons(self, followups: List[str]):
        st.write("💡 **You might also want to ask:**")
        
        cols = st.columns(min(len(followups), 3))
        
        for i, followup in enumerate(followups[:3]):
            with cols[i]:
                if st.button(truncate_text(followup, 50), key=f"followup_{i}"):
                    self._handle_user_input(followup)
    
    def render_sidebar(self):
        st.subheader(f"🏪 Shop: {st.session_state.shop_id}")
        
        # Shop info
        if st.button("Refresh Shop Info"):
            self._refresh_shop_info()
        
        # Quick actions
        st.subheader("⚡ Quick Actions")
        
        quick_questions = [
            "What's your return policy?",
            "Do you ship internationally?",
            "What are your customer service hours?",
            "Show me your bestsellers",
            "What payment methods do you accept?"
        ]
        
        for question in quick_questions:
            if st.button(truncate_text(question, 30), key=f"quick_{hash(question)}"):
                self._handle_user_input(question)
        
        # Conversation stats
        st.subheader("📊 Conversation Stats")
        st.metric("Messages", len(st.session_state.messages))
        st.metric("Sources", len(st.session_state.last_sources))
        st.metric("Tool Calls", len(st.session_state.tool_traces))
    
    def _refresh_shop_info(self):
        try:
            shop_info = asyncio.run(
                self.api_client.get_shop_info(st.session_state.shop_id)
            )
            
            st.success(f"✅ Shop Status: {shop_info.get('status', 'Unknown')}")
            st.info(f"Documents: {shop_info.get('document_count', 0)}")
            
        except Exception as e:
            display_error(f"Failed to get shop info: {e}")


class AdminPanel:
    def __init__(self):
        self.api_client = st.session_state.api_client
    
    def render(self):
        st.header("⚙️ Admin Panel")
        
        tabs = st.tabs(["🕷️ Crawler", "📊 Analytics", "🔧 Management"])
        
        with tabs[0]:
            self._render_crawler_tab()
        
        with tabs[1]:
            self._render_analytics_tab()
        
        with tabs[2]:
            self._render_management_tab()
    
    def _render_crawler_tab(self):
        st.subheader("Web Crawler")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Start New Crawl**")
            
            shop_id = st.text_input("Shop ID", value=st.session_state.shop_id)
            shop_url = st.text_input("Shop URL", placeholder="https://example-shop.com")
            
            col1_1, col1_2 = st.columns(2)
            with col1_1:
                include_patterns = st.text_area(
                    "Include Patterns (one per line)",
                    placeholder="/products/\n/category/",
                    height=100
                ).strip().split('\n') if st.text_area(
                    "Include Patterns (one per line)",
                    placeholder="/products/\n/category/",
                    height=100
                ).strip() else []
            
            with col1_2:
                exclude_patterns = st.text_area(
                    "Exclude Patterns (one per line)",
                    placeholder="/admin/\n/api/",
                    height=100
                ).strip().split('\n') if st.text_area(
                    "Exclude Patterns (one per line)",
                    placeholder="/admin/\n/api/",
                    height=100
                ).strip() else []
            
            if st.button("Start Crawl", type="primary"):
                if shop_url:
                    self._start_crawl(shop_id, shop_url, include_patterns, exclude_patterns)
                else:
                    st.error("Please provide a shop URL")
        
        with col2:
            st.write("**Crawl Status**")
            
            if st.button("Refresh Status"):
                self._refresh_crawl_status(st.session_state.shop_id)
            
            # Status will be displayed here
    
    def _render_analytics_tab(self):
        st.subheader("Usage Analytics")
        
        # Mock analytics data
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Total Queries Today", "47", "12")
        
        with col2:
            st.metric("Avg Response Time", "2.3s", "-0.1s")
        
        with col3:
            st.metric("Tool Usage", "23", "5")
        
        # Simple chart
        import pandas as pd
        import numpy as np
        
        dates = pd.date_range(start='2024-01-01', periods=30, freq='D')
        queries = np.random.randint(10, 100, 30)
        
        chart_data = pd.DataFrame({
            'Date': dates,
            'Queries': queries
        })
        
        st.line_chart(chart_data.set_index('Date'))
    
    def _render_management_tab(self):
        st.subheader("System Management")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.write("**Database Management**")
            
            if st.button("Clear All Conversations"):
                st.session_state.messages = []
                st.success("Conversations cleared")
            
            if st.button("Reset Shop Index"):
                st.warning("This would clear the shop's search index (not implemented in demo)")
        
        with col2:
            st.write("**Configuration**")
            
            st.json({
                "current_shop": st.session_state.shop_id,
                "gateway_url": self.api_client.base_url,
                "demo_mode": True
            })
    
    def _start_crawl(self, shop_id: str, shop_url: str, include: List[str], exclude: List[str]):
        try:
            with st.spinner("Starting crawl..."):
                response = asyncio.run(
                    self.api_client.start_crawl(shop_id, shop_url, include, exclude)
                )
            
            st.success(f"✅ Crawl started for {shop_id}")
            st.json(response)
            
        except Exception as e:
            display_error(f"Failed to start crawl: {e}")
    
    def _refresh_crawl_status(self, shop_id: str):
        try:
            status = asyncio.run(
                self.api_client.get_crawl_status(shop_id)
            )
            
            st.json(status)
            
        except Exception as e:
            display_error(f"Failed to get crawl status: {e}")


class SourceViewer:
    @staticmethod
    def render(sources: List[Dict[str, Any]]):
        if not sources:
            st.info("No sources available")
            return
        
        st.subheader(f"📚 Sources ({len(sources)})")
        
        for i, source in enumerate(sources):
            with st.expander(f"{i+1}. {source.get('title', 'Unknown Source')}", expanded=i == 0):
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    st.write(f"**URL:** {source.get('url', 'N/A')}")
                    st.write(f"**Snippet:**")
                    st.write(source.get('snippet', 'No snippet available'))
                
                with col2:
                    score = source.get('score', 0)
                    st.metric("Relevance", f"{score:.3f}")
                
                if st.button(f"Visit Source {i+1}", key=f"visit_{i}"):
                    st.write(f"🔗 [Open in new tab]({source.get('url', '#')})")