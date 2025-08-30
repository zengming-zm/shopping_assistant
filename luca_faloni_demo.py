"""
Enhanced ShopTalk Demo with Luca Faloni Vector Database
"""

import streamlit as st
import requests
import json
import os
import re
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="ShopTalk - Luca Faloni", 
    page_icon="🛒",
    layout="wide"
)

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "shop_id" not in st.session_state:
        st.session_state.shop_id = "luca_faloni"

def setup_gemini():
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-1.5-flash')
    return None

def load_luca_faloni_data():
    """Load the Luca Faloni vector database"""
    documents = {}
    search_index = {}
    
    if os.path.exists('luca_faloni_documents.json'):
        with open('luca_faloni_documents.json', 'r') as f:
            docs_list = json.load(f)
            documents = {doc['id']: doc for doc in docs_list}
    
    if os.path.exists('luca_faloni_search_index.json'):
        with open('luca_faloni_search_index.json', 'r') as f:
            search_index = json.load(f)
    
    return documents, search_index

def search_luca_faloni(query: str, limit: int = 3):
    """Search the Luca Faloni vector database"""
    documents, search_index = load_luca_faloni_data()
    
    if not search_index:
        return []
    
    query_words = set(re.findall(r'\b[a-z]{3,}\b', query.lower()))
    
    # Score documents
    results = []
    for doc_id, doc_data in search_index.items():
        keywords = set(doc_data['keywords'])
        
        # Calculate simple overlap score
        overlap = len(query_words.intersection(keywords))
        if overlap > 0:
            score = overlap / len(query_words.union(keywords))
            results.append({
                'doc_id': doc_id,
                'title': doc_data['title'],
                'url': doc_data['url'],
                'section': doc_data['section'],
                'snippet': doc_data['text'],
                'score': score
            })
    
    # Sort by score and return top results
    results.sort(key=lambda x: x['score'], reverse=True)
    return results[:limit]

def convert_currency(amount, from_curr, to_curr):
    """Convert currency using exchangerate.host"""
    try:
        response = requests.get(
            f"https://api.exchangerate.host/convert?from={from_curr}&to={to_curr}&amount={amount}"
        )
        if response.status_code == 200:
            data = response.json()
            if data.get('success'):
                return data['result']
    except:
        pass
    return None

