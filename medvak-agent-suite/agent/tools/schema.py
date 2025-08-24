from __future__ import annotations
from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel, Field, validator

# Поля нашей схемы (ровно как в NocoDB)
F_TITLE = "Title"
F_DEPT = "Отделение"
F_ROLE = "Должность"
F_WORKER = "Работник"            # Multi
F_SCHEDULE = "График"            # Multi
F_SHIFT = "Тип_смены"            # Multi
F_TIME = "Время_работы"          # Multi
F_SALARY = "Зарплата"
F_CONTACT = "Контактное_лицо"
F_STATUS = "Статус"
F_REQ = "Требования"             # relation (ids)

SINGLE_FIELDS = {F_DEPT, F_ROLE, F_STATUS}
MULTI_FIELDS = {F_WORKER, F_SCHEDULE, F_SHIFT, F_TIME}

ALL_FIELDS = [
    F_TITLE, F_DEPT, F_ROLE, F_WORKER, F_SCHEDULE, F_SHIFT, F_TIME,
    F_SALARY, F_CONTACT, F_STATUS, F_REQ
]

class Record(BaseModel):
    Title: Optional[str] = None
    Отделение: Optional[str] = None
    Должность: Optional[str] = None
    Работник: Optional[List[str]] = None
    График: Optional[List[str]] = None
    Тип_смены: Optional[List[str]] = None
    Время_работы: Optional[List[str]] = None
    Зарплата: Optional[str] = None
    Контактное_лицо: Optional[str] = None
    Статус: Optional[str] = None
    Требования: Optional[List[int]] = None

    @validator(F_WORKER, F_SCHEDULE, F_SHIFT, F_TIME, pre=True)
    def _ensure_list(cls, v):
        if v is None:
            return None
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            # Разделители: запятая / точка с запятой / пробел
            parts = [p.strip() for p in v.replace(";", ",").split(",") if p.strip()]
            return parts or [v.strip()]
        return [str(v)]

class Uncertain(TypedDict):
    field: str
    value: str
    suggest: List[str]

class PreviewItem(BaseModel):
    record: Record
    uncertain: List[Uncertain] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)
    confidence: float = 0.0

AllowedMap = Dict[str, Dict[str, List[str]]]   # {"selects": {...}, "multiselects": {...}}
