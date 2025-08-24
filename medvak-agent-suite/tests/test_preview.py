import sys, pathlib, json, os
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT / "agent"))

from tools.schema import Record
from tools.preview import preview_records

def test_preview_with_allowed_map(tmp_path):
    # Готовим временный agent-map с разрешёнными значениями
    allowed = {
        "selects": {
            "Должность": ["Процедурная медицинская сестра", "Палатная медицинская сестра", "Операционная медицинская сестра"],
            "Статус": ["Открыта", "Закрыта"],
            "Отделение": ["Операционный блок", "Дневной стационар детской онкологии и гематологии"]
        },
        "multiselects": {
            "Время_работы": ["08:00 - 17:00", "08:00 - 20:00", "17:00 - 08:00", "08:00 - 08:00"],
            "Работник": ["Студент УГМУ","Студент СОМК","Основной сотрудник","Студент УРГУПС"],
            "Тип_смены": ["Суточные смены","Дневные смены","Вечерние смены"],
            "График": ["5/2","1/3","2/2","Смешанный"]
        }
    }
    amap = tmp_path / "agent-map.json"
    amap.write_text(json.dumps(allowed, ensure_ascii=False), encoding="utf-8")
    os.environ["AGENT_MAP_PATH"] = str(amap)  # подсовываем наш map

    rec = Record(
        Title="Процедурная медсестра",
        Должность="процедурная медсестра",
        Отделение="Дневной стационар онкологического и гематологического центра",
        График=["2/2 (возможны 1/3)"],
        Тип_смены=["дневная 12-часовая"],
        Время_работы=["12 часов (8:00-20:00)"],
        Статус="Открыта"
    )

    items = preview_records([rec])
    it = items[0]
    # После нормализации часть полей должна попасть в allowed
    assert "Дневные смены" in (it.record.Тип_смены or [])
    assert "2/2" in (it.record.График or [])
    assert "08:00 - 20:00" in (it.record.Время_работы or [])
    # Отделение слегка «не канон» — ожидаем подсказки
    assert any(u["field"] == "Отделение" for u in it.uncertain)
