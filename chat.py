"""
Chat Module for Universal ShopTalk
Supports multi-turn conversations with multiple AI APIs (Gemini, Claude, GPT)
"""

import os
import json
import re
import time
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime
import google.generativeai as genai
import openai
import anthropic
from dotenv import load_dotenv

load_dotenv()

class ConversationManager:
    """Manages conversation history and context"""
    
    def __init__(self):
        self.conversations = {}
        self.max_history_length = 10  # Maximum number of turns to keep in memory
        self.context_window = 4000    # Maximum characters for context
    
    def add_message(self, domain: str, role: str, content: str):
        """Add a message to the conversation history"""
        if domain not in self.conversations:
            self.conversations[domain] = []
        
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        self.conversations[domain].append(message)
        
        # Keep only recent messages to prevent memory overflow
        if len(self.conversations[domain]) > self.max_history_length * 2:
            self.conversations[domain] = self.conversations[domain][-self.max_history_length * 2:]
    
    def get_conversation_history(self, domain: str) -> List[Dict[str, Any]]:
        """Get conversation history for a domain"""
        return self.conversations.get(domain, [])
    
    def get_context_string(self, domain: str, exclude_last: bool = False) -> str:
        """Get conversation context as formatted string"""
        history = self.get_conversation_history(domain)
        if exclude_last and len(history) > 0:
            history = history[:-1]
        
        context_parts = []
        for msg in history[-6:]:  # Last 3 exchanges (6 messages)
            role_label = "User" if msg["role"] == "user" else "Assistant"
            # Include full content for both user and assistant messages
            context_parts.append(f"{role_label}: {msg['content']}")
        
        context = "\n".join(context_parts)
        
        # Truncate if too long
        if len(context) > self.context_window:
            context = context[-self.context_window:]
            # Try to start from a complete message
            if "\n" in context:
                context = context[context.find("\n") + 1:]
        
        return context
    
    def get_chat_template_history(self, domain: str, exclude_last: bool = False) -> List[Dict[str, str]]:
        """Get conversation history in chat template format"""
        history = self.get_conversation_history(domain)
        if exclude_last and len(history) > 0:
            history = history[:-1]
        
        # Keep last 6 messages (3 exchanges) to stay within context limits
        recent_history = history[-6:]
        
        chat_messages = []
        for msg in recent_history:
            chat_messages.append({
                "role": msg["role"], 
                "content": msg["content"]
            })
        
        return chat_messages
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for a domain"""
        if domain in self.conversations:
            del self.conversations[domain]
    
    def get_conversation_summary(self, domain: str) -> Dict[str, Any]:
        """Get summary of conversation"""
        history = self.get_conversation_history(domain)
        user_messages = [msg for msg in history if msg["role"] == "user"]
        assistant_messages = [msg for msg in history if msg["role"] == "assistant"]
        
        return {
            "total_turns": len(user_messages),
            "total_messages": len(history),
            "last_interaction": history[-1]["timestamp"] if history else None
        }

class AIProvider:
    """Base class for AI providers"""
    
    def __init__(self, name: str):
        self.name = name
        self.is_available = False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response from AI model"""
        raise NotImplementedError
    
    def generate_response_with_template(self, system_prompt: str, chat_history: List[Dict[str, str]], current_message: str, domain: str = "default") -> str:
        """Generate response using chat template format"""
        # Default implementation - subclasses can override for better template support
        full_prompt = system_prompt + "\n\n"
        
        # Add conversation history
        for msg in chat_history:
            role = "user" if msg["role"] == "user" else "assistant"
            full_prompt += f"{role}: {msg['content']}\n"
        
        # Add current message
        full_prompt += f"user: {current_message}\nassistant:"
        
        return self.generate_response(full_prompt, "")
    
    def generate_response_with_thinking(self, prompt: str, context: str = "") -> Dict[str, str]:
        """Generate response with thinking mode (Chain of Thought)"""
        thinking_prompt = f"""
{context}

{prompt}

Please think through this step-by-step inside <thinking> tags. Explain your reasoning. After you have a final answer, provide it outside the tags.

Format:
<thinking>
Your step-by-step reasoning here...
</thinking>

Your final answer here.
"""
        
        full_response = self.generate_response(thinking_prompt, "")
        
        try:
            # Parse thinking process
            thinking_match = re.search(r"<thinking>(.*?)</thinking>", full_response, re.DOTALL)
            thinking_process = thinking_match.group(1).strip() if thinking_match else ""
            
            # Extract final answer (remove thinking block)
            final_answer = re.sub(r"<thinking>.*?</thinking>", "", full_response, flags=re.DOTALL).strip()
            
            return {
                "thinking_process": thinking_process,
                "final_answer": final_answer,
                "full_response": full_response
            }
        except Exception as e:
            return {
                "thinking_process": f"Error parsing thinking: {e}",
                "final_answer": full_response,
                "full_response": full_response
            }
    
    def check_availability(self) -> bool:
        """Check if the AI provider is available"""
        return self.is_available

