# 💬 Multi-turn Conversation System

## Problem Solved
The original system couldn't handle follow-up questions that depend on previous context. Questions like "What colors do they come in?" or "Do you have it in size M?" would fail because the system didn't know what "they" or "it" referred to.

## 🧠 Solution: Conversational RAG with Query Rewriting

### **Key Components:**

#### **1. 🧠 Conversation Memory**
- Stores previous turns for each website domain
- Maintains context across multiple questions
- Automatically manages conversation history (10 turns max)

#### **2. 🔄 Query Rewriting System**  
- Analyzes conversation context to understand user intent
- Rewrites vague questions into clear, standalone queries
- Replaces pronouns with specific product references

#### **3. 🎯 Enhanced Retrieval**
- Uses rewritten queries for more accurate search
- Retrieves relevant product information based on context
- Maintains conversation flow while improving search precision

## 🌟 Multi-turn Conversation Examples

### **Example 1: Product Discovery → Colors → Pricing → Sizing**

**Turn 1:**
- **👤 User:** "Do you have any cashmere sweaters?"
- **🔍 Query:** "Do you have any cashmere sweaters?" (no rewriting needed)
- **🤖 Assistant:** "Yes, we have cashmere polo sweaters in beige, red, blue, and grey for $300..."

**Turn 2:**  
- **👤 User:** "What colors do they come in?"
- **🔄 Rewritten:** "What colors are available for Luca Faloni cashmere sweaters?"
- **💭 Reasoning:** Replaced "they" with "cashmere sweaters" from context
- **🤖 Assistant:** "The cashmere sweaters come in beige, red, blue, and grey..."

**Turn 3:**
- **👤 User:** "How much does the gray one cost?"
- **🔄 Rewritten:** "What is the price of the gray cashmere polo sweater?"
- **💭 Reasoning:** Replaced "the gray one" with specific product from context
- **🤖 Assistant:** "The gray cashmere polo sweater is $300..."

**Turn 4:**
- **👤 User:** "Do you have it in size M?"
- **🔄 Rewritten:** "What sizes of gray cashmere polo sweaters are available?"
- **💭 Reasoning:** Replaced "it" with the specific product being discussed
- **🤖 Assistant:** "For the gray cashmere polo sweater you asked about, sizes available are..."

### **Example 2: Comparison Shopping**

**Turn 1:**
- **👤 User:** "Show me your wool jackets"
- **🤖 Assistant:** "Here are our wool jacket options: [product details]..."

**Turn 2:**
- **👤 User:** "Which one is warmest?"  
- **🔄 Rewritten:** "Which wool jacket is the warmest?"
- **🤖 Assistant:** "Based on the materials, the merino wool jacket would be warmest..."

**Turn 3:**
- **👤 User:** "What's the price difference?"
- **🔄 Rewritten:** "What are the price differences between the wool jackets?"
- **🤖 Assistant:** "The price comparison for the wool jackets is..."

## 🎛️ Enhanced User Interface

### **💬 Conversation Analysis Panel**
For each response, users can see:
- **🔄 Original vs Rewritten Query**
- **💭 Rewriting Reasoning**  
- **📊 Sources Found with Relevance Scores**
- **🧠 Conversation Context Used**

### **💭 Conversation Management**
- **Turn Counter:** Shows number of conversation turns
- **🧹 Clear History:** Reset conversation context
- **📈 Context Awareness:** Visual indication when context is being used

## 🔧 Technical Implementation

### **Query Rewriting Pipeline:**
```python
# 1. Get conversation context (last 3 turns)
context = memory.get_recent_context(domain, num_turns=3)

# 2. AI-powered query rewriting
rewritten_query, reasoning = query_rewriter.rewrite_query(
    current_query, context, domain
)

# 3. Enhanced retrieval with rewritten query
search_results = search_website(domain, rewritten_query)

# 4. Context-aware response generation
response = generate_conversational_response(
    original_query, rewritten_query, search_results, context
)
```

### **Conversation Memory Structure:**
```json
{
  "domain": [
    {
      "timestamp": "2025-01-27T05:30:00Z",
      "user": "Do you have cashmere sweaters?",
      "assistant": "Yes, we have cashmere polo sweaters...",
      "sources": [...]
    },
    {
      "timestamp": "2025-01-27T05:31:00Z", 
      "user": "What colors do they come in?",
      "assistant": "The cashmere sweaters come in...",
      "sources": [...]
    }
  ]
}
```

## 🚀 Live Demo Features

### **How to Test Multi-turn Conversations:**

1. **Go to:** `http://localhost:8502`
2. **Index a website** (e.g., Luca Faloni)
3. **Start a conversation** with questions like:
   - "Show me your shirts"
   - "What colors do they come in?" ← Follow-up
   - "How much is the blue one?" ← Specific follow-up
   - "Do you have it in large?" ← Size inquiry

4. **Observe the features:**
   - 🔄 Query rewriting in action
   - 🧠 Conversation analysis panel
   - 💭 Context awareness indicators
   - 📊 Source relevance scoring

### **Advanced Conversation Scenarios:**
- **Product Comparisons:** "Which is better?" "What's the difference?"  
- **Attribute Inquiries:** "What materials?" "Available sizes?"
- **Follow-up Questions:** "Tell me more about that" "What about the other one?"
- **Cross-references:** "Do you have something similar?" "What else do you recommend?"

## ✅ Results

**Before (No Multi-turn Support):**
```
❌ User: "What colors do they come in?"
❌ Assistant: "I'm not sure what 'they' refers to..."
```

**After (Conversational RAG):**
```
✅ User: "What colors do they come in?"
✅ Rewritten: "What colors are available for cashmere sweaters?"
✅ Assistant: "The cashmere sweaters come in beige, red, blue, and grey..."
✅ Context: Successfully used previous conversation about cashmere sweaters
```

**🎉 Perfect multi-turn conversation support with intelligent query rewriting!**