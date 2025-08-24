import sys, pathlib
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "agent"))

from tools.normalize import normalize_schedule, normalize_shift, normalize_time_tokens, normalize_role

def test_schedule_extract():
    vals, _ = normalize_schedule("2/2 (возможны 1/3 1/2), 5/2")
    assert "2/2" in vals and "1/3" in vals and "5/2" in vals
    assert "1/2" not in vals  # такого значения нет в справочнике

def test_shift_synonyms():
    assert normalize_shift("дневная 12-часовая") == ["Дневные смены"]
    assert "Суточные смены" in normalize_shift("24ч")

def test_time_parse():
    times, notes = normalize_time_tokens("8:00—20:00")
    assert times == ["08:00 - 20:00"]
    assert notes == []

def test_role_map():
    role, notes = normalize_role("процедурная медсестра")
    assert role == "Процедурная медицинская сестра"
