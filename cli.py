"""Interactive CLI for the payment collection agent."""

from __future__ import annotations

from payment_agent import Agent


def main() -> None:
    agent = Agent()
    print("=" * 50)
    print("  Payment Collection Agent")
    print("  Type 'quit' to exit")
    print("=" * 50)

    while True:
        try:
            user_input = input("\nYou: ").strip()
            if user_input.lower() in ("quit", "exit", "q"):
                print("\nGoodbye!")
                break
            response = agent.next(user_input)
            print(f"\nAgent: {response['message']}")
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
