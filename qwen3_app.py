"""
Qwen3 Thinking Mode Shopping Assistant
Displays model thinking process and uses Google Search for real-time product information
"""

import streamlit as st
import os
from urllib.parse import urlparse
from qwen3_search_rag import Qwen3SearchRAG

st.set_page_config(
    page_title="Qwen3 Thinking Shopping Assistant",
    page_icon="🧠",
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
    if "show_thinking" not in st.session_state:
        st.session_state.show_thinking = True

def main():
    st.title("🧠 Qwen3 Thinking Shopping Assistant")
    st.subheader("AI Reasoning + Google Search for E-commerce")
    
    # Check for API keys
    has_qwen3_api = bool(os.getenv('QWEN3_API_BASE')) and bool(os.getenv('QWEN3_API_KEY'))
    has_search_api = bool(os.getenv('GOOGLE_SEARCH_API_KEY'))
    has_cse_id = bool(os.getenv('GOOGLE_CSE_ID'))
    
    # API Configuration status
    with st.sidebar.expander("🔑 API Configuration", expanded=not all([has_qwen3_api, has_search_api, has_cse_id])):
        st.write("**Required API Configuration:**")
        st.write(f"{'✅' if has_qwen3_api else '❌'} Qwen3 API (QWEN3_API_BASE, QWEN3_API_KEY)")
        st.write(f"{'✅' if has_search_api else '❌'} GOOGLE_SEARCH_API_KEY")
        st.write(f"{'✅' if has_cse_id else '❌'} GOOGLE_CSE_ID")
        
        if not has_qwen3_api:
            st.warning("Configure Qwen3 API in .env file")
            st.info("""
            **Setup Options:**
            - **Ollama**: `ollama serve qwen3:32b` → `QWEN3_API_BASE=http://localhost:11434/v1`
            - **vLLM**: `vllm serve Qwen/Qwen3-32B --port 8000` → `QWEN3_API_BASE=http://localhost:8000/v1`
            - **Remote API**: Use hosted Qwen3 service
            """)
        
        if not all([has_search_api, has_cse_id]):
            st.info("Get Google Search API: https://developers.google.com/custom-search/v1/introduction")
    
    initialize_session_state()
    qwen_rag = Qwen3SearchRAG()
    
    # Sidebar settings
    st.sidebar.title("🌐 Domain Setup")
    
    # Thinking mode toggle
    st.session_state.show_thinking = st.sidebar.checkbox(
        "🧠 Show Thinking Process", 
        value=st.session_state.show_thinking,
        help="Display Qwen3's internal reasoning process"
    )
    
    # URL input
    website_url = st.sidebar.text_input(
        "Enter website domain:",
        placeholder="https://lucafaloni.com",
        help="Enter any e-commerce website domain"
    )
    
    if website_url:
        domain = get_domain_from_url(website_url)
        
        # Simple setup for Qwen3 + Google Search
        if domain not in st.session_state.used_domains:
            st.sidebar.info(f"🧠 Ready to analyze {domain} with Qwen3!")
            
            if st.sidebar.button("🚀 Start Thinking & Searching", type="primary"):
                st.session_state.used_domains.append(domain)
                st.session_state.current_website = domain
                st.success(f"✅ Now analyzing {domain} with Qwen3 thinking mode!")
                st.rerun()
        else:
            st.sidebar.success(f"✅ Ready to analyze {domain}!")
            if st.sidebar.button(f"💬 Switch to {domain}"):
                st.session_state.current_website = domain
                st.rerun()
    
    # Recent domains
    if st.session_state.used_domains:
        st.sidebar.subheader("💬 Recent Domains")
        for site in st.session_state.used_domains:
            if st.sidebar.button(f"🧠 {site}", key=f"chat_{site}"):
                st.session_state.current_website = site
                st.rerun()
    
    # Conversation management
    if st.session_state.current_website:
        st.sidebar.subheader("💭 Conversation")
        
        # Show conversation summary
        conv_summary = qwen_rag.get_conversation_summary(st.session_state.current_website)
        if conv_summary['total_turns'] > 0:
            st.sidebar.info(f"🔄 {conv_summary['total_turns']} turns")
            if conv_summary.get('has_thinking'):
                st.sidebar.info("🧠 Thinking processes recorded")
            
            if st.sidebar.button("🧹 Clear History"):
                qwen_rag.clear_conversation(st.session_state.current_website)
                if st.session_state.current_website in st.session_state.messages:
                    st.session_state.messages[st.session_state.current_website] = []
                st.success("Conversation history cleared!")
                st.rerun()
        else:
            st.sidebar.info("💬 Start a new conversation")
    
    # Main chat interface
    if st.session_state.current_website:
        st.header(f"🧠 Qwen3 Analysis: {st.session_state.current_website}")
        st.caption("Powered by Qwen3 Thinking Mode + Google Search API")
        
        # Initialize messages for current website
        if st.session_state.current_website not in st.session_state.messages:
            st.session_state.messages[st.session_state.current_website] = []
        
        current_messages = st.session_state.messages[st.session_state.current_website]
        
        # Display chat messages
        for message in current_messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
                # Show thinking process if available and enabled
                if (message["role"] == "assistant" and 
                    st.session_state.show_thinking and 
                    message.get("thinking")):
                    with st.expander("🧠 Qwen3 Thinking Process", expanded=False):
                        st.text_area(
                            "Model's reasoning:",
                            message["thinking"],
                            height=200,
                            disabled=True,
                            key=f"thinking_{len(current_messages)}_{message.get('timestamp', '')}"
                        )
        
        # Chat input
        if prompt := st.chat_input(f"Ask Qwen3 about {st.session_state.current_website} products..."):
            # Add user message
            current_messages.append({
                "role": "user", 
                "content": prompt,
                "timestamp": datetime.now().isoformat()
            })
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate and display assistant response
            with st.chat_message("assistant"):
                with st.spinner("🧠 Qwen3 is thinking and searching..."):
                    # Use Qwen3 with thinking mode
                    conv_result = qwen_rag.generate_conversational_response(
                        st.session_state.current_website, 
                        prompt,
                        enable_thinking=st.session_state.show_thinking
                    )
                    
                    response = conv_result['response']
                    thinking = conv_result['thinking_process']
                    
                    # Display response
                    st.markdown(response)
                    
                    # Show thinking process immediately if enabled
                    if st.session_state.show_thinking and thinking:
                        with st.expander("🧠 Qwen3 Thinking Process", expanded=True):
                            st.text_area(
                                "Model's reasoning:",
                                thinking,
                                height=200,
                                disabled=True,
                                key=f"live_thinking_{len(current_messages)}"
                            )
                    
                    # Show analysis in expander
                    with st.expander("🔍 Search & Context Analysis", expanded=False):
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            st.write("**Query Processing:**")
                            if conv_result['rewritten_keyphrases'] != [prompt]:
                                st.write(f"🔄 **Original:** {prompt}")
                                st.write(f"🔍 **Key Phrases:** {', '.join(conv_result['rewritten_keyphrases'])}")
                                st.write(f"💭 **Reasoning:** {conv_result['rewrite_reasoning']}")
                                
                                if conv_result.get('query_thinking'):
                                    st.write("**Query Rewrite Thinking:**")
                                    st.text_area(
                                        "Qwen3's query analysis:",
                                        conv_result['query_thinking'],
                                        height=100,
                                        disabled=True,
                                        key=f"query_thinking_{len(current_messages)}"
                                    )
                            else:
                                st.write("✅ Used original query")
                        
                        with col2:
                            st.write("**Google Search Results:**")
                            if conv_result['sources']:
                                for i, source in enumerate(conv_result['sources'], 1):
                                    search_phrase = source.get('search_phrase', 'unknown')
                                    st.write(f"{i}. [{source['title']}]({source['url']})")
                                    st.caption(f"Found via: '{search_phrase}'")
                                    st.caption(f"Snippet: {source['snippet'][:100]}...")
                            else:
                                st.write("No Google Search results found")
                        
                        if conv_result['conversation_context_used']:
                            st.write("**Conversation Context:**")
                            st.text_area(
                                "Previous context used:",
                                conv_result['conversation_context_used'],
                                height=100,
                                disabled=True,
                                key=f"context_{len(current_messages)}"
                            )
            
            # Store message with thinking process
            current_messages.append({
                "role": "assistant", 
                "content": response,
                "thinking": thinking if st.session_state.show_thinking else "",
                "timestamp": datetime.now().isoformat()
            })
    
    else:
        st.info("👆 Enter a website domain to start chatting with Qwen3!")
        
        # Instructions
        st.markdown("""
        ## 🧠 How Qwen3 Thinking Mode Works:
        
        ### 🔄 **Three-Stage Process:**
        1. **🧠 Think**: Qwen3 analyzes conversation context and user intent
        2. **🔍 Search**: Generates multiple Google search phrases for comprehensive results  
        3. **💬 Respond**: Uses thinking + search evidence for accurate answers
        
        ### ✨ **Key Features:**
        - 🧠 **Visible Thinking**: See how Qwen3 reasons through problems
        - 🔍 **Smart Search**: Multiple key phrases for comprehensive Google results
        - 💭 **Context Awareness**: Remembers conversation history
        - 📱 **Any Domain**: Works with any e-commerce website
        
        ### 🎯 **Example Thinking Process:**
        ```
        User: "What colors do they come in?"
        
        🧠 Qwen3 Thinking:
        "Looking at the conversation context, the user previously asked about 
        cashmere sweaters. The pronoun 'they' refers to cashmere sweaters. 
        I need to search for specific color information about cashmere sweaters
        from this domain..."
        
        🔍 Search Phrases Generated:
        - "cashmere sweater colors lucafaloni.com"
        - "lucafaloni.com cashmere available colors"
        
        💬 Final Response:
        "The cashmere sweaters we discussed come in beige, red, blue, and grey..."
        ```
        
        ### 🛠️ **Setup Requirements:**
        
        **Option 1 - Local Ollama:**
        ```bash
        ollama pull qwen3:32b
        ollama serve
        ```
        
        **Option 2 - vLLM:**
        ```bash
        vllm serve Qwen/Qwen3-32B --port 8000
        ```
        
        **Then set in .env:**
        ```
        QWEN3_API_BASE=http://localhost:8000/v1  # or :11434 for Ollama
        QWEN3_API_KEY=dummy  # or your API key
        QWEN3_MODEL=Qwen/Qwen3-32B
        ```
        """)
        
        if st.session_state.used_domains:
            st.subheader("Continue with recent domains:")
            cols = st.columns(min(3, len(st.session_state.used_domains)))
            for i, site in enumerate(st.session_state.used_domains):
                with cols[i % 3]:
                    if st.button(f"🧠 {site}", key=f"main_chat_{site}"):
                        st.session_state.current_website = site
                        st.rerun()

if __name__ == "__main__":
    main()