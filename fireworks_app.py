"""
Fireworks AI Qwen3 Thinking Mode Shopping Assistant
Uses Fireworks AI's hosted Qwen3 models with thinking capabilities and Google Search
"""

import streamlit as st
import os
from datetime import datetime
from urllib.parse import urlparse
from fireworks_qwen3_rag import FireworksQwen3SearchRAG

st.set_page_config(
    page_title="Fireworks AI Qwen3 Shopping Assistant",
    page_icon="🔥",
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
    st.title("🔥 Fireworks AI Qwen3 Shopping Assistant")
    st.subheader("Advanced AI Reasoning + Google Search for E-commerce")
    
    # Check for API keys
    has_fireworks_api = bool(os.getenv('FIREWORKS_API_KEY'))
    has_search_api = bool(os.getenv('GOOGLE_SEARCH_API_KEY'))
    has_cse_id = bool(os.getenv('GOOGLE_CSE_ID'))
    
    # API Configuration status
    with st.sidebar.expander("🔑 API Configuration", expanded=not all([has_fireworks_api, has_search_api, has_cse_id])):
        st.write("**Required API Keys:**")
        st.write(f"{'✅' if has_fireworks_api else '❌'} FIREWORKS_API_KEY")
        st.write(f"{'✅' if has_search_api else '❌'} GOOGLE_SEARCH_API_KEY")
        st.write(f"{'✅' if has_cse_id else '❌'} GOOGLE_CSE_ID")
        
        if not has_fireworks_api:
            st.warning("Get Fireworks AI API key at: https://fireworks.ai")
            st.info("""
            **Available Qwen3 Models:**
            - `accounts/fireworks/models/qwen3-235b-a22b` (Default)
            - `accounts/fireworks/models/qwen3-coder-480b-a35b-instruct`
            - `accounts/fireworks/models/qwen3-32b`
            """)
        
        if not all([has_search_api, has_cse_id]):
            st.info("Setup Google Search: https://developers.google.com/custom-search/v1/introduction")
    
    initialize_session_state()
    qwen_rag = FireworksQwen3SearchRAG()
    
    # Sidebar settings
    st.sidebar.title("🌐 Domain Setup")
    
    # Model selection
    model_options = {
        "Qwen3-235B (Flagship)": "accounts/fireworks/models/qwen3-235b-a22b",
        "Qwen3-Coder-480B": "accounts/fireworks/models/qwen3-coder-480b-a35b-instruct",
        "Qwen3-32B": "accounts/fireworks/models/qwen3-32b"
    }
    
    selected_model_name = st.sidebar.selectbox(
        "🧠 Select Qwen3 Model:",
        list(model_options.keys()),
        help="Choose Qwen3 model variant"
    )
    qwen_rag.model_name = model_options[selected_model_name]
    qwen_rag.query_rewriter.model_name = model_options[selected_model_name]
    
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
        
        # Simple setup for Fireworks AI Qwen3 + Google Search
        if domain not in st.session_state.used_domains:
            st.sidebar.info(f"🔥 Ready to analyze {domain} with Qwen3!")
            
            if st.sidebar.button("🚀 Start Thinking & Searching", type="primary"):
                st.session_state.used_domains.append(domain)
                st.session_state.current_website = domain
                st.success(f"✅ Now analyzing {domain} with Fireworks AI Qwen3!")
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
            if st.sidebar.button(f"🔥 {site}", key=f"chat_{site}"):
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
        col1, col2 = st.columns([3, 1])
        with col1:
            st.header(f"🔥 Qwen3 Analysis: {st.session_state.current_website}")
        with col2:
            st.caption(f"Model: {selected_model_name}")
        
        st.caption("Powered by Fireworks AI Qwen3 + Google Search")
        
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
                            key=f"thinking_{message.get('timestamp', '')}"
                        )
        
        # Chat input
        if prompt := st.chat_input(f"Ask Qwen3 about {st.session_state.current_website} products..."):
            # Add user message
            timestamp = datetime.now().isoformat()
            current_messages.append({
                "role": "user", 
                "content": prompt,
                "timestamp": timestamp
            })
            with st.chat_message("user"):
                st.markdown(prompt)
            
            # Generate and display assistant response
            with st.chat_message("assistant"):
                with st.spinner("🔥 Qwen3 is thinking and searching..."):
                    # Use Fireworks AI Qwen3 with thinking mode
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
                    
                    # Show detailed analysis in expander
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
                                    st.caption(f"Via: '{search_phrase}'")
                                    st.caption(f"Snippet: {source['snippet'][:80]}...")
                            else:
                                st.write("No Google Search results found")
                        
                        if conv_result['conversation_context_used']:
                            st.write("**Conversation Context:**")
                            st.text_area(
                                "Previous context used:",
                                conv_result['conversation_context_used'],
                                height=80,
                                disabled=True,
                                key=f"context_{len(current_messages)}"
                            )
            
            # Store message with thinking process
            current_messages.append({
                "role": "assistant", 
                "content": response,
                "thinking": thinking if st.session_state.show_thinking else "",
                "timestamp": timestamp
            })
    
    else:
        st.info("👆 Enter a website domain to start chatting with Fireworks AI Qwen3!")
        
        # Instructions
        st.markdown("""
        ## 🔥 Fireworks AI Qwen3 Thinking Mode:
        
        ### 🚀 **Powered by Fireworks AI:**
        - **Fast Inference**: Serverless Qwen3 models with sub-second response times
        - **Advanced Reasoning**: 235B parameter model with thinking capabilities
        - **Tool Integration**: Optimized for multi-step reasoning and search
        
        ### 🧠 **Three-Stage Thinking Process:**
        1. **🔥 Think**: Qwen3 analyzes conversation context and user intent
        2. **🔍 Search**: Generates multiple Google search phrases for comprehensive results  
        3. **💬 Respond**: Combines thinking + search evidence for accurate answers
        
        ### ✨ **Key Features:**
        - 🧠 **Visible Thinking**: See Qwen3's step-by-step reasoning in `<think>` tags
        - 🔍 **Multi-Phrase Search**: 2-4 optimized Google searches per query
        - 💭 **Context Awareness**: Maintains conversation history with thinking records
        - 📱 **Any Domain**: Works with any e-commerce website
        
        ### 🎯 **Example Thinking Process:**
        ```
        User: "What colors do they come in?"
        
        🧠 Qwen3 Thinking:
        <think>
        Looking at the conversation context, I can see the user previously 
        asked about cashmere sweaters from lucafaloni.com. The pronoun "they" 
        clearly refers to the cashmere sweaters we were discussing.
        
        I should search for specific color information about cashmere sweaters 
        from this domain. I'll generate search phrases that include:
        1. The specific product (cashmere sweaters)
        2. The domain (lucafaloni.com) 
        3. The intent (available colors)
        </think>
        
        🔍 Search Phrases Generated:
        - "cashmere sweater colors lucafaloni.com"
        - "lucafaloni.com cashmere available colors"
        
        💬 Final Response:
        "The cashmere sweaters we discussed come in beige, red, blue, and grey..."
        ```
        
        ### 🛠️ **Setup Requirements:**
        
        **Get Fireworks AI API Key:**
        1. Visit https://fireworks.ai
        2. Sign up and get your API key
        3. Add to `.env`: `FIREWORKS_API_KEY=your_api_key_here`
        
        **Configure Google Search:**
        ```env
        GOOGLE_SEARCH_API_KEY=your_google_api_key
        GOOGLE_CSE_ID=your_custom_search_engine_id
        ```
        
        ### 🎮 **Available Models:**
        - **Qwen3-235B**: Flagship model with 235B parameters, best reasoning
        - **Qwen3-Coder-480B**: Optimized for coding and technical tasks
        - **Qwen3-32B**: Balanced performance and efficiency
        """)
        
        if st.session_state.used_domains:
            st.subheader("Continue with recent domains:")
            cols = st.columns(min(3, len(st.session_state.used_domains)))
            for i, site in enumerate(st.session_state.used_domains):
                with cols[i % 3]:
                    if st.button(f"🔥 {site}", key=f"main_chat_{site}"):
                        st.session_state.current_website = site
                        st.rerun()

if __name__ == "__main__":
    main()