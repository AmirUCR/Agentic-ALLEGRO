"""
agent.py — ALLEGRO agentic loop using Anthropic tool use.

The loop:
  1. Send user message + conversation history to Claude
  2. If Claude returns tool_use blocks, execute each tool
  3. Send tool results back to Claude
  4. Repeat until Claude returns a plain text response (no more tool calls)
  5. Return final response to caller
"""

import json
from typing import Generator
import anthropic

from prompts import SYSTEM_PROMPT
from tools import TOOL_DEFINITIONS, dispatch


MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 4096


class AllegroAgent:
    """
    Stateful agent that maintains conversation history across turns.
    Handles the full tool use agentic loop internally.
    """

    def __init__(self):
        self.client = anthropic.Anthropic()
        self.history: list[dict] = []

    def chat(self, user_message: str, verbose: bool = True) -> str:
        """
        Send a user message, execute any tool calls Claude makes,
        and return Claude's final plain-text response.

        Args:
            user_message: The user's input
            verbose: If True, print tool calls as they happen

        Returns:
            Claude's final response as a string
        """
        self.history.append({"role": "user", "content": user_message})

        while True:
            response = self.client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=SYSTEM_PROMPT,
                tools=TOOL_DEFINITIONS,
                messages=self.history,
            )

            # Add Claude's response to history
            self.history.append({"role": "assistant", "content": response.content})

            # If no tool calls, we're done — return the text response
            if response.stop_reason == "end_turn":
                return self._extract_text(response.content)

            # Handle tool calls
            if response.stop_reason == "tool_use":
                tool_results = []

                for block in response.content:
                    if block.type != "tool_use":
                        continue

                    tool_name = block.name
                    tool_input = block.input
                    tool_use_id = block.id

                    if verbose:
                        print(f"\n  → Calling tool: {tool_name}")
                        print(f"    Input: {json.dumps(tool_input, indent=6)}")

                    result_str = dispatch(tool_name, tool_input)

                    if verbose:
                        # Pretty-print result (truncated)
                        result_preview = result_str[:500] + ("..." if len(result_str) > 500 else "")
                        print(f"    Result: {result_preview}")

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": result_str,
                    })

                # Feed tool results back into the conversation
                self.history.append({"role": "user", "content": tool_results})

            else:
                # Unexpected stop reason
                return self._extract_text(response.content)

    def reset(self):
        """Clear conversation history to start a new session."""
        self.history = []

    @staticmethod
    def _extract_text(content: list) -> str:
        """Extract all text blocks from a response content list."""
        return "\n".join(
            block.text
            for block in content
            if hasattr(block, "text")
        )