"""
Universal ShopTalk - Google Search-based Shopping Assistant
Uses Google Search API instead of local crawling for real-time product information
"""

import streamlit as st
import os
from urllib.parse import urlparse
from google_search_rag import GoogleSearchRAG

st.set_page_config(
    page_title="Universal ShopTalk - Google Search",
    page_icon="🔍",
    layout="wide"
)

def get_domain_from_url(url: str) -> str:
    """Extract domain from URL"""
    parsed = urlparse(url)
    domain = parsed.netloc.lower()
    if domain.startswith('www.'):
        domain = domain[4:]
    return domain

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "current_website" not in st.session_state:
        st.session_state.current_website = ""
    if "used_domains" not in st.session_state:
        st.session_state.used_domains = []

def main():
    st.title("🔍 Universal ShopTalk")
    st.subheader("Google Search-Powered Shopping Assistant")
    
    # Check for API keys
    has_google_api = bool(os.getenv('GOOGLE_API_KEY'))
    has_search_api = bool(os.getenv('GOOGLE_SEARCH_API_KEY'))
    has_cse_id = bool(os.getenv('GOOGLE_CSE_ID'))
    
    # API Configuration status
    with st.sidebar.expander("🔑 API Configuration", expanded=not all([has_google_api, has_search_api, has_cse_id])):
        st.write("**Required API Keys:**")
        st.write(f"{'✅' if has_google_api else '❌'} GOOGLE_API_KEY (Gemini)")
        st.write(f"{'✅' if has_search_api else '❌'} GOOGLE_SEARCH_API_KEY")
        st.write(f"{'✅' if has_cse_id else '❌'} GOOGLE_CSE_ID")
        
        if not all([has_google_api, has_search_api, has_cse_id]):
            st.warning("Configure missing API keys in your .env file")
            st.info("Get Google Search API: https://developers.google.com/custom-search/v1/introduction")
    
    initialize_session_state()
    search_rag = GoogleSearchRAG()
    
    # Sidebar
    st.sidebar.title("🌐 Domain Setup")
    
    # URL input
    website_url = st.sidebar.text_input(
        "Enter website domain:",
        placeholder="https://lucafaloni.com",
        help="Enter any website domain to start chatting about their products"
    )
    
    if website_url:
        domain = get_domain_from_url(website_url)
        
        # Simple setup for Google Search
        if domain not in st.session_state.used_domains:
            st.sidebar.info(f"🔍 Ready to search {domain} with Google!")
            
            if st.sidebar.button("🚀 Start Chatting", type="primary"):
                # Add domain to used list
                st.session_state.used_domains.append(domain)
                st.session_state.current_website = domain
                st.success(f"✅ Now chatting with {domain} using Google Search!")
                st.rerun()
        else:
            st.sidebar.success(f"✅ Ready to chat with {domain}!")
            if st.sidebar.button(f"💬 Switch to {domain}"):
                st.session_state.current_website = domain
                st.rerun()
    
    # Recent domains list
    if st.session_state.used_domains:
        st.sidebar.subheader("💬 Recent Domains")
        for site in st.session_state.used_domains:
            if st.sidebar.button(f"💬 {site}", key=f"chat_{site}"):
                st.session_state.current_website = site
                st.rerun()
    
    # Conversation management
    if st.session_state.current_website:
        st.sidebar.subheader("💭 Conversation")
        
        # Show conversation summary
        conv_summary = search_rag.get_conversation_summary(st.session_state.current_website)
        if conv_summary['total_turns'] > 0:
            st.sidebar.info(f"🔄 {conv_summary['total_turns']} turns in conversation")
            
            if st.sidebar.button("🧹 Clear Conversation History"):
                search_rag.clear_conversation(st.session_state.current_website)
                # Also clear Streamlit session messages
                if st.session_state.current_website in st.session_state.messages:
                    st.session_state.messages[st.session_state.current_website] = []
                st.success("Conversation history cleared!")
                st.rerun()
        else:
            st.sidebar.info("💬 Start a new conversation")
    
    # Main chat interface
    if st.session_state.current_website:
        st.header(f"🔍 Chatting with: {st.session_state.current_website}")
        st.caption("Powered by Google Search API for real-time product information")
        
        # Initialize messages for current website
        if st.session_state.current_website not in st.session_state.messages:
            st.session_state.messages[st.session_state.current_website] = []
        
        current_messages = st.session_state.messages[st.session_state.current_website]
        
        # Display chat messages
        for message in current_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
        
        # Chat input
        if prompt := st.chat_input(f"Ask about {st.session_state.current_website} products..."):
            # Add user message
            current_messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate and display assistant response
            with st.chat_message("assistant"):
                with st.spinner("🔍 Searching Google and analyzing context..."):
                    # Use Google Search RAG for multi-turn support
                    conv_result = search_rag.generate_conversational_response(
                        st.session_state.current_website, 
                        prompt
                    )
                    
                    response = conv_result['response']
                    st.markdown(response)
                    
                    # Show conversation insights in an expander
                    with st.expander("🧠 Google Search Analysis", expanded=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Query Processing:**")
                            if conv_result['rewritten_keyphrases'] != [prompt]:
                                st.write(f"🔄 **Original:** {prompt}")
                                st.write(f"🔍 **Key Phrases:** {', '.join(conv_result['rewritten_keyphrases'])}")
                                st.write(f"💭 **Reasoning:** {conv_result['rewrite_reasoning']}")
                            else:
                                st.write("✅ Used original query (no rewriting needed)")
                        
                        with col2:
                            st.write("**Google Search Results:**")
                            if conv_result['sources']:
                                for i, source in enumerate(conv_result['sources'], 1):
                                    search_phrase = source.get('search_phrase', 'unknown')
                                    st.write(f"{i}. [{source['title']}]({source['url']})")
                                    st.caption(f"Found via: '{search_phrase}'")
                            else:
                                st.write("No Google Search results found")
                        
                        if conv_result['conversation_context_used']:
                            st.write("**Conversation Context:**")
                            st.text_area("Previous context used:", conv_result['conversation_context_used'], height=100, disabled=True)
            
            current_messages.append({"role": "assistant", "content": response})
    
    else:
        st.info("👆 Enter a website domain in the sidebar to start chatting!")
        
        # Instructions
        st.markdown("""
        ## 🔍 How it works:
        
        1. **Enter any website domain** (e.g., lucafaloni.com, amazon.com)
        2. **Start chatting** about products from that website
        3. **Google Search powers** real-time product information retrieval
        4. **Multi-turn conversations** with context awareness
        
        ### ✨ Key Features:
        - 🔍 **Google Search Integration**: Real-time product information
        - 💬 **Multi-turn Conversations**: Remembers what you discussed
        - 🧠 **Smart Query Rewriting**: Converts "How much is it?" to specific product searches
        - 📱 **Any Website**: Works with any e-commerce domain
        
        ### 📝 Example Conversations:
        ```
        You: "Show me cashmere sweaters from lucafaloni.com"
        Assistant: [Searches Google for "cashmere sweaters lucafaloni.com"]
        
        You: "What colors do they come in?"
        Assistant: [Searches for "cashmere sweater colors lucafaloni.com" 
                   based on previous conversation]
        
        You: "How much is the gray one?"
        Assistant: [Searches for "gray cashmere sweater price lucafaloni.com"]
        ```
        """)
        
        if st.session_state.used_domains:
            st.subheader("Or continue with recent domains:")
            cols = st.columns(min(3, len(st.session_state.used_domains)))
            for i, site in enumerate(st.session_state.used_domains):
                with cols[i % 3]:
                    if st.button(f"🔍 {site}", key=f"main_chat_{site}"):
                        st.session_state.current_website = site
                        st.rerun()

if __name__ == "__main__":
    main()