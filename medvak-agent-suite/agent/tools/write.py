from __future__ import annotations
from typing import Dict, Any, List
import logging, os
from .schema import Record
from .preview import preview_records
from .nocodb_client import from_env as nococlient_from_env

log = logging.getLogger("write")

def write_records(records: List[Record], table_id: str, rel_name: str | None = None) -> List[Dict[str, Any]]:
    """
    Пишем подтверждённые записи в таблицу NocoDB.
    Возвращаем список результатов: {"id": ..., "status": "ok"|"skip", "reason": "..."}
    """
    client = nococlient_from_env("VAC")
    results: List[Dict[str, Any]] = []
    try:
        for rec in records:
            # safety: ещё раз быстро проверим превью (должно быть без uncertain)
            prev = preview_records([rec])[0]
            if prev.uncertain:
                results.append({"status": "skip", "reason": "uncertain_fields", "record": rec.dict()})
                continue

            payload = {k: v for k, v in rec.dict(exclude_none=True).items() if k != "Требования"}
            res = client.create_record(table_id, payload)
            new_id = res.get("Id") or res.get("id") or res.get("ID")  # NocoDB может называть по-разному
            # линковка требований
            if new_id and rel_name and rec.Требования:
                client.link_requirements(table_id, rel_name, new_id, rec.Требования)
            results.append({"status": "ok", "id": new_id})
    finally:
        client.close()
    return results