class ReactTool:
    """Base class for ReAct tools"""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
    
    def execute(self, tool_input: str) -> str:
        """Execute the tool"""
        raise NotImplementedError

class QueryRewriter:
    """Query rewriting system using thinking model"""
    
    def __init__(self, ai_provider: AIProvider):
        self.ai_provider = ai_provider
    
    def rewrite_query(self, chat_history: List[Dict[str, str]], current_question: str, domain: str) -> Dict[str, str]:
        """Rewrite query based on chat history and current question"""
        
        # Build context from chat history
        history_context = ""
        if chat_history:
            history_context = "Previous conversation:\n"
            for msg in chat_history[-4:]:  # Last 2 exchanges
                role = "User" if msg["role"] == "user" else "Assistant"
                history_context += f"{role}: {msg['content']}\n"
        
        thinking_prompt = f"""You are a query rewriting assistant. Your task is to analyze the conversation history and current question to create an optimal search query.

Domain: {domain}
{history_context}

Current question: {current_question}

Please think through this step-by-step inside <thinking> tags, then provide the rewritten query.

<thinking>
1. Analyze the conversation history to understand the context
2. Identify what the user is really looking for
3. Consider the domain context
4. Create a search query that captures the intent and context
5. Make the query specific enough to find relevant information
</thinking>

Rewritten search query: [Your optimized query here]
Reasoning: [Brief explanation of why this query is better]"""

        try:
            if hasattr(self.ai_provider, 'generate_response_with_template'):
                response = self.ai_provider.generate_response_with_template(
                    thinking_prompt, [], current_question, f"rewrite_{domain}"
                )
            else:
                response = self.ai_provider.generate_response(thinking_prompt)
            
            # Parse the response
            thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL)
            thinking_process = thinking_match.group(1).strip() if thinking_match else ""
            
            # Extract rewritten query
            query_match = re.search(r"Rewritten search query:\s*(.*?)(?:\n|$)", response)
            rewritten_query = query_match.group(1).strip() if query_match else current_question
            
            # Extract reasoning
            reasoning_match = re.search(r"Reasoning:\s*(.*?)(?:\n|$)", response)
            reasoning = reasoning_match.group(1).strip() if reasoning_match else "Query rewriting applied"
            
            return {
                "rewritten_query": rewritten_query,
                "thinking_process": thinking_process,
                "reasoning": reasoning,
                "original_query": current_question
            }
            
        except Exception as e:
            print(f"Query rewriting error: {e}")
            return {
                "rewritten_query": current_question,
                "thinking_process": f"Error in query rewriting: {e}",
                "reasoning": "Using original query due to rewriting error",
                "original_query": current_question
            }

class SearchTool(ReactTool):
    """Search tool for ReAct framework with Google API and query rewriting"""
    
    def __init__(self, search_function: Optional[Callable] = None, ai_provider: Optional[AIProvider] = None, 
                 chat_history: Optional[List[Dict[str, str]]] = None, domain: str = ""):
        super().__init__("search", "A search engine that can look up recent information using Google API")
        self.search_function = search_function
        self.query_rewriter = QueryRewriter(ai_provider) if ai_provider else None
        self.chat_history = chat_history or []
        self.domain = domain
    
    def execute(self, tool_input: str) -> str:
        """Execute search with query rewriting and Google API"""
        
        # Rewrite query using thinking model if available
        rewrite_result = None
        search_query = tool_input
        
        if self.query_rewriter:
            rewrite_result = self.query_rewriter.rewrite_query(
                self.chat_history, tool_input, self.domain
            )
            search_query = rewrite_result["rewritten_query"]
            print(f"ming-debug: Query rewritten from '{tool_input}' to '{search_query}'")
            print(f"ming-debug: Reasoning: {rewrite_result['reasoning']}")
        
        # Execute search
        if not self.search_function:
            # Fallback mock responses
            if "apple" in search_query.lower() and "ceo" in search_query.lower():
                return "Tim Cook is the current CEO of Apple Inc."
            elif "iphone" in search_query.lower():
                return "Apple Inc. designs and manufactures the iPhone."
            else:
                return f"No information found for query: {search_query}"
        
        try:
            # Use Google search function with rewritten query
            results = self.search_function(self.domain, search_query, 3)
            
            if results:
                formatted_results = []
                for i, result in enumerate(results, 1):
                    title = result.get('title', 'Unknown')
                    snippet = result.get('snippet', result.get('text', ''))[:200]
                    url = result.get('url', '')
                    
                    result_text = f"{i}. {title}"
                    if snippet:
                        result_text += f": {snippet}"
                    if url:
                        result_text += f" (Source: {url})"
                    
                    formatted_results.append(result_text)
                
                search_summary = "\n".join(formatted_results)
                
                # Add query rewriting info if available
                if rewrite_result:
                    search_summary = f"Search query: '{search_query}' (rewritten from '{tool_input}')\n\nResults:\n{search_summary}"
                
                return search_summary
            else:
                return f"No search results found for: {search_query}"
                
        except Exception as e:
            return f"Google search error: {str(e)}"

