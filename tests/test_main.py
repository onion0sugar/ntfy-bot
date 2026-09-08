from main import build_new_order_messages


def test_new_orders_are_split_by_zone_group():
    messages = build_new_order_messages(
        [(101, "ZAM-1", 1), (102, "ZAM-2", 2)],
        {"grupa1", "grupa2", "grupa3", "zajety"},
        {"grupa1": 1, "grupa2": 2, "grupa3": 3, "zajety": 3},
        {"zajety"},
        "supervisor",
    )

    recipients_by_order = {
        "ZAM-1": {topic for topic, text, *_ in messages if "ZAM-1" in text},
        "ZAM-2": {topic for topic, text, *_ in messages if "ZAM-2" in text},
    }
    assert recipients_by_order["ZAM-1"] == {"supervisor", "grupa1", "grupa2", "grupa3"}
    assert recipients_by_order["ZAM-2"] == {"supervisor", "grupa2", "grupa3"}


def test_same_zone_group_only_oldest_order_is_sent():
    messages = build_new_order_messages(
        [(101, "STARSZE", 1), (102, "NOWSZE", 1), (103, "INNA-GRUPA", 2)],
        {"grupa1", "grupa2"},
        {"grupa1": 1, "grupa2": 2},
        set(),
        "supervisor",
    )

    texts = [text for _topic, text, *_ in messages]
    assert any("STARSZE" in text for text in texts)
    assert not any("NOWSZE" in text for text in texts)
    assert any("INNA-GRUPA" in text for text in texts)
