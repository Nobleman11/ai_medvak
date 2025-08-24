from __future__ import annotations
import os, httpx, logging
from typing import Any, Dict, List, Optional

log = logging.getLogger("nocodb")

class NocoClient:
    def __init__(self, base: str, token: str, timeout: float = 20.0,
                 max_conn: int = 4, max_keepalive: int = 2):
        limits = httpx.Limits(max_connections=max_conn, max_keepalive_connections=max_keepalive)
        self._client = httpx.Client(base_url=base.rstrip("/"), timeout=timeout, limits=limits)
        self._hdr = {"xc-token": token}

    def close(self):
        self._client.close()

    # ----- metadata -----
    def columns(self, table_id: str) -> List[Dict[str, Any]]:
        r = self._client.get(f"/tables/{table_id}/columns", headers=self._hdr)
        r.raise_for_status()
        return r.json()

    # ----- records -----
    def list_records(self, table_id: str, limit: int = 50, offset: int = 0) -> Any:
        r = self._client.get(f"/tables/{table_id}/records", headers=self._hdr,
                             params={"limit": limit, "offset": offset})
        r.raise_for_status()
        return r.json()

    def create_record(self, table_id: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._client.post(f"/tables/{table_id}/records", headers=self._hdr, json=payload)
        if r.status_code >= 400:
            log.error("NocoDB create error %s: %s", r.status_code, r.text)
        r.raise_for_status()
        return r.json()

    def patch_record(self, table_id: str, row_id: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
        r = self._client.patch(f"/tables/{table_id}/records/{row_id}", headers=self._hdr, json=payload)
        if r.status_code >= 400:
            log.error("NocoDB patch error %s: %s", r.status_code, r.text)
        r.raise_for_status()
        return r.json()

    # ----- links -----
    def link_requirements(self, table_id: str, rel_name: str, row_id: Any, req_ids: List[int]) -> bool:
        """
        Пробуем самые распространённые варианты API линковки.
        1) PATCH записью поля-связи (Noco умеет, если связь M2M названа колонкой)
        2) POST в /records/{id}/links/{relation} (некоторые версии v2)
        Возвращаем True, если один из способов прошёл 2xx.
        """
        # 1) PATCH через поле-связь
        try:
            payload = {rel_name: [{"id": rid} for rid in req_ids]}
            r = self._client.patch(f"/tables/{table_id}/records/{row_id}", headers=self._hdr, json=payload)
            if r.status_code // 100 == 2:
                return True
            log.warning("Link via PATCH failed %s: %s", r.status_code, r.text)
        except Exception as e:
            log.warning("Link via PATCH exception: %s", e)

        # 2) Через отдельный endpoint ссылок (если включён)
        try:
            r = self._client.post(
                f"/tables/{table_id}/records/{row_id}/links/{rel_name}",
                headers=self._hdr, json={"add": req_ids}
            )
            if r.status_code // 100 == 2:
                return True
            log.warning("Link via /links failed %s: %s", r.status_code, r.text)
        except Exception as e:
            log.warning("Link via /links exception: %s", e)
        return False


def from_env(kind: str = "VAC") -> NocoClient:
    base = os.getenv("NOCODB_BASE", "").rstrip("/")
    token = os.getenv("NOCODB_TOKEN_VAC" if kind == "VAC" else "NOCODB_TOKEN_STAT", "")
    max_conn = int(os.getenv("HTTPX_MAX_CONN", "4"))
    max_keep = int(os.getenv("HTTPX_MAX_KEEPALIVE", "2"))
    timeout = float(os.getenv("REQUEST_TIMEOUT_SEC", "20"))
    return NocoClient(base=base, token=token, timeout=timeout, max_conn=max_conn, max_keepalive=max_keep)