class ThinkingReactAgent:
    """Unified Thinking + ReAct Agent that uses thinking model to decide on actions"""
    
    def __init__(self, ai_provider: AIProvider, tools: List[ReactTool]):
        self.ai_provider = ai_provider
        self.tools = {tool.name: tool for tool in tools}
        self.max_turns = 5  # Safety limit
    
    def run(self, question: str, chat_history: Optional[List[Dict[str, str]]] = None, domain: str = "") -> Dict[str, Any]:
        """Run the unified thinking-react loop"""
        
        # Create tool descriptions
        tool_descriptions = []
        for tool in self.tools.values():
            tool_descriptions.append(f"- `{tool.name}(query)`: {tool.description}")
        
        tools_text = "\n".join(tool_descriptions)
        
        system_prompt = f"""You are an intelligent assistant that thinks step-by-step and can use external tools when needed.

Available tools:
{tools_text}

Instructions:
1. Always start by thinking through the problem step-by-step inside <thinking> tags
2. In your thinking, decide whether you need to use tools or can answer directly
3. If you need to use tools, specify the tool and optimized query
4. If you can answer directly, provide the answer after thinking

Format:
<thinking>
Let me think about this question step by step:
1. [Analyze the question and context]
2. [Determine if I need to search for information]
3. [If search needed, what would be the best search query?]
4. [Plan my response approach]
</thinking>

If tool needed:
Action: {{"tool": "search", "tool_input": "optimized search query"}}

If no tool needed:
Final Answer: [Your direct answer]

Always think first, then act if necessary."""

        # Update search tools with chat history and domain context
        for tool in self.tools.values():
            if isinstance(tool, SearchTool):
                tool.chat_history = chat_history or []
                tool.domain = domain
        
        # Initialize conversation
        thinking_react_history = []
        turn_history = []
        
        # Start with the question
        current_message = question
        
        print(f"ming-debug: ThinkingReactAgent starting with question: {question}")
        print(f"ming-debug: chat_history: {chat_history}")
        print(f"ming-debug: domain: {domain}")

        for turn in range(self.max_turns):
            print(f"ming-debug: thinking-react turn: {turn}")
            
            # Call the AI model using template format if available
            if hasattr(self.ai_provider, 'generate_response_with_template'):
                response = self.ai_provider.generate_response_with_template(
                    system_prompt, thinking_react_history, current_message, f"thinking_react_{domain}"
                )
            else:
                # Fallback to regular format
                full_prompt = f"{system_prompt}\n\nQuestion: {current_message}"
                for msg in thinking_react_history:
                    role = "user" if msg["role"] == "user" else "assistant"
                    full_prompt += f"\n{role}: {msg['content']}"
                response = self.ai_provider.generate_response(full_prompt)
            
            turn_history.append({"turn": turn + 1, "model_output": response})
            
            # Add assistant response to history
            thinking_react_history.append({"role": "assistant", "content": response})
            
            # Extract thinking process
            thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL)
            thinking_process = thinking_match.group(1).strip() if thinking_match else ""
            
            # Check for Final Answer (direct response without tools)
            if "Final Answer:" in response:
                final_answer = response.split("Final Answer:")[-1].strip()
                return {
                    "success": True,
                    "final_answer": final_answer,
                    "turns": turn_history,
                    "total_turns": turn + 1,
                    "thinking_process": thinking_process,
                    "used_tools": False
                }
            
            # Check for Action (tool usage)
            action_match = re.search(r"Action:\s*(.*?)(?=\n|$)", response, re.DOTALL)
            if action_match:
                action_text = action_match.group(1).strip()
                
                # Try to extract JSON from various formats
                json_patterns = [
                    r'\{[^}]*\}',  # Simple JSON pattern
                    r'```json\s*(\{[^}]*\})\s*```',  # JSON in code blocks
                    r'```\s*(\{[^}]*\})\s*```',  # JSON in generic code blocks
                ]
                
                action_data = None
                for pattern in json_patterns:
                    json_match = re.search(pattern, action_text, re.DOTALL)
                    if json_match:
                        try:
                            json_str = json_match.group(1) if json_match.groups() else json_match.group(0)
                            action_data = json.loads(json_str)
                            break
                        except json.JSONDecodeError:
                            continue
                
                if action_data and "tool" in action_data and "tool_input" in action_data:
                    tool_name = action_data["tool"]
                    tool_input = action_data["tool_input"]
                    
                    if tool_name in self.tools:
                        tool_result = self.tools[tool_name].execute(tool_input)
                    else:
                        tool_result = f"Error: Unknown tool '{tool_name}'. Available tools: {list(self.tools.keys())}"
                    
                    # Create observation message
                    observation_message = f"Observation: {tool_result}\n\nNow provide your final answer based on this information."
                    current_message = observation_message
                    
                    # Add observation to history
                    thinking_react_history.append({"role": "user", "content": observation_message})
                    turn_history[-1]["observation"] = tool_result
                    turn_history[-1]["thinking_process"] = thinking_process
                    
                else:
                    # If action parsing failed, try to get direct answer
                    final_answer_match = re.search(r"(?:Final Answer:|Answer:)\s*(.*)", response, re.DOTALL | re.IGNORECASE)
                    if final_answer_match:
                        final_answer = final_answer_match.group(1).strip()
                        return {
                            "success": True,
                            "final_answer": final_answer,
                            "turns": turn_history,
                            "total_turns": turn + 1,
                            "thinking_process": thinking_process,
                            "used_tools": False
                        }
                    else:
                        error_message = f"Could not parse action from: {action_text[:100]}. Please provide a direct answer or use proper action format."
                        current_message = error_message
                        thinking_react_history.append({"role": "user", "content": error_message})
                        turn_history[-1]["error"] = "Action parsing failed"
                        turn_history[-1]["thinking_process"] = thinking_process
            else:
                # No action found, but no final answer either - ask for clarification
                clarification = "Please provide either a Final Answer or an Action to use a tool."
                current_message = clarification
                thinking_react_history.append({"role": "user", "content": clarification})
                turn_history[-1]["thinking_process"] = thinking_process
        
        return {
            "success": False,
            "final_answer": "Max turns reached without final answer",
            "turns": turn_history,
            "total_turns": self.max_turns,
            "thinking_process": "",
            "used_tools": False
        }

