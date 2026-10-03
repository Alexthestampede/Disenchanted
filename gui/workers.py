#!/usr/bin/env python3
"""
Disenchanted background worker threads (QThread) for AI calls.

AIWorkerThread   — main chat: plain chat / vision / tool-calling loop
SimpleTaskThread — one-shot generate() calls (titles, compression, memory)
"""
from typing import Optional, List, Dict

from PyQt5.QtCore import QThread, pyqtSignal

from modulle.tools import ToolRegistry


class AIWorkerThread(QThread):
    """Background thread for AI processing to keep UI responsive"""
    finished = pyqtSignal(str)
    error = pyqtSignal(str)
    tool_called = pyqtSignal(str, dict)  # Signal for tool usage (tool_name, args)

    def __init__(self, processor, messages: List[Dict], temperature: Optional[float],
                 image_data: Optional[str] = None, use_vision: bool = False,
                 client=None, model: Optional[str] = None, provider: Optional[str] = None,
                 tool_registry: Optional[ToolRegistry] = None, web_search_enabled: bool = False):
        super().__init__()
        self.processor = processor
        self.messages = messages
        self.temperature = temperature
        self.image_data = image_data
        self.use_vision = use_vision
        self.client = client
        self.model = model
        self.provider = provider
        self.tool_registry = tool_registry
        self.web_search_enabled = web_search_enabled

    def run(self):
        try:
            # Prepare kwargs with optional temperature
            kwargs = {}
            if self.temperature is not None:
                kwargs['temperature'] = self.temperature

            # If we have an image and a vision processor, use analyze_image
            if self.use_vision and self.image_data and hasattr(self.processor, 'analyze_image'):
                # Get the last user message as the prompt
                prompt = self.messages[-1]['content'] if self.messages else "Analyze this image"
                response = self.processor.analyze_image(
                    image_data=self.image_data,
                    prompt=prompt,
                    **kwargs
                )
                if response:
                    self.finished.emit(response)
                else:
                    self.error.emit("AI returned empty response")

            # Web search enabled - use tool calling
            elif self.web_search_enabled and self.client and self.tool_registry and hasattr(self.client, 'chat_with_tools'):
                response_text = self._handle_tool_calling(kwargs)
                if response_text:
                    self.finished.emit(response_text)
                else:
                    self.error.emit("AI returned empty response")

            # Standard chat without tools
            else:
                response = self.processor.chat(
                    messages=self.messages,
                    **kwargs
                )
                if response:
                    self.finished.emit(response)
                else:
                    self.error.emit("AI returned empty response")

        except Exception as e:
            self.error.emit(f"Error: {str(e)}")

    def _handle_tool_calling(self, kwargs):
        """Handle tool calling workflow with web search"""
        MAX_ITERATIONS = 10
        messages = self.messages.copy()

        # Get tool format method based on provider
        tool_format_map = {
            'ollama': 'to_ollama_format',
            'openai': 'to_openai_format',
            'claude': 'to_claude_format',
            'gemini': 'to_gemini_format',
            'lm_studio': 'to_openai_format'
        }
        tool_format = tool_format_map.get(self.provider, 'to_openai_format')
        tools_formatted = getattr(self.tool_registry, tool_format)()

        for iteration in range(MAX_ITERATIONS):
            # Call LLM with tools
            response = self.client.chat_with_tools(
                model=self.model,
                messages=messages,
                tools=tools_formatted,
                **kwargs
            )

            if response['finish_reason'] == 'error':
                raise Exception("Error communicating with LLM")

            # Check if LLM wants to use tools
            if response.get('tool_calls'):
                # Execute each tool call
                for tool_call in response['tool_calls']:
                    tool_name = tool_call['name']
                    tool_args = tool_call['arguments']

                    # Emit signal for UI update
                    self.tool_called.emit(tool_name, tool_args)

                    # Execute the tool
                    try:
                        result = self.tool_registry.execute(tool_name, **tool_args)

                        # Add assistant message with tool call
                        messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{
                                "id": tool_call['id'],
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": tool_args
                                }
                            }]
                        })

                        # Add tool result message
                        tool_result_msg = {
                            "role": "tool",
                            "content": result,
                            "name": tool_name
                        }

                        # Claude needs tool_use_id
                        if self.provider == 'claude':
                            tool_result_msg['tool_use_id'] = tool_call['id']

                        messages.append(tool_result_msg)

                    except Exception as e:
                        # Add error message
                        messages.append({
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [{
                                "id": tool_call['id'],
                                "type": "function",
                                "function": {
                                    "name": tool_name,
                                    "arguments": tool_args
                                }
                            }]
                        })
                        messages.append({
                            "role": "tool",
                            "content": f"Error: {str(e)}",
                            "name": tool_name
                        })
            else:
                # LLM provided final answer
                return response.get('content', '')

        # Max iterations reached
        return response.get('content', '') or "Research incomplete (max iterations reached)"


class SimpleTaskThread(QThread):
    """One-shot generate() for auxiliary tasks (title, compression, HRR)."""
    finished = pyqtSignal(str, str)   # (task_name, result)
    error = pyqtSignal(str, str)      # (task_name, error)

    def __init__(self, task_name: str, processor, prompt: str,
                 temperature: Optional[float] = 0.3):
        super().__init__()
        self.task_name = task_name
        self.processor = processor
        self.prompt = prompt
        self.temperature = temperature

    def run(self):
        try:
            result = self.processor.generate(
                prompt=self.prompt, temperature=self.temperature)
            if result:
                self.finished.emit(self.task_name, result)
            else:
                self.error.emit(self.task_name, "Empty response")
        except Exception as e:
            self.error.emit(self.task_name, str(e))