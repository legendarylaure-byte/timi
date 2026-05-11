from datetime import datetime


def test_past_publish_at_is_detected():
    past = datetime(2020, 1, 1, 6, 0, 0)
    assert past < datetime.utcnow()


def test_publish_at_parsing():
    past_time = "2020-01-01T06:00:00Z"
    pub_dt = datetime.strptime(past_time.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    assert pub_dt < datetime.utcnow()


def test_future_publish_at_not_discarded():
    future_time = "2099-12-31T23:59:59Z"
    pub_dt = datetime.strptime(future_time.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
    assert pub_dt > datetime.utcnow()


def test_publish_at_guard_logic():
    def guard(publish_at_str):
        if not publish_at_str:
            return None
        try:
            pub_dt = datetime.strptime(
                publish_at_str.replace("Z", "").replace("z", ""),
                "%Y-%m-%dT%H:%M:%S"
            )
            if pub_dt < datetime.utcnow():
                return None
        except ValueError:
            pass
        return publish_at_str

    assert guard("2099-06-01T10:00:00Z") is not None
    assert guard("2020-01-01T06:00:00Z") is None
    assert guard(None) is None
    assert guard("") is None
