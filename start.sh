#!/bin/bash

# ShopTalk Startup Script

echo "🛒 Starting ShopTalk - Shopping Conversational Assistant"

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  .env file not found. Copying from .env.example..."
    cp .env.example .env
    echo "📝 Please edit .env with your API keys before proceeding."
    echo "   Required: At least one LLM API key (ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.)"
    read -p "Press Enter to continue after editing .env..."
fi

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker and try again."
    exit 1
fi

# Pull latest images and start services
echo "🐳 Starting Docker services..."
docker-compose pull
docker-compose up -d

# Wait for services to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo "🔍 Checking service health..."

# Check Qdrant
if curl -s http://localhost:6333/collections > /dev/null; then
    echo "✅ Qdrant is ready"
else
    echo "❌ Qdrant is not ready"
fi

# Check Redis
if redis-cli -p 6379 ping > /dev/null 2>&1; then
    echo "✅ Redis is ready"
else
    echo "❌ Redis is not ready"
fi

# Check Gateway
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✅ Gateway is ready"
else
    echo "❌ Gateway is not ready"
fi

# Check Crawler
if curl -s http://localhost:8001/health > /dev/null; then
    echo "✅ Crawler is ready"
else
    echo "❌ Crawler is not ready"
fi

# Check Streamlit
if curl -s http://localhost:8501 > /dev/null; then
    echo "✅ Streamlit is ready"
else
    echo "❌ Streamlit is not ready"
fi

echo ""
echo "🎉 ShopTalk is starting up!"
echo ""
echo "🌐 Access the application:"
echo "   Streamlit UI: http://localhost:8501"
echo "   Gateway API:  http://localhost:8000"
echo "   API Docs:     http://localhost:8000/docs"
echo "   Crawler API:  http://localhost:8001"
echo ""
echo "📚 Quick Start:"
echo "1. Open http://localhost:8501 in your browser"
echo "2. Go to Admin tab to crawl a demo shop"
echo "3. Switch to Chat tab and start asking questions!"
echo ""
echo "🛑 To stop: docker-compose down"
echo "📜 View logs: docker-compose logs -f"