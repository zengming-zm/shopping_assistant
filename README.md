# ShopTalk - Shopping Conversational Assistant

ShopTalk is an advanced shopping assistant that understands any given shop URL and answers questions grounded in that shop's content (products, policies, reviews). It uses a crawl+index service to maintain a searchable knowledge base and provides agentic capabilities with external tools and APIs.

## 🎯 Key Features

- **Smart Shop Understanding**: Crawls and indexes any e-commerce website
- **Conversational AI**: Multi-turn conversations with memory and context
- **Agentic Tools**: Currency conversion, shipping estimates, product search, and more
- **Flexible LLM Support**: Works with Claude, Gemini, GPT, and other models via LiteLLM/OpenRouter
- **Modular Prompts**: Hot-swappable prompt templates organized by feature
- **Real-time Sources**: Always shows citations and source materials
- **Demo-Ready APIs**: Built-in demo APIs for quick demonstrations

## 🏗️ Architecture

```
/app (Streamlit UI) → /gateway (FastAPI) → Multiple Services:
                          ├── Agent Orchestrator (planner + tool executor)
                          ├── RAG Service (retriever + reranker + answer composer)
                          ├── Memory Service (short/long-term)
                          ├── LLM Router (OpenRouter/LiteLLM)
                          └── Tool Registry (currency, shipping, reviews, etc.)

/crawler (Side system):
   ├── URL discovery (sitemap/links), robots.txt compliance
   ├── Fetch (Playwright for JS sites)
   ├── Parse & clean (Trafilatura/Unstructured)
   ├── Chunk + embed (SentenceTransformers)
   └── Index (Qdrant) + metadata store (SQLite/Postgres)
```

## 🚀 Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository>
   cd ShoppingAssistant
   cp .env.example .env
   # Edit .env with your API keys
   ```

2. **Start with Docker**
   ```bash
   docker-compose up -d
   ```

3. **Access the Application**
   - Streamlit UI: http://localhost:8501
   - Gateway API: http://localhost:8000
   - Crawler API: http://localhost:8001

## 📋 Prerequisites

### Required API Keys (add to .env)
- **LLM Access**: At least one of:
  - `ANTHROPIC_API_KEY` (Claude)
  - `GOOGLE_API_KEY` (Gemini)
  - `OPENAI_API_KEY` (GPT)
  - `OPENROUTER_API_KEY` (Multi-provider)

### Optional API Keys
- `COHERE_API_KEY` - For Cohere reranking
- `JINA_API_KEY` - For Jina reranking
- `EASYPOST_TEST_API_KEY` - For shipping estimates
- `LANGFUSE_PUBLIC_KEY` & `LANGFUSE_SECRET_KEY` - For observability

## 🛠️ Configuration

### LLM Models (config.yaml)
```yaml
llm_router:
  provider: "litellm"  # or "openrouter"
  models:
    planner: "gemini-2.0-flash-exp"
    rag_answer: "claude-3-5-sonnet-20241022"
    followups: "gemini-1.5-flash"
```

### RAG Settings
```yaml
rag:
  chunk_size: 1000
  chunk_overlap: 200
  top_k: 18
  rerank_top_n: 8

reranker: "local_bge"  # or "cohere" or "jina_cloud"
```

## 📖 Usage Guide

### 1. Index a Shop
```python
# Via API
POST http://localhost:8001/crawl/start
{
  "shop_id": "example_shop",
  "shop_url": "https://example-shop.com",
  "include": ["/products/", "/policies/"],
  "exclude": ["/admin/", "/api/"]
}
```

### 2. Chat with the Assistant
```python
# Via API
POST http://localhost:8000/chat
{
  "shop_id": "example_shop",
  "message": "What's your return policy?",
  "conversation_history": []
}
```

### 3. Use the Streamlit UI
1. Open http://localhost:8501
2. Use the Admin panel to start crawling a shop
3. Switch to Chat tab and start asking questions
4. View sources and tool traces for transparency

## 🔧 Available Tools

### Built-in Tools
- **convert_currency**: Live currency conversion via exchangerate.host
- **search_products**: Search shop products or demo product APIs
- **get_product_detail**: Detailed product information
- **get_reviews**: Customer reviews and ratings
- **geolocate_ip**: IP-based geolocation for shipping estimates
- **estimate_shipping**: Shipping cost and time estimates

### Demo APIs (DEMO_MODE=true)
- **Products**: DummyJSON, Fake Store API
- **Currency**: ExchangeRate.host
- **Geolocation**: ipapi.co, ip-api.com
- **Shipping**: Mock estimates

## 📝 Prompt Customization

Prompts are organized in `/prompts/` with YAML + Jinja2:

```yaml
# prompts/rag/qa.yaml
template: |
  You are a shopping assistant for {{ shop_name }}.
  
  Customer Question: {{ question }}
  
  Shop Information:
  {% for source in sources %}
  - {{ source.title }}: {{ source.snippet }}
  {% endfor %}
  
  Provide a helpful answer with citations.
```

### Hot Reloading
Prompts can be modified without restarting the service. Use the Streamlit Settings tab to reload prompt cache.

## 🧪 Testing

```bash
# Run unit tests
pytest tests/

# Run integration tests
pytest tests/integration/

# Run specific test
pytest tests/test_rag.py::TestRAGService::test_query
```

## 📊 Observability

### Langfuse Integration
When configured, ShopTalk automatically logs:
- Full conversation traces
- LLM calls with token usage
- Tool executions with latency
- RAG retrieval performance
- Error tracking

### Metrics Available
- Response latency (P95 target: <3.5s)
- Token usage and costs
- Tool usage patterns
- Source quality scores

## 🔒 Security & Compliance

- **Robots.txt Compliance**: Respects crawl directives
- **Rate Limiting**: Configurable crawl delays
- **Domain Scope**: Crawling limited to specified domains
- **No Personal Data**: Never stores user personal information
- **API Key Security**: Keys only in backend environment

## 🚢 Deployment

### Production Deployment
1. Use PostgreSQL instead of SQLite
2. Set up Redis cluster for caching
3. Configure Qdrant cloud or self-hosted cluster
4. Set up proper secrets management
5. Enable SSL/TLS
6. Configure observability and monitoring

### Environment Variables
```bash
# Required
ANTHROPIC_API_KEY=your_key
QDRANT_URL=https://your-qdrant-cluster.com

# Optional
COHERE_API_KEY=your_key
LANGFUSE_PUBLIC_KEY=your_key
REDIS_URL=redis://your-redis-cluster.com
```

## 📚 API Documentation

### Gateway Endpoints
- `POST /chat` - Main chat interface
- `POST /rag/query` - Direct RAG queries
- `GET /shops/{shop_id}/info` - Shop information
- `GET /health` - Health check

### Crawler Endpoints
- `POST /crawl/start` - Start crawling a shop
- `GET /crawl/status` - Check crawl progress
- `POST /crawl/reindex` - Reindex specific URLs

Full API documentation available at http://localhost:8000/docs

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

MIT License - see LICENSE file for details

## 🆘 Support

- 📧 Issues: Use GitHub Issues for bug reports
- 📖 Documentation: See `/docs/` for detailed guides
- 💬 Discussions: Use GitHub Discussions for questions

---

**Ready to build amazing shopping experiences with AI? Start with `docker-compose up` and explore the demo!** 🛒✨