class ReactAgent:
    """DEPRECATED: ReAct (Reasoning + Acting) Agent - Use ThinkingReactAgent instead"""
    
    def __init__(self, ai_provider: AIProvider, tools: List[ReactTool]):
        print("WARNING: ReactAgent is deprecated. Use ThinkingReactAgent instead.")
        self.ai_provider = ai_provider
        self.tools = {tool.name: tool for tool in tools}
        self.max_turns = 5  # Safety limit
    
    def run(self, question: str, chat_history: Optional[List[Dict[str, str]]] = None, domain: str = "") -> Dict[str, Any]:
        """Run the ReAct agent loop with chat history context"""
        
        # Create tool descriptions
        tool_descriptions = []
        for tool in self.tools.values():
            tool_descriptions.append(f"- `{tool.name}(query)`: {tool.description}")
        
        tools_text = "\n".join(tool_descriptions)
        
        system_prompt = f"""You are a helpful assistant that can use external tools. You have access to the following tools:
{tools_text}

To answer the question, you must follow this cycle strictly:
Thought: Think about what you need to do to answer the question.
Action: Output a JSON blob with the tool to use, like {{"tool": "search", "tool_input": "your query"}}.
Observation: I will provide the result from the tool.
... (repeat Thought/Action/Observation as needed)
Thought: I have now gathered enough information to answer the question.
Final Answer: The final answer to the original question.\n\n"""
        
        # Initialize conversation history for ReAct
        react_history = []
        turn_history = []
        
        # Update search tools with chat history and domain context
        for tool in self.tools.values():
            if isinstance(tool, SearchTool):
                tool.chat_history = chat_history or []
                tool.domain = domain
        
        # Start with the initial question
        current_message = f"Begin!\n\nQuestion: {question}"
        
        print(f"ming-debug: self.ai_provider: {self.ai_provider}")
        print(f"ming-debug: chat_history for ReAct: {chat_history}")
        print(f"ming-debug: domain for ReAct: {domain}")

        for turn in range(self.max_turns):
            print(f"ming-debug: turn: {turn}")
            # Call the AI model using template format if available
            if hasattr(self.ai_provider, 'generate_response_with_template'):
                
                print(f"ming-debug: system_prompt: {system_prompt}"
                      f"react_history: {react_history}"
                      f"current_message: {current_message}"
                      )

                response = self.ai_provider.generate_response_with_template(
                    system_prompt, react_history, current_message, "react_session"
                )
            else:
                # Fallback to regular format
                full_prompt = system_prompt + "\n\n" + current_message
                for msg in react_history:
                    role = "user" if msg["role"] == "user" else "assistant"
                    full_prompt += f"\n{role}: {msg['content']}"

                print(f"ming-debug: full_prompt: {full_prompt}")

                response = self.ai_provider.generate_response(full_prompt)
            
            turn_history.append({"turn": turn + 1, "model_output": response})
            
            # Add assistant response to history
            react_history.append({"role": "assistant", "content": response})
            
            # Check for Final Answer
            if "Final Answer:" in response:
                final_answer = response.split("Final Answer:")[-1].strip()
                return {
                    "success": True,
                    "final_answer": final_answer,
                    "turns": turn_history,
                    "total_turns": turn + 1
                }
            
            # Parse and execute action
            action_match = re.search(r"Action:\s*(.*?)(?=\n\n|$)", response, re.DOTALL)
            if action_match:
                action_text = action_match.group(1).strip()
                
                # Try to extract JSON from various formats
                json_patterns = [
                    r'\{[^}]*\}',  # Simple JSON pattern
                    r'```json\s*(\{[^}]*\})\s*```',  # JSON in code blocks
                    r'```\s*(\{[^}]*\})\s*```',  # JSON in generic code blocks
                ]
                
                action_data = None
                for pattern in json_patterns:
                    json_match = re.search(pattern, action_text, re.DOTALL)
                    if json_match:
                        try:
                            json_str = json_match.group(1) if json_match.groups() else json_match.group(0)
                            action_data = json.loads(json_str)
                            break
                        except json.JSONDecodeError:
                            continue
                
                if action_data and "tool" in action_data and "tool_input" in action_data:
                    tool_name = action_data["tool"]
                    tool_input = action_data["tool_input"]
                    
                    if tool_name in self.tools:
                        tool_result = self.tools[tool_name].execute(tool_input)
                    else:
                        tool_result = f"Error: Unknown tool '{tool_name}'. Available tools: {list(self.tools.keys())}"
                    
                    # Create observation message
                    observation_message = f"Observation: {tool_result}"
                    current_message = observation_message
                    
                    # Add observation to history
                    react_history.append({"role": "user", "content": observation_message})
                    turn_history[-1]["observation"] = tool_result
                    
                else:
                    error_message = f"Observation: Could not parse action JSON from: {action_text[:100]}. Please use format: {{\"tool\": \"search\", \"tool_input\": \"your query\"}}"
                    current_message = error_message
                    react_history.append({"role": "user", "content": error_message})
                    turn_history[-1]["error"] = "JSON parsing failed"
            else:
                # No action found, end loop
                break
        
        return {
            "success": False,
            "final_answer": "Max turns reached without final answer",
            "turns": turn_history,
            "total_turns": self.max_turns
        }

