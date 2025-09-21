"""
Unified Streamlit Interface for Shopping Assistant
Supports multiple implementations: Direct API calls and LangGraph multi-agent
"""

import streamlit as st
import os
from dotenv import load_dotenv

from core.base import assistant_registry
from implementations.fireworks_implementation import FireworksDirectImplementation
from implementations.langgraph_implementation import LangGraphMultiAgentImplementation

load_dotenv()

# Register implementations
assistant_registry.register(
    "fireworks_direct", 
    FireworksDirectImplementation,
    "Direct API calls using Fireworks AI Qwen3 with thinking mode"
)

assistant_registry.register(
    "langgraph_agents",
    LangGraphMultiAgentImplementation, 
    "Multi-agent workflow using LangGraph for specialized search tasks"
)

def initialize_session_state():
    """Initialize Streamlit session state"""
    if 'messages' not in st.session_state:
        st.session_state.messages = {}
    if 'selected_implementation' not in st.session_state:
        st.session_state.selected_implementation = "fireworks_direct"
    if 'assistant_instance' not in st.session_state:
        st.session_state.assistant_instance = None
    if 'domain' not in st.session_state:
        st.session_state.domain = "lucafaloni.com"

def setup_sidebar():
    """Setup sidebar configuration"""
    
    st.sidebar.title("🛍️ Shopping Assistant")
    st.sidebar.markdown("---")
    
    # Implementation selection
    st.sidebar.subheader("Implementation")
    implementations = assistant_registry.list_implementations()
    
    selected = st.sidebar.selectbox(
        "Choose Implementation:",
        options=list(implementations.keys()),
        format_func=lambda x: f"{x.replace('_', ' ').title()}",
        key="implementation_selector"
    )
    
    # Show implementation description
    if selected in implementations:
        st.sidebar.info(implementations[selected])
    
    # Domain configuration
    st.sidebar.subheader("Domain")
    domain = st.sidebar.text_input("Website Domain:", value="lucafaloni.com")
    
    # Advanced settings
    with st.sidebar.expander("Advanced Settings"):
        enable_thinking = st.checkbox("Enable Thinking Mode", value=True)
        show_sources = st.checkbox("Show Sources", value=True)
        show_thinking = st.checkbox("Show Thinking Process", value=False)
        show_keyphrases = st.checkbox("Show Search Keyphrases", value=False)
    
    # API Status
    st.sidebar.subheader("API Status")
    fireworks_key = os.getenv('FIREWORKS_API_KEY')
    google_key = os.getenv('GOOGLE_SEARCH_API_KEY')
    google_cse = os.getenv('GOOGLE_CSE_ID')
    
    st.sidebar.write(f"🔥 Fireworks: {'✅' if fireworks_key else '❌'}")
    st.sidebar.write(f"🔍 Google Search: {'✅' if google_key and google_cse else '❌'}")
    
    # Clear conversation button
    if st.sidebar.button("🗑️ Clear Conversation"):
        if st.session_state.assistant_instance:
            st.session_state.assistant_instance.clear_conversation(domain)
        if domain in st.session_state.messages:
            del st.session_state.messages[domain]
        st.rerun()
    
    return {
        'implementation': selected,
        'domain': domain,
        'enable_thinking': enable_thinking,
        'show_sources': show_sources,
        'show_thinking': show_thinking,
        'show_keyphrases': show_keyphrases
    }

def get_assistant_instance(implementation_name: str):
    """Get or create assistant instance"""
    if (st.session_state.assistant_instance is None or 
        st.session_state.selected_implementation != implementation_name):
        
        st.session_state.assistant_instance = assistant_registry.create_instance(implementation_name)
        st.session_state.selected_implementation = implementation_name
    
    return st.session_state.assistant_instance

def display_conversation_history(domain: str):
    """Display conversation history"""
    if domain not in st.session_state.messages:
        st.session_state.messages[domain] = []
    
    for message in st.session_state.messages[domain]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

