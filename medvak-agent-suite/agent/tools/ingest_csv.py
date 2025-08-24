from __future__ import annotations
import csv, io
from typing import List
from .schema import Record, F_TITLE, F_DEPT, F_ROLE, F_WORKER, F_SCHEDULE, F_SHIFT, F_TIME, F_SALARY, F_CONTACT, F_STATUS, F_REQ

KNOWN = {
    F_TITLE, F_DEPT, F_ROLE, F_WORKER, F_SCHEDULE, F_SHIFT, F_TIME, F_SALARY, F_CONTACT, F_STATUS, F_REQ
}

def parse_csv_text(csv_text: str, delimiter: str = ",") -> List[Record]:
    """
    Принимает текст CSV (включая кириллицу). Возвращает список Record.
    Неизвестные колонки игнорируем (схему не расширяем).
    """
    buf = io.StringIO(csv_text)
    # авто-детект разделителя, если вдруг ; используется
    sniffer = csv.Sniffer()
    sample = csv_text[:1024]
    try:
        dialect = sniffer.sniff(sample)
        delim = dialect.delimiter
    except Exception:
        delim = delimiter

    buf.seek(0)
    reader = csv.DictReader(buf, delimiter=delim)
    out: List[Record] = []
    for row in reader:
        payload = {}
        for k, v in row.items():
            if k is None:
                continue
            key = k.strip()
            if key not in KNOWN:
                continue
            payload[key] = (v or "").strip()
        # Требования → список int
        if F_REQ in payload and payload[F_REQ]:
            req = []
            for t in str(payload[F_REQ]).replace(";", ",").split(","):
                t = t.strip()
                if t.isdigit():
                    req.append(int(t))
            payload[F_REQ] = req or None
        out.append(Record(**payload))
    return out