class GeminiProvider(AIProvider):
    """Google Gemini AI Provider"""
    
    def __init__(self):
        super().__init__("Gemini")
        self.model = None
        self.chat_sessions = {}  # Store chat sessions per domain
        self._setup()
    
    def _setup(self):
        """Setup Gemini API"""
        api_key = os.getenv('GOOGLE_API_KEY')
        if api_key:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-1.5-flash')
                self.is_available = True
            except Exception as e:
                print(f"Failed to setup Gemini: {e}")
                self.is_available = False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response using Gemini"""
        if not self.is_available or not self.model:
            return "Gemini is not available. Please check your GOOGLE_API_KEY."
        
        try:
            full_prompt = f"{context}\n\n{prompt}" if context else prompt
            response = self.model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            return f"Error generating response with Gemini: {str(e)}"
    
    def get_or_create_chat_session(self, domain: str, system_prompt: str, chat_history: List[Dict[str, str]]) -> Any:
        """Get existing chat session or create a new one for the domain"""
        session_key = f"{domain}:{hash(system_prompt)}"
        
        if session_key not in self.chat_sessions:
            try:
                # Create a new model instance with system instruction
                model_with_system = genai.GenerativeModel(
                    'gemini-1.5-flash',
                    system_instruction=system_prompt
                )
                
                # Convert chat history to Gemini format
                history = []
                for msg in chat_history:
                    if msg["role"] == "user":
                        history.append({"role": "user", "parts": [msg["content"]]})
                    elif msg["role"] == "assistant":
                        history.append({"role": "model", "parts": [msg["content"]]})
                
                # Start a chat session with history
                chat = model_with_system.start_chat(history=history)
                self.chat_sessions[session_key] = chat
                
            except Exception as e:
                print(f"Error creating chat session: {e}")
                return None
        
        return self.chat_sessions.get(session_key)
    
    def clear_chat_session(self, domain: str):
        """Clear chat session for a domain"""
        # Remove all sessions for this domain
        keys_to_remove = [key for key in self.chat_sessions.keys() if key.startswith(f"{domain}:")]
        for key in keys_to_remove:
            del self.chat_sessions[key]
    
    def generate_response_with_template(self, system_prompt: str, chat_history: List[Dict[str, str]], current_message: str, domain: str = "default") -> str:
        """Generate response using chat template format for Gemini with persistent session"""
        if not self.is_available:
            return "Gemini is not available. Please check your GOOGLE_API_KEY."
        
        try:
            # Get or create persistent chat session
            chat = self.get_or_create_chat_session(domain, system_prompt, chat_history)
            
            if chat is None:
                return "Error: Could not create chat session."
            
            # Send the current message
            response = chat.send_message(current_message)
            return response.text
            
        except Exception as e:
            return f"Error generating response with Gemini: {str(e)}"

class ClaudeProvider(AIProvider):
    """Anthropic Claude AI Provider"""
    
    def __init__(self):
        super().__init__("Claude")
        self.client = None
        self._setup()
    
    def _setup(self):
        """Setup Claude API"""
        api_key = os.getenv('ANTHROPIC_API_KEY')
        if api_key:
            try:
                self.client = anthropic.Anthropic(api_key=api_key)
                self.is_available = True
            except Exception as e:
                print(f"Failed to setup Claude: {e}")
                self.is_available = False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response using Claude"""
        if not self.is_available or not self.client:
            return "Claude is not available. Please check your ANTHROPIC_API_KEY."
        
        try:
            messages = []
            if context:
                messages.append({"role": "user", "content": context})
                messages.append({"role": "assistant", "content": "I understand the conversation context."})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            return f"Error generating response with Claude: {str(e)}"
    
    def generate_response_with_template(self, system_prompt: str, chat_history: List[Dict[str, str]], current_message: str, domain: str = "default") -> str:
        """Generate response using chat template format for Claude"""
        if not self.is_available or not self.client:
            return "Claude is not available. Please check your ANTHROPIC_API_KEY."
        
        try:
            # Claude uses proper message format
            messages = []
            
            # Add conversation history
            for msg in chat_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current message
            messages.append({
                "role": "user", 
                "content": current_message
            })
            
            response = self.client.messages.create(
                model="claude-3-haiku-20240307",
                max_tokens=1000,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            return f"Error generating response with Claude: {str(e)}"

class GPTProvider(AIProvider):
    """OpenAI GPT AI Provider"""
    
    def __init__(self):
        super().__init__("GPT")
        self.client = None
        self._setup()
    
    def _setup(self):
        """Setup OpenAI API"""
        api_key = os.getenv('OPENAI_API_KEY')
        if api_key:
            try:
                self.client = openai.OpenAI(api_key=api_key)
                self.is_available = True
            except Exception as e:
                print(f"Failed to setup GPT: {e}")
                self.is_available = False
    
    def generate_response(self, prompt: str, context: str = "") -> str:
        """Generate response using GPT"""
        if not self.is_available or not self.client:
            return "GPT is not available. Please check your OPENAI_API_KEY."
        
        try:
            messages = []
            if context:
                messages.append({"role": "system", "content": f"Previous conversation context:\n{context}"})
            
            messages.append({"role": "user", "content": prompt})
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response with GPT: {str(e)}"
    
    def generate_response_with_template(self, system_prompt: str, chat_history: List[Dict[str, str]], current_message: str, domain: str = "default") -> str:
        """Generate response using chat template format for GPT"""
        if not self.is_available or not self.client:
            return "GPT is not available. Please check your OPENAI_API_KEY."
        
        try:
            # GPT uses proper message format with system prompt
            messages = [{"role": "system", "content": system_prompt}]
            
            # Add conversation history
            for msg in chat_history:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
            
            # Add current message
            messages.append({
                "role": "user", 
                "content": current_message
            })
            
            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=messages,
                max_tokens=1000,
                temperature=0.7
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response with GPT: {str(e)}"

class UniversalChatRAG:
    """Universal Chat RAG system with multiple AI provider support"""
    
    def __init__(self):
        self.conversation_manager = ConversationManager()
        self.providers = {
            "gemini": GeminiProvider(),
            "claude": ClaudeProvider(),
            "gpt": GPTProvider()
        }
        self.default_provider = "gemini"
        
        # Find the first available provider as default
        for name, provider in self.providers.items():
            if provider.is_available:
                self.default_provider = name
                break
        
        # Response modes
        self.response_mode = "normal"  # Options: "normal", "thinking", "react"
    
    def get_available_providers(self) -> List[str]:
        """Get list of available AI providers"""
        return [name for name, provider in self.providers.items() if provider.is_available]
    
    def set_provider(self, provider_name: str) -> bool:
        """Set the active AI provider"""
        if provider_name in self.providers and self.providers[provider_name].is_available:
            self.default_provider = provider_name
            return True
        return False
    
    def set_response_mode(self, mode: str) -> bool:
        """Set the response mode: 'normal', 'thinking_react', or 'react' (deprecated)"""
        # Map old modes to new unified mode
        mode_mapping = {
            "thinking": "thinking_react",
            "react": "thinking_react"
        }
        
        actual_mode = mode_mapping.get(mode, mode)
        
        if actual_mode in ["normal", "thinking_react"]:
            self.response_mode = actual_mode
            return True
        return False
    
    def get_response_mode(self) -> str:
        """Get current response mode"""
        return self.response_mode
    
    def search_website_content(self, domain: str, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        """Search website content (placeholder for integration with existing search)"""
        # This would integrate with the existing search functionality
        # For now, return empty list as placeholder
        # Parameters are kept for interface compatibility
        _ = domain, query, limit  # Suppress unused parameter warnings
        return []
    
    def format_search_context(self, search_results: List[Dict[str, Any]], domain: str) -> str:
        """Format search results into context string"""
        if not search_results:
            return f"No specific information found for {domain}. Please provide general assistance."
        
        context = f"\n{domain.upper()} Website Information:\n"
        for result in search_results:
            context += f"- {result.get('title', 'Unknown')}: {result.get('snippet', '')[:200]}...\n"
            if 'url' in result:
                context += f"  Source: {result['url']}\n\n"
        
        return context
    
    def generate_conversational_response(
        self, 
        domain: str, 
        user_message: str, 
        provider_name: Optional[str] = None,
        search_function: Optional[Callable] = None,
        response_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a conversational response with context"""

        # Use specified response mode or default
        current_mode = response_mode or self.response_mode
        
        # Use specified provider or default
        provider_name = provider_name or self.default_provider
        provider = self.providers.get(provider_name)
        
        if not provider or not provider.is_available:
            return {
                'response': f"AI provider '{provider_name}' is not available.",
                'provider_used': provider_name,
                'conversation_context_used': "",
                'sources': [],
                'rewritten_keyphrases': [user_message],
                'rewrite_reasoning': "Provider not available",
                'response_mode': current_mode
            }
        
        # Get conversation context - exclude only the current user message, not assistant responses
        conversation_context = self.conversation_manager.get_context_string(domain, exclude_last=False)
        chat_history = self.conversation_manager.get_chat_template_history(domain, exclude_last=False)
        
        print(f"ming-debug: chat_history: {chat_history}")

        # Initialize website context - will be populated differently based on mode
        website_context = f"No specific information available for {domain}. Please provide general assistance."
        search_results = []
        
        # Build the system prompt
        system_prompt = f"""You are ShopTalk, a universal shopping assistant that helps customers with questions about any website.

Current website: {domain}
AI Provider: {provider.name}

{website_context}

Instructions:
- Use the provided website information to answer questions about products, services, and policies
- Consider the conversation history to provide contextual responses
- For product questions, include specific details like prices, sizes, colors, materials, and availability when available
- If you have specific information from the website, reference it with source URLs
- If you don't have specific information, acknowledge this and provide helpful general guidance
- Maintain a helpful, professional tone appropriate for customer service
- Focus on being accurate and citing sources when available
- For product recommendations, consider the customer's needs and highlight relevant features
- Keep responses concise but informative

Respond as a knowledgeable shopping assistant for {domain}."""
        
        print(f"ming-debug: response_mode: {current_mode}")
        
        # Handle different response modes
        if current_mode == "thinking_react":
            # Use unified ThinkingReact framework
            search_tool = SearchTool(
                search_function=search_function,
                ai_provider=provider,
                chat_history=chat_history,
                domain=domain
            )
            tools = [search_tool]
            thinking_react_agent = ThinkingReactAgent(provider, tools)
            
            # Create context-aware question for ThinkingReact
            thinking_react_question = f"""You are assisting customers with questions about {domain}.

Previous conversation context:
{conversation_context if conversation_context else "No previous conversation."}

Current customer question: {user_message}

Think step-by-step about whether you need to search for information or can provide a helpful response directly. If you need to search, formulate an optimized search query based on the conversation context and the customer's question."""
            
            thinking_react_result = thinking_react_agent.run(thinking_react_question, chat_history, domain)
            response = thinking_react_result["final_answer"]
            
            # Extract website context from SearchTool output if tools were used
            extracted_search_results = []
            if thinking_react_result.get("used_tools", False):
                for turn in thinking_react_result.get("turns", []):
                    if "observation" in turn:
                        # Parse search results from observation
                        observation = turn["observation"]
                        if "Search query:" in observation and "Results:" in observation:
                            # Extract search information from SearchTool output
                            lines = observation.split('\n')
                            for line in lines:
                                if line.strip().startswith(('1.', '2.', '3.')):
                                    # Parse result line: "1. Title: snippet (Source: url)"
                                    try:
                                        parts = line.split(': ', 2)
                                        if len(parts) >= 2:
                                            title_part = parts[1]
                                            if '(Source:' in title_part:
                                                title, url_part = title_part.split('(Source:', 1)
                                                url = url_part.rstrip(')')
                                            else:
                                                title = title_part
                                                url = ''
                                            
                                            extracted_search_results.append({
                                                'title': title.strip(),
                                                'snippet': title.strip(),
                                                'url': url.strip(),
                                                'source': 'thinking_react_tool'
                                            })
                                    except:
                                        continue
            
            # Update website context from SearchTool results
            if extracted_search_results:
                website_context = self.format_search_context(extracted_search_results, domain)
                search_results = extracted_search_results
            
            # Add to conversation history
            self.conversation_manager.add_message(domain, "user", user_message)
            self.conversation_manager.add_message(domain, "assistant", response)
            
            return {
                'response': response,
                'provider_used': provider_name,
                'conversation_context_used': conversation_context,
                'sources': search_results,
                'rewritten_keyphrases': [user_message],
                'rewrite_reasoning': "Using ThinkingReact framework with intelligent query optimization",
                'response_mode': current_mode,
                'thinking_process': thinking_react_result.get("thinking_process", ""),
                'react_turns': thinking_react_result.get("turns", []),
                'react_success': thinking_react_result.get("success", False),
                'total_react_turns': thinking_react_result.get("total_turns", 0),
                'website_context': website_context,
                'used_tools': thinking_react_result.get("used_tools", False)
            }
            
        else:
            # Normal mode - optionally use search function for context
            if search_function:
                try:
                    search_results = search_function(domain, user_message, limit=3)
                    website_context = self.format_search_context(search_results, domain)
                    
                    # Update system prompt with search context
                    system_prompt = f"""You are ShopTalk, a universal shopping assistant that helps customers with questions about any website.

Current website: {domain}
AI Provider: {provider.name}

{website_context}

Instructions:
- Use the provided website information to answer questions about products, services, and policies
- Consider the conversation history to provide contextual responses
- For product questions, include specific details like prices, sizes, colors, materials, and availability when available
- If you have specific information from the website, reference it with source URLs
- If you don't have specific information, acknowledge this and provide helpful general guidance
- Maintain a helpful, professional tone appropriate for customer service
- Focus on being accurate and citing sources when available
- For product recommendations, consider the customer's needs and highlight relevant features
- Keep responses concise but informative

Respond as a knowledgeable shopping assistant for {domain}."""
                except Exception as e:
                    print(f"Search function error in normal mode: {e}")
            
            # Use chat template for better multi-turn conversation
            if hasattr(provider, 'generate_response_with_template'):
                response = provider.generate_response_with_template(system_prompt, chat_history, user_message, domain)
            else:
                # Fallback for providers without template support
                response = provider.generate_response(system_prompt + f"\n\nUser: {user_message}", conversation_context)
            
            # Add to conversation history
            self.conversation_manager.add_message(domain, "user", user_message)
            self.conversation_manager.add_message(domain, "assistant", response)

            return {
                'response': response,
                'provider_used': provider_name,
                'conversation_context_used': conversation_context,
                'sources': search_results,
                'rewritten_keyphrases': [user_message],
                'rewrite_reasoning': "Using original query",
                'response_mode': current_mode,
                'website_context': website_context
            }
    
    def clear_conversation(self, domain: str):
        """Clear conversation history for a domain"""
        self.conversation_manager.clear_conversation(domain)
        
        # Also clear any persistent chat sessions for Gemini
        for provider in self.providers.values():
            if hasattr(provider, 'clear_chat_session'):
                provider.clear_chat_session(domain)
    
    def get_conversation_summary(self, domain: str) -> Dict[str, Any]:
        """Get conversation summary for a domain"""
        return self.conversation_manager.get_conversation_summary(domain)
    
    def get_conversation_history(self, domain: str) -> List[Dict[str, Any]]:
        """Get full conversation history for a domain"""
        return self.conversation_manager.get_conversation_history(domain)

# Convenience function for easy integration
def create_chat_system() -> UniversalChatRAG:
    """Create and return a new chat system instance"""
    return UniversalChatRAG()