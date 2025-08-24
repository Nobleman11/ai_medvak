from __future__ import annotations
import json, pathlib, os
from typing import Dict, List, Any, Tuple
from .schema import Record, PreviewItem, AllowedMap, SINGLE_FIELDS, MULTI_FIELDS
from .normalize import (
    trim, normalize_time_tokens, normalize_schedule, normalize_shift,
    normalize_role, normalize_dept, suggest_close, load_aliases
)

def _load_allowed_map(path: str) -> AllowedMap:
    p = pathlib.Path(path)
    if not p.exists():
        return {"selects": {}, "multiselects": {}}
    data = json.loads(p.read_text(encoding="utf-8"))
    # trim & unique
    for k in ("selects","multiselects"):
        data[k] = {fld: sorted({str(v).strip() for v in vals}) for fld, vals in data.get(k, {}).items()}
    return data  # type: ignore

def _validate_select(field: str, value: str, allowed: Dict[str, List[str]]) -> Tuple[bool, List[str]]:
    opts = allowed.get(field, [])
    if value in opts:
        return True, []
    return False, suggest_close(value, opts, n=3)

def _validate_multi(field: str, values: List[str], allowed: Dict[str, List[str]]) -> Tuple[List[str], List[Dict[str, Any]]]:
    opts = set(allowed.get(field, []))
    valid: List[str] = []
    uncertain: List[Dict[str, Any]] = []
    for v in values:
        if v in opts:
            valid.append(v)
        else:
            uncertain.append({"field": field, "value": v, "suggest": suggest_close(v, list(opts), n=3)})
    return sorted(valid), uncertain

def _confidence(item: PreviewItem) -> float:
    # Простая метрика: 1 - (несоответствий / (1 + число проверяемых полей))
    uncertain = len(item.uncertain)
    denom = 1 + 6  # 6 селект-полей максимум
    conf = max(0.0, 1.0 - uncertain/denom)
    return round(conf, 2)

def preview_records(records: List[Record]) -> List[PreviewItem]:
    allowed_path = os.getenv("AGENT_MAP_PATH", "agent/agent_map/agent-map.json")
    aliases_file = os.getenv("ALIASES_FILE", "shared/aliases.yml")
    allowed = _load_allowed_map(allowed_path)
    aliases = load_aliases(aliases_file)

    items: List[PreviewItem] = []
    for rec in records:
        notes: List[str] = []
        uncertain: List[Dict[str, Any]] = []

        # --- нормализация ---
        # Должность
        if rec.Должность:
            rec.Должность, note_role = normalize_role(rec.Должность)
            notes += note_role

        # Тип_смены
        if rec.Тип_смены:
            norm = set()
            for v in rec.Тип_смены:
                for t in normalize_shift(v):
                    norm.add(t)
            rec.Тип_смены = sorted(norm) or rec.Тип_смены

        # График
        if rec.График:
            acc = set()
            for v in rec.График:
                vs, _ = normalize_schedule(v)
                acc.update(vs)
            rec.График = sorted(acc) or rec.График

        # Время
        if rec.Время_работы:
            acc = set()
            for v in rec.Время_работы:
                times, note = normalize_time_tokens(v)
                notes += note
                acc.update(times)
            rec.Время_работы = sorted(acc) or rec.Время_работы

        # Отделение
        if rec.Отделение:
            rec.Отделение, note_d = normalize_dept(rec.Отделение, aliases)
            notes += note_d

        # --- валидация against allowed ---
        # SINGLE
        for field in {"Должность","Статус","Отделение"}:
            val = getattr(rec, field, None)
            if not val:
                continue
            ok, suggest = _validate_select(field, val, allowed.get("selects", {}))
            if not ok:
                uncertain.append({"field": field, "value": val, "suggest": suggest})

        # MULTI
        for field in {"Работник","График","Тип_смены","Время_работы"}:
            vals = getattr(rec, field, None)
            if not vals:
                continue
            valid, uncs = _validate_multi(field, vals, allowed.get("multiselects", {}))
            setattr(rec, field, valid)
            uncertain += uncs

        item = PreviewItem(record=rec, uncertain=uncertain, notes=notes)
        item.confidence = _confidence(item)
        items.append(item)
    return items
