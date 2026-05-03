"""Interactive CLI for the payment collection agent."""

from __future__ import annotations

import os
import sys

from payment_agent import Agent


def main() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable is required.")
        print("Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        sys.exit(1)

    agent = Agent()
    print("=" * 50)
    print("  Payment Collection Agent (Claude-powered)")
    print("  Type 'quit' to exit")
    print("=" * 50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("\nGoodbye!")
                break
            if not user_input:
                continue
            response = agent.next(user_input)
            print(f"\nAgent: {response['message']}")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
