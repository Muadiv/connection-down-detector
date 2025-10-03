import time

from connection_monitor import config
from connection_monitor.outage_logger import OutageLogger
from connection_monitor.stats import ServerStats


class DummyLogger(OutageLogger):
    def __init__(self):
        self.logged = []

    def log_outage(self, host, start_ts, end_ts, missed):  # type: ignore[override]
        self.logged.append((host, round(end_ts - start_ts), missed))


def test_latency_classification():
    st = ServerStats("x")
    st.record_result(True, 30, None)
    assert st.classify_latency() == config.EMOJI_GREEN
    st.record_result(True, 120, None)
    assert st.classify_latency() == config.EMOJI_YELLOW
    st.record_result(True, 200, None)
    assert st.classify_latency() == config.EMOJI_RED
    st.record_result(False, None, "timeout")
    assert st.classify_latency() == config.EMOJI_TIMEOUT


def test_outage_grouping():
    st = ServerStats("x")
    logger = DummyLogger()
    # 3 failures triggers outage open
    for _ in range(config.CONSECUTIVE_FAILURES_FOR_OUTAGE):
        st.record_result(False, None, "timeout")
        logger.maybe_open_outage(st)
    assert st.outage_open
    # success closes
    st.record_result(True, 10, None)
    # closing handled by maybe_close_outage
    logger.maybe_close_outage(st)
    assert not st.outage_open
    assert logger.logged  # something logged


def test_packet_loss_and_uptime():
    st = ServerStats("x")
    # 5 successes
    for _ in range(5):
        st.record_result(True, 20, None)
    # 2 failures
    for _ in range(2):
        st.record_result(False, None, "timeout")
    # 3 successes
    for _ in range(3):
        st.record_result(True, 25, None)
    loss = st.packet_loss_pct()
    # total records = 10, failures=2 -> 20%
    assert 19.0 <= loss <= 21.0
    # after success streak, consecutive failures should be 0
    assert st.consecutive_failures == 0
    assert st.current_uptime_streak() >= 0