def generate_response(user_message, model, context=""):
    """Generate response using Gemini with Luca Faloni context"""
    if not model:
        return "Please configure GOOGLE_API_KEY in your .env file to use the AI assistant."
    
    try:
        # Search Luca Faloni database
        luca_results = search_luca_faloni(user_message)
        luca_context = ""
        
        if luca_results:
            luca_context = "\nLuca Faloni Information:\n"
            for result in luca_results:
                luca_context += f"- {result['title']}: {result['snippet'][:200]}...\n"
                luca_context += f"  Source: {result['url']}\n\n"
        
        # Currency conversion context
        currency_context = ""
        if '$' in user_message or 'convert' in user_message.lower():
            # Try to extract conversion request
            words = user_message.split()
            for i, word in enumerate(words):
                if word.startswith('$') and i + 2 < len(words) and words[i+1].lower() == 'to':
                    try:
                        amount = float(word[1:])
                        to_currency = words[i+2].upper()
                        converted = convert_currency(amount, 'USD', to_currency)
                        if converted:
                            currency_context = f"\nCurrency conversion: ${amount} USD = {converted:.2f} {to_currency}"
                    except:
                        pass

        prompt = f"""You are ShopTalk, a personal shopping assistant for Luca Faloni, a luxury Italian menswear brand.

Customer question: {user_message}

{luca_context}
{currency_context}
{context}

Instructions:
- You represent Luca Faloni, a premium Italian menswear brand known for exceptional craftsmanship
- Use the provided Luca Faloni information to answer questions about products, materials, and policies
- If asked about products, highlight the Italian craftsmanship, premium materials (cashmere, linen, cotton, silk)
- For policy questions, refer to the care guide and sizing information when available
- Always maintain a sophisticated, helpful tone appropriate for a luxury brand
- If you don't have specific information, acknowledge this and offer to help find more details
- Include source URLs when referencing specific information

Respond as a knowledgeable Luca Faloni shopping assistant.
"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"I encountered an error: {e}. Please try rephrasing your question."

def display_sources(sources):
    """Display search result sources"""
    if not sources:
        return
    
    with st.expander(f"📚 Sources ({len(sources)})", expanded=False):
        for i, source in enumerate(sources, 1):
            st.write(f"**{i}. {source['title']}**")
            st.write(f"🔗 [{source['url']}]({source['url']})")
            st.write(f"*Score: {source['score']:.3f} | Section: {source['section']}*")
            st.write(f"_{source['snippet'][:150]}..._")
            st.write("---")

def main():
    initialize_session_state()
    
    st.title("🛒 ShopTalk - Luca Faloni")
    st.caption("Personal Shopping Assistant • Powered by AI • Vector Search Enabled")
    
    # Setup AI model
    model = setup_gemini()
    if not model:
        st.error("❌ Please configure GOOGLE_API_KEY in your .env file")
        return
    
    # Load and display database status
    documents, search_index = load_luca_faloni_data()
    
    # Sidebar
    with st.sidebar:
        st.header("🏪 Luca Faloni")
        st.image("https://lucafaloni.com/cdn/shop/files/LF_LOGO_BLACK_400x.png?v=1613485869", width=200)
        
        st.subheader("📊 Database Status")
        st.metric("Documents Indexed", len(documents))
        st.metric("Search Terms", len(search_index))
        
        if documents:
            st.success("✅ Vector database ready")
        else:
            st.warning("⚠️ Run luca_faloni_crawler.py first")
        
        st.subheader("⚡ Quick Questions")
        quick_questions = [
            "Tell me about Luca Faloni",
            "What materials do you use?",
            "Show me your knitwear collection", 
            "How do I care for cashmere?",
            "What's your size guide?",
            "Italian craftsmanship details"
        ]
        
        for q in quick_questions:
            if st.button(q, key=f"quick_{hash(q)}"):
                st.session_state.messages.append({
                    "role": "user", 
                    "content": q,
                    "timestamp": datetime.now().isoformat()
                })
                st.rerun()
        
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()
        
        st.subheader("🔍 Search Test")
        test_query = st.text_input("Test search:", placeholder="cotton shirts")
        if st.button("Search") and test_query:
            results = search_luca_faloni(test_query)
            if results:
                st.write(f"Found {len(results)} results:")
                for result in results:
                    st.write(f"• {result['title']} ({result['score']:.3f})")
            else:
                st.write("No results found")
    
    # Main chat area
    st.subheader("💬 Personal Shopping Assistant")
    
    # Display messages
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        time_str = datetime.fromisoformat(message["timestamp"]).strftime("%H:%M")
        sources = message.get("sources", [])
        
        if role == "user":
            st.chat_message("user").write(f"**You** *({time_str})*\n\n{content}")
        else:
            with st.chat_message("assistant"):
                st.write(f"**ShopTalk** *({time_str})*\n\n{content}")
                if sources:
                    display_sources(sources)
    
    # Input area
    user_input = st.chat_input("Ask about Luca Faloni products, materials, care, or anything else...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })
        
        # Generate response
        with st.spinner("ShopTalk is thinking..."):
            # Get search results for context
            search_results = search_luca_faloni(user_input)
            
            response = generate_response(user_input, model)
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response,
                "timestamp": datetime.now().isoformat(),
                "sources": search_results
            })
        
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.caption("🎯 **Features:** Luca Faloni Vector Search • AI-Powered Responses • Italian Luxury Menswear Expertise")
    
    # Debug info
    if st.checkbox("Show Debug Info"):
        st.json({
            "documents_loaded": len(documents),
            "search_terms": len(search_index),
            "messages": len(st.session_state.messages)
        })

if __name__ == "__main__":
    main()