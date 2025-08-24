from __future__ import annotations
import re, difflib, os, pathlib
from typing import Dict, List, Tuple, Set, Optional

TIME_RE = re.compile(
    r"(?P<h1>\d{1,2})[:.\-‐–—]?(?P<m1>\d{2})\s*[-–—]\s*(?P<h2>\d{1,2})[:.\-‐–—]?(?P<m2>\d{2})"
)
ONLY_HOURS_RE = re.compile(r"(?<!\d)(8|12|24)\s*час", re.I)

# Синонимы → канон
SHIFT_SYNONYMS = {
    "сутки": "Суточные смены",
    "24ч": "Суточные смены",
    "24 ч": "Суточные смены",
    "круглосуточно": "Суточные смены",
    "дневная": "Дневные смены",
    "дневн": "Дневные смены",
    "вечерняя": "Вечерние смены",
    "вечерн": "Вечерние смены",
}
ROLE_SYNONYMS = {
    "палатная медсестра": "Палатная медицинская сестра",
    "процедурная медсестра": "Процедурная медицинская сестра",
    "операционная медсестра": "Операционная медицинская сестра",
}
DEPT_TYPO = {
    # часто встречающиеся опечатки
    "анестезиолгии": "анестезиологии",
    "анестезиолоии": "анестезиологии",
}

def trim(s: str) -> str:
    return re.sub(r"\s+", " ", s.strip())

def _canon_time(h1: str, m1: str, h2: str, m2: str) -> str:
    return f"{int(h1):02d}:{int(m1):02d} - {int(h2):02d}:{int(m2):02d}"

def normalize_time_tokens(raw: str) -> Tuple[List[str], List[str]]:
    """Возвращает ([валидные интервалы], [заметки])."""
    notes: List[str] = []
    s = raw
    s = s.replace("—", "-").replace("–", "-")
    found = TIME_RE.findall(s)
    res: List[str] = []
    for h1, m1, h2, m2 in found:
        res.append(_canon_time(h1, m1, h2, m2))
    if not res and ONLY_HOURS_RE.search(s):
        notes.append("Указаны только часы без интервала")
    return (sorted(set(res)), notes)

def normalize_shift(raw: str) -> List[str]:
    s = trim(raw).lower()
    out: Set[str] = set()
    for key, val in SHIFT_SYNONYMS.items():
        if key in s:
            out.add(val)
    # прямые канонические значения пропускаем как есть
    if s in {"суточные", "суточные смены"}:
        out.add("Суточные смены")
    if s in {"дневные", "дневные смены"}:
        out.add("Дневные смены")
    if s in {"вечерние", "вечерние смены"}:
        out.add("Вечерние смены")
    return sorted(out)

def normalize_schedule(raw: str) -> Tuple[List[str], List[str]]:
    s = trim(raw).replace("или", ",").replace("возможны", ",")
    candidates = re.findall(r"\b\d\s*/\s*\d\b", s)  # 1/3, 2/2, 5/2
    clean = [c.replace(" ", "") for c in candidates]
    return (sorted(set(clean)), [])

def normalize_role(raw: str) -> Tuple[str, List[str]]:
    s = trim(raw)
    l = s.lower()
    if l in ROLE_SYNONYMS:
        return ROLE_SYNONYMS[l], []
    return s, []

def normalize_dept(raw: str, aliases: Dict[str, str]) -> Tuple[str, List[str]]:
    s = trim(raw)
    base = s
    # правим опечатки
    for bad, good in DEPT_TYPO.items():
        base = re.sub(bad, good, base, flags=re.I)
    # алиасы
    low = base.lower()
    for k, v in aliases.items():
        if low == k.lower():
            return v, []
    return base, []

def suggest_close(value: str, options: List[str], n: int = 3) -> List[str]:
    return difflib.get_close_matches(value, options, n=n, cutoff=0.55)

def load_aliases(path: str) -> Dict[str, str]:
    """Простой YAML-парсер 'ключ: значение' (без зависимостей)."""
    out: Dict[str, str] = {}
    p = pathlib.Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        k, v = line.split(":", 1)
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out
