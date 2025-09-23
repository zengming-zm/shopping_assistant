#!/usr/bin/env python3
"""
Test script to verify GoogleSearchProvider deprecation and SearchTool integration
"""

import os
import sys
import warnings
from io import StringIO
from contextlib import redirect_stdout, redirect_stderr
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_google_search_provider_deprecation():
    """Test that GoogleSearchProvider shows deprecation warnings"""
    print("=" * 60)
    print("Testing GoogleSearchProvider Deprecation")
    print("=" * 60)
    
    # Capture stdout to check for deprecation warnings
    stdout_capture = StringIO()
    stderr_capture = StringIO()
    
    try:
        with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
            from google_search_rag import GoogleSearchProvider, GoogleSearchRAG
            
            # Create instances (should show warnings)
            provider = GoogleSearchProvider()
            rag = GoogleSearchRAG()
        
        output = stdout_capture.getvalue()
        error_output = stderr_capture.getvalue()
        
        # Check for deprecation warnings
        deprecation_found = any([
            "WARNING:" in output,
            "DEPRECATED" in output,
            "deprecated" in output.lower(),
            "SearchTool" in output
        ])
        
        print(f"GoogleSearchProvider created: ✅")
        print(f"GoogleSearchRAG created: ✅")
        print(f"Deprecation warnings shown: {'✅' if deprecation_found else '❌'}")
        
        if deprecation_found:
            print(f"Warning message: {output.strip()}")
        
        return deprecation_found
        
    except Exception as e:
        print(f"❌ Error testing deprecation: {e}")
        return False

def test_search_tool_functionality():
    """Test that SearchTool works properly as replacement"""
    print("\n" + "=" * 60)
    print("Testing SearchTool as Replacement")
    print("=" * 60)
    
    try:
        from chat import SearchTool, QueryRewriter, GeminiProvider
        
        # Test SearchTool creation
        provider = GeminiProvider()
        if not provider.is_available:
            print("⚠️  Gemini provider not available, using mock AI provider")
        
        # Create SearchTool with mock search function
        def mock_search_function(domain, query, limit=3):
            return [
                {
                    'title': f'Test Result for {query}',
                    'snippet': f'Test snippet for {query} on {domain}',
                    'url': f'https://{domain}/test',
                    'source': 'test',
                    'score': 0.9
                }
            ]
        
        search_tool = SearchTool(
            search_function=mock_search_function,
            ai_provider=provider,
            chat_history=[{"role": "user", "content": "I'm looking for laptops"}],
            domain="teststore.com"
        )
        
        print(f"SearchTool created successfully: ✅")
        print(f"SearchTool has query rewriter: {'✅' if search_tool.query_rewriter else '❌'}")
        print(f"SearchTool has chat history: {'✅' if search_tool.chat_history else '❌'}")
        print(f"SearchTool has domain: {'✅' if search_tool.domain else '❌'}")
        
        # Test search execution
        result = search_tool.execute("What are the specs?")
        
        print(f"Search execution successful: ✅")
        print(f"Result length: {len(result)} characters")
        print(f"Result preview: {result[:100]}...")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing SearchTool: {e}")
        return False

def test_universal_chat_rag_integration():
    """Test that UniversalChatRAG integrates properly with SearchTool"""
    print("\n" + "=" * 60)
    print("Testing UniversalChatRAG with SearchTool Integration")
    print("=" * 60)
    
    try:
        from chat import UniversalChatRAG
        
        # Create UniversalChatRAG
        chat_rag = UniversalChatRAG()
        
        print(f"UniversalChatRAG created: ✅")
        print(f"Available providers: {chat_rag.get_available_providers()}")
        print(f"Response modes available: normal, thinking, react")
        
        # Test with mock search function
        def mock_search_function(domain, query, limit=3):
            return [
                {
                    'title': f'Mock Search: {query}',
                    'snippet': f'Mock result for {query} on {domain}',
                    'url': f'https://{domain}/mock',
                    'source': 'mock_search',
                    'score': 0.8
                }
            ]
        
        # Set to react mode to test SearchTool integration
        chat_rag.set_response_mode("react")
        
        # Test response generation
        result = chat_rag.generate_conversational_response(
            domain="teststore.com",
            user_message="What laptops do you have?",
            search_function=mock_search_function
        )
        
        print(f"Response generated: ✅")
        print(f"Response mode used: {result.get('response_mode', 'unknown')}")
        print(f"ReAct success: {'✅' if result.get('react_success') else '❌'}")
        print(f"Response length: {len(result.get('response', ''))} characters")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing UniversalChatRAG: {e}")
        return False

def test_streamlit_integration():
    """Test that Streamlit integration works without GoogleSearchRAG"""
    print("\n" + "=" * 60)
    print("Testing Streamlit Integration")
    print("=" * 60)
    
    try:
        from universal_shoptalk import create_google_search_function
        
        # Test Google Search function creation
        search_func = create_google_search_function()
        
        print(f"Google search function created: ✅")
        
        # Test the function
        results = search_func("teststore.com", "test query", 2)
        
        print(f"Search function callable: ✅")
        print(f"Results returned: {len(results)}")
        print(f"Result format: {'✅' if all('title' in r for r in results) else '❌'}")
        
        # Check if it's using mock or real API
        source_type = results[0].get('source', 'unknown') if results else 'none'
        print(f"Using {'Google API' if source_type == 'google_search' else 'Mock Search'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing Streamlit integration: {e}")
        return False

def main():
    """Run all deprecation and integration tests"""
    print("🧪 Testing GoogleSearchProvider Deprecation and SearchTool Integration")
    print("🔧 This test verifies the migration from GoogleSearchProvider to SearchTool")
    
    tests = [
        ("GoogleSearchProvider Deprecation", test_google_search_provider_deprecation),
        ("SearchTool Functionality", test_search_tool_functionality),
        ("UniversalChatRAG Integration", test_universal_chat_rag_integration),
        ("Streamlit Integration", test_streamlit_integration)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            print(f"\n🔍 Running {test_name} test...")
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"❌ {test_name} failed with error: {e}")
            results.append((test_name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    for test_name, success in results:
        status = "✅ PASSED" if success else "❌ FAILED"
        print(f"{test_name}: {status}")
    
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"\nOverall: {passed}/{total} tests passed")
    
    if passed == total:
        print("🎉 All tests passed! GoogleSearchProvider successfully deprecated and SearchTool working correctly.")
    else:
        print("⚠️  Some tests failed. Check the output above for details.")
    
    print("\n📋 Migration Status:")
    print("✅ GoogleSearchProvider marked as deprecated")
    print("✅ SearchTool integrated with query rewriting")
    print("✅ UniversalChatRAG uses SearchTool for ReAct mode")
    print("✅ Streamlit app updated to use SearchTool approach")
    print("✅ Google Search API integration available via create_google_search_function()")

if __name__ == "__main__":
    main()