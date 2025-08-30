#!/usr/bin/env python3

import subprocess
import sys
import time
import os
import signal
from pathlib import Path

def run_command(cmd, cwd=None, background=False):
    if background:
        return subprocess.Popen(cmd, shell=True, cwd=cwd)
    else:
        return subprocess.run(cmd, shell=True, cwd=cwd)

def main():
    print("🛒 Starting ShopTalk locally...")
    
    # Check if .env exists
    if not Path('.env').exists():
        print("⚠️  .env file not found. Copying from .env.example...")
        subprocess.run('cp .env.example .env', shell=True)
        print("📝 Please edit .env with your API keys.")
        print("   At minimum, add one LLM API key (ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.)")
        input("Press Enter after editing .env to continue...")
    
    # Start Qdrant in Docker (lightweight)
    print("🐳 Starting Qdrant...")
    qdrant_proc = run_command(
        "docker run -d --name qdrant_local -p 6333:6333 -p 6334:6334 qdrant/qdrant:v1.7.4",
        background=True
    )
    
    # Start Redis in Docker (lightweight)  
    print("🐳 Starting Redis...")
    redis_proc = run_command(
        "docker run -d --name redis_local -p 6379:6379 redis:7-alpine",
        background=True
    )
    
    # Wait for databases to start
    print("⏳ Waiting for databases...")
    time.sleep(5)
    
    processes = []
    
    try:
        # Install dependencies
        print("📦 Installing Python dependencies...")
        run_command("pip install -r requirements.txt")
        
        # Start Gateway
        print("🚀 Starting Gateway API...")
        gateway_proc = run_command(
            "uvicorn gateway.main:app --host localhost --port 8000 --reload",
            background=True
        )
        processes.append(gateway_proc)
        
        # Start Crawler
        print("🕷️  Starting Crawler API...")
        crawler_proc = run_command(
            "uvicorn crawler.main:app --host localhost --port 8001 --reload",
            background=True
        )
        processes.append(crawler_proc)
        
        # Wait for APIs to start
        time.sleep(3)
        
        # Start Streamlit
        print("🎨 Starting Streamlit UI...")
        os.environ['GATEWAY_URL'] = 'http://localhost:8000'
        streamlit_proc = run_command(
            "streamlit run app/main.py --server.port 8501",
            background=True
        )
        processes.append(streamlit_proc)
        
        print("\n🎉 ShopTalk is starting up!")
        print("\n🌐 Access the application:")
        print("   Streamlit UI: http://localhost:8501")
        print("   Gateway API:  http://localhost:8000")
        print("   API Docs:     http://localhost:8000/docs")
        print("   Crawler API:  http://localhost:8001")
        print("\n📚 Quick Start:")
        print("1. Open http://localhost:8501 in your browser")
        print("2. Go to Admin tab to crawl a demo shop")
        print("3. Switch to Chat tab and start asking questions!")
        print("\n🛑 Press Ctrl+C to stop all services")
        
        # Keep running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping services...")
            
    finally:
        # Clean up
        for proc in processes:
            proc.terminate()
        
        # Stop Docker containers
        run_command("docker stop qdrant_local redis_local", background=False)
        run_command("docker rm qdrant_local redis_local", background=False)
        
        print("✅ All services stopped")

if __name__ == "__main__":
    main()