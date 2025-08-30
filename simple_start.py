"""
Simple local startup for ShopTalk - runs without Docker for development
"""

import os
import sys
import subprocess
import time
from pathlib import Path

def check_env():
    """Check if .env exists and has required keys"""
    env_path = Path('.env')
    if not env_path.exists():
        print("⚠️  Creating .env from template...")
        subprocess.run('cp .env.example .env', shell=True)
        print("📝 Edit .env with at least one LLM API key:")
        print("   ANTHROPIC_API_KEY, GOOGLE_API_KEY, OPENAI_API_KEY, or OPENROUTER_API_KEY")
        return False
    
    with open('.env') as f:
        env_content = f.read()
        
    required_keys = ['ANTHROPIC_API_KEY', 'GOOGLE_API_KEY', 'OPENAI_API_KEY', 'OPENROUTER_API_KEY']
    has_llm_key = False
    
    for key in required_keys:
        if f'{key}=' in env_content:
            value = env_content.split(f'{key}=')[1].split('\n')[0].strip().strip('"').strip("'")
            if value and 'your_' not in value and len(value) > 10:
                print(f"✅ Found {key}")
                has_llm_key = True
                break
    
    if not has_llm_key:
        print("❌ No LLM API key found in .env")
        print("   Please add at least one: ANTHROPIC_API_KEY, GOOGLE_API_KEY, etc.")
        return False
    
    return True

def install_deps():
    """Install Python dependencies"""
    print("📦 Installing dependencies...")
    result = subprocess.run([sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'], 
                          capture_output=True, text=True)
    if result.returncode != 0:
        print("❌ Failed to install dependencies:")
        print(result.stderr)
        return False
    return True

def start_qdrant():
    """Start Qdrant in Docker"""
    print("🐳 Starting Qdrant...")
    subprocess.run('docker stop qdrant_local 2>/dev/null || true', shell=True)
    subprocess.run('docker rm qdrant_local 2>/dev/null || true', shell=True)
    
    result = subprocess.run([
        'docker', 'run', '-d', 
        '--name', 'qdrant_local',
        '-p', '6333:6333',
        'qdrant/qdrant:v1.7.4'
    ])
    return result.returncode == 0

def start_redis():
    """Start Redis in Docker"""  
    print("🐳 Starting Redis...")
    subprocess.run('docker stop redis_local 2>/dev/null || true', shell=True)
    subprocess.run('docker rm redis_local 2>/dev/null || true', shell=True)
    
    result = subprocess.run([
        'docker', 'run', '-d',
        '--name', 'redis_local', 
        '-p', '6379:6379',
        'redis:7-alpine'
    ])
    return result.returncode == 0

def wait_for_services():
    """Wait for Docker services to be ready"""
    print("⏳ Waiting for services...")
    time.sleep(5)
    
    # Check Qdrant
    try:
        import requests
        requests.get('http://localhost:6333/collections', timeout=5)
        print("✅ Qdrant ready")
    except:
        print("❌ Qdrant not ready")
        return False
    
    return True

def main():
    os.chdir(Path(__file__).parent)
    
    print("🛒 Starting ShopTalk locally (development mode)")
    
    if not check_env():
        return
    
    # Start databases
    if not start_qdrant() or not start_redis():
        print("❌ Failed to start databases")
        return
    
    if not wait_for_services():
        print("❌ Services not ready")
        return
    
    if not install_deps():
        return
    
    print("\n🚀 Starting Python services...")
    
    # Set environment
    os.environ['QDRANT_URL'] = 'http://localhost:6333'
    os.environ['REDIS_URL'] = 'redis://localhost:6379'
    
    # Add current directory to Python path
    os.environ['PYTHONPATH'] = str(Path.cwd())
    
    print("📖 To start the services manually:")
    print("   Terminal 1: uvicorn gateway.main:app --host localhost --port 8000 --reload")
    print("   Terminal 2: uvicorn crawler.main:app --host localhost --port 8001 --reload") 
    print("   Terminal 3: streamlit run app/main.py --server.port 8501")
    print("\n🌐 Then visit: http://localhost:8501")
    print("\n🛑 Run 'docker stop qdrant_local redis_local' to stop databases when done")

if __name__ == "__main__":
    main()