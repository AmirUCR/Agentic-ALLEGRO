#!/usr/bin/env python3
"""
main.py — Interactive CLI for the ALLEGRO agent.

Usage:
    python main.py                  # Start interactive session
    python main.py --once "..."     # Run a single query and exit
"""

import sys
import argparse
from agent import AllegroAgent


BANNER = """
╔══════════════════════════════════════════════════════╗
║           ALLEGRO Agent  •  Powered by Claude        ║
║  CRISPR sgRNA library design assistant               ║
║  Type 'quit' or Ctrl-C to exit  •  'reset' to clear  ║
╚══════════════════════════════════════════════════════╝
"""

EXAMPLE_PROMPTS = [
    "Design a minimal Cas9 sgRNA library for RAD51 across 10 yeast species.",
    "My input is in data/input/my_experiment — what do I need to check before running?",
    "What's the difference between track_e and track_a?",
    "Run ALLEGRO on data/input/example_input using the example species CSV.",
]


def run_interactive(agent: AllegroAgent):
    print(BANNER)
    print("Example prompts:")
    for i, p in enumerate(EXAMPLE_PROMPTS, 1):
        print(f"  {i}. {p}")
    print()

    while True:
        try:
            user_input = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("Goodbye!")
            break

        if user_input.lower() == "reset":
            agent.reset()
            print("Conversation history cleared.\n")
            continue

        print("\nAgent: ", end="", flush=True)
        response = agent.chat(user_input, verbose=True)
        print(f"\n{response}\n")
        print("─" * 60)


def run_once(agent: AllegroAgent, query: str):
    print(f"Query: {query}\n")
    response = agent.chat(query, verbose=True)
    print(f"\nAgent: {response}")


def main():
    parser = argparse.ArgumentParser(description="ALLEGRO AI Agent")
    parser.add_argument("--once", type=str, help="Run a single query and exit.")
    args = parser.parse_args()

    agent = AllegroAgent()

    if args.once:
        run_once(agent, args.once)
    else:
        run_interactive(agent)


if __name__ == "__main__":
    main()