from __future__ import annotations
from typing import List
from .nocodb_client import from_env as nococlient_from_env

def link_requirements(table_id: str, rel_name: str, row_id: int, requirement_ids: List[int]) -> bool:
    client = nococlient_from_env("VAC")
    try:
        return client.link_requirements(table_id, rel_name, row_id, requirement_ids)
    finally:
        client.close()