def display_response_details(result: dict, config: dict):
    """Display detailed response information"""
    
    # Show search keyphrases
    if config['show_keyphrases'] and result.get('rewritten_keyphrases'):
        with st.expander("🔍 Search Keyphrases"):
            for i, phrase in enumerate(result['rewritten_keyphrases'], 1):
                st.write(f"{i}. `{phrase}`")
            if result.get('rewrite_reasoning'):
                st.write(f"**Reasoning:** {result['rewrite_reasoning']}")
    
    # Show thinking process
    if config['show_thinking'] and result.get('thinking_process'):
        with st.expander("🧠 Thinking Process"):
            if isinstance(result['thinking_process'], str):
                st.text(result['thinking_process'])
            else:
                st.write(result['thinking_process'])
    
    # Show sources
    if config['show_sources'] and result.get('sources'):
        with st.expander(f"📚 Sources ({len(result['sources'])})"):
            for i, source in enumerate(result['sources'], 1):
                st.write(f"**{i}. {source.get('title', 'No title')}**")
                st.write(f"*{source.get('snippet', 'No description')}*")
                if source.get('url'):
                    st.write(f"🔗 [Source]({source['url']})")
                if source.get('search_phrase'):
                    st.caption(f"Found via: '{source['search_phrase']}'")
                st.write("---")
    
    # Show metadata
    if result.get('metadata'):
        with st.expander("ℹ️ Response Metadata"):
            metadata = result['metadata']
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**Implementation:** {metadata.get('implementation', 'unknown')}")
                if 'model' in metadata:
                    st.write(f"**Model:** {metadata['model']}")
                if 'thinking_enabled' in metadata:
                    st.write(f"**Thinking Mode:** {'✅' if metadata['thinking_enabled'] else '❌'}")
            
            with col2:
                if 'agents_executed' in metadata:
                    st.write(f"**Agents Used:** {', '.join(metadata['agents_executed'])}")
                if 'google_results_count' in metadata:
                    st.write(f"**Google Results:** {metadata['google_results_count']}")
                if 'deal_results_count' in metadata:
                    st.write(f"**Deal Results:** {metadata['deal_results_count']}")

def main():
    """Main Streamlit application"""
    
    st.set_page_config(
        page_title="Shopping Assistant",
        page_icon="🛍️",
        layout="wide"
    )
    
    initialize_session_state()
    config = setup_sidebar()
    
    # Main content area
    st.title("🛍️ Shopping Assistant")
    st.markdown(f"**Domain:** {config['domain']} | **Implementation:** {config['implementation'].replace('_', ' ').title()}")
    
    # Get assistant instance
    assistant = get_assistant_instance(config['implementation'])
    
    if not assistant:
        st.error(f"Failed to initialize {config['implementation']} implementation")
        return
    
    # Display conversation history
    display_conversation_history(config['domain'])
    
    # Chat input
    if prompt := st.chat_input("Ask about products, features, or deals..."):
        
        # Add user message to chat
        st.session_state.messages[config['domain']].append({"role": "user", "content": prompt})
        
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking and searching..."):
                try:
                    result = assistant.generate_conversational_response(
                        domain=config['domain'],
                        user_message=prompt,
                        save_to_memory=True,
                        enable_thinking=config['enable_thinking']
                    )
                    
                    # Display main response
                    response_text = result.get('response', 'No response generated')
                    st.markdown(response_text)
                    
                    # Add to session state
                    st.session_state.messages[config['domain']].append({
                        "role": "assistant", 
                        "content": response_text
                    })
                    
                    # Display additional details
                    display_response_details(result, config)
                    
                except Exception as e:
                    error_msg = f"Error: {str(e)}"
                    st.error(error_msg)
                    st.session_state.messages[config['domain']].append({
                        "role": "assistant",
                        "content": error_msg
                    })
    
    # Show conversation summary in sidebar
    with st.sidebar.expander("📊 Conversation Summary"):
        if assistant:
            summary = assistant.get_conversation_summary(config['domain'])
            st.json(summary)

if __name__ == "__main__":
    main()