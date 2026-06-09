from mazyr.domain.message import Message, Conversation


class TestMessage:
    def test_message_creation(self):
        msg = Message(
            id="1",
            content="Hello",
            sender="creator",
            platform="cli",
            timestamp="2026-01-01T00:00:00",
        )
        assert msg.is_from_creator is True
        assert msg.is_from_instance is False

    def test_conversation_add(self):
        conv = Conversation(id="test")
        msg = Message(
            id="1",
            content="Hello",
            sender="creator",
            platform="cli",
            timestamp="2026-01-01T00:00:00",
        )
        conv.add_message(msg)
        assert len(conv.messages) == 1
        assert conv.updated_at == msg.timestamp

    def test_conversation_last_n(self):
        conv = Conversation(id="test")
        for i in range(5):
            conv.add_message(
                Message(
                    id=str(i),
                    content=f"msg{i}",
                    sender="creator",
                    platform="cli",
                    timestamp=f"2026-01-01T00:00:0{i}",
                )
            )
        last = conv.last_n(2)
        assert len(last) == 2
        assert last[0].content == "msg3"
