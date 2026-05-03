from __future__ import annotations

from payment_agent.memory.conversation import ConversationMemory


class TestConversationMemory:
    def test_empty_initial(self):
        mem = ConversationMemory()
        messages = mem.get_messages_for_claude()
        assert messages == []

    def test_add_user_message(self):
        mem = ConversationMemory()
        mem.add_user_message("Hello")
        messages = mem.get_messages_for_claude()
        assert len(messages) == 1
        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Hello"

    def test_add_assistant_message(self):
        mem = ConversationMemory()
        mem.add_assistant_message("Hi there!")
        messages = mem.get_messages_for_claude()
        assert len(messages) == 1
        assert messages[0]["role"] == "assistant"

    def test_add_tool_result(self):
        mem = ConversationMemory()
        mem.add_assistant_tool_use(
            "toolu_123", "lookup_account", {"account_id": "ACC1001"}
        )
        mem.add_tool_result("toolu_123", "Account found. Verification data loaded.")
        messages = mem.get_messages_for_claude()
        assert len(messages) == 2
        assert messages[0]["role"] == "assistant"
        assert messages[1]["role"] == "user"

    def test_conversation_ordering(self):
        mem = ConversationMemory()
        mem.add_user_message("Hi")
        mem.add_assistant_message("Hello!")
        mem.add_user_message("ACC1001")
        messages = mem.get_messages_for_claude()
        assert len(messages) == 3
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]

    def test_window_returns_recent_messages(self):
        mem = ConversationMemory(window_size=4)
        for i in range(10):
            mem.add_user_message(f"msg_{i}")
            mem.add_assistant_message(f"reply_{i}")
        messages = mem.get_messages_for_claude()
        assert len(messages) <= 5  # summary + 4 window

    def test_small_conversation_no_summary(self):
        mem = ConversationMemory(window_size=20)
        mem.add_user_message("Hi")
        mem.add_assistant_message("Hello!")
        messages = mem.get_messages_for_claude()
        assert len(messages) == 2

    def test_get_full_history(self):
        mem = ConversationMemory(window_size=2)
        mem.add_user_message("msg1")
        mem.add_assistant_message("reply1")
        mem.add_user_message("msg2")
        mem.add_assistant_message("reply2")
        full = mem.get_full_history()
        assert len(full) == 4
