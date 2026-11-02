"""发送窗口：9 点后要把昨晚还没发的补上，所以窗口必须能跨天。"""

from datetime import datetime

from core.clock import report_days


def test_window_covers_yesterday_and_today():
    """正常日子：旧的在前，新的在后，方便按时间顺序补发。"""
    days = report_days(datetime(2026, 11, 2, 9, 1), lookback_days=1)
    assert days == ["2026-11-01", "2026-11-02"]


def test_window_crosses_month_boundary():
    """1 号早上的补发要能翻到上个月最后一天。"""
    days = report_days(datetime(2026, 11, 1, 9, 1), lookback_days=1)
    assert days == ["2026-10-31", "2026-11-01"]


def test_window_crosses_year_boundary():
    days = report_days(datetime(2027, 1, 1, 9, 1), lookback_days=1)
    assert days == ["2026-12-31", "2027-01-01"]


def test_lookback_zero_means_today_only():
    days = report_days(datetime(2026, 11, 2, 9, 1), lookback_days=0)
    assert days == ["2026-11-02"]


def test_lookback_three_returns_four_days():
    days = report_days(datetime(2026, 11, 2, 9, 1), lookback_days=3)
    assert days == ["2026-10-30", "2026-10-31", "2026-11-01", "2026-11-02"]


def test_lookback_is_clamped_so_one_typo_cannot_spam():
    """配错成 99 天不该一口气翻一百份报告；负数和乱填退化成今天。"""
    assert len(report_days(datetime(2026, 11, 2, 9, 1), lookback_days=99)) == 8
    assert report_days(datetime(2026, 11, 2, 9, 1), lookback_days=-3) == ["2026-11-02"]
    assert report_days(datetime(2026, 11, 2, 9, 1), lookback_days="abc") == ["2026-11-02"]
