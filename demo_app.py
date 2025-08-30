"""
Simple demo of ShopTalk without complex dependencies
"""

import streamlit as st
import requests
import json
import os
from datetime import datetime
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()

st.set_page_config(
    page_title="ShopTalk Demo", 
    page_icon="🛒",
    layout="wide"
)

def initialize_session_state():
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "shop_id" not in st.session_state:
        st.session_state.shop_id = "demo_shop"

def setup_gemini():
    api_key = os.getenv('GOOGLE_API_KEY')
    if api_key:
        genai.configure(api_key=api_key)
        return genai.GenerativeModel('gemini-1.5-flash')
    return None

def get_demo_product_data(query=""):
    """Get demo product data from DummyJSON"""
    try:
        if query:
            response = requests.get(f"https://dummyjson.com/products/search?q={query}&limit=5")
        else:
            response = requests.get("https://dummyjson.com/products?limit=10")
        
        if response.status_code == 200:
            return response.json().get('products', [])
    except:
        pass
    
    return []

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
    """Generate response using Gemini"""
    if not model:
        return "Please configure GOOGLE_API_KEY in your .env file to use the AI assistant."
    
    try:
        # Simple product search context
        products = get_demo_product_data(user_message)
        product_context = ""
        
        if products and any(word in user_message.lower() for word in ['product', 'buy', 'price', 'cost', 'search']):
            product_context = f"\nAvailable products:\n"
            for p in products[:3]:
                product_context += f"- {p['title']}: ${p['price']} - {p['description'][:100]}...\n"
        
        # Currency conversion context
        currency_context = ""
        if '$' in user_message or 'convert' in user_message.lower():
            # Try to extract conversion request
            words = user_message.split()
            for i, word in enumerate(words):
                if word.startswith('$') and i + 2 < len(words) and words[i+1].lower() == 'to':
                    amount = float(word[1:])
                    to_currency = words[i+2].upper()
                    converted = convert_currency(amount, 'USD', to_currency)
                    if converted:
                        currency_context = f"\nCurrency conversion: ${amount} USD = {converted:.2f} {to_currency}"
        
        prompt = f"""You are ShopTalk, a helpful shopping assistant for an online store.

Customer question: {user_message}

{product_context}
{currency_context}
{context}

Respond helpfully as a shopping assistant. If you mention products or prices, use the context provided. 
Keep responses concise but informative. Always be friendly and customer-focused.
"""
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        return f"I encountered an error: {e}. Please try rephrasing your question."

def main():
    initialize_session_state()
    
    st.title("🛒 ShopTalk - Shopping Assistant Demo")
    st.caption("Powered by AI • Demo Mode")
    
    # Setup AI model
    model = setup_gemini()
    if not model:
        st.error("❌ Please configure GOOGLE_API_KEY in your .env file")
        return
    
    # Sidebar
    with st.sidebar:
        st.header(f"🏪 Shop: {st.session_state.shop_id}")
        
        st.subheader("⚡ Quick Questions")
        quick_questions = [
            "Show me some products",
            "What's your return policy?",
            "Do you ship internationally?",
            "Convert $100 to EUR",
            "What are your bestsellers?"
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
    
    # Main chat area
    st.subheader("💬 Chat")
    
    # Display messages
    for message in st.session_state.messages:
        role = message["role"]
        content = message["content"]
        time_str = datetime.fromisoformat(message["timestamp"]).strftime("%H:%M")
        
        if role == "user":
            st.chat_message("user").write(f"**You** *({time_str})*\n\n{content}")
        else:
            st.chat_message("assistant").write(f"**ShopTalk** *({time_str})*\n\n{content}")
    
    # Input area
    user_input = st.chat_input("Ask about products, policies, shipping, or anything else...")
    
    if user_input:
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": user_input,
            "timestamp": datetime.now().isoformat()
        })
        
        # Generate response
        with st.spinner("ShopTalk is thinking..."):
            response = generate_response(user_input, model)
            
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response,
                "timestamp": datetime.now().isoformat()
            })
        
        st.rerun()
    
    # Footer
    st.markdown("---")
    st.caption("🎯 **Demo Features Active:** Product search via DummyJSON • Currency conversion via ExchangeRate.host • AI responses via Gemini")

if __name__ == "__main__":
    main()