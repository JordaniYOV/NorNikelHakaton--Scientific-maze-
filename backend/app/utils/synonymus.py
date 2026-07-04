from backend.app.core.schemas import EntityType


SYNONYMS: dict[str, dict[str, list[str]]] = {
    "Material": {
        "никель": ["nickel", "ni", "Ni"],
        "медь": ["copper", "cu", "Cu"],
        "титан": ["titanium", "ti", "Ti"],
        "алюминий": ["aluminum", "aluminium", "al", "Al"],
        "железо": ["iron", "fe", "Fe"],
        "золото": ["gold", "au", "Au"],
        "серебро": ["silver", "ag", "Ag"],
        "платиновые металлы": ["платиноиды", "МПГ", "platinum group metals", "pgm"],
        "сульфат натрия": ["сульфат натрия", "sodium sulfate", "Na2SO4"],
        "сульфат кальция": ["гипс", "техногенный гипс", "calcium sulfate", "CaSO4"],
        "Ti-6Al-4V": ["ti-6al-4v", "титановый сплав Ti-6Al-4V", "титановый сплав ВТ6"],
    },
    "Process": {
        "электроэкстракция": ["electrowinning", "электровыигрывание", "электролиз", "электроосаждение"],
        "кучное выщелачивание": ["heap leaching", "кучное вскрытие", "выщелачивание в кучах"],
        "плавка": ["smelting", "плавление", "выплавка"],
        "обессоливание": ["desalination", "умягчение", "очистка от солей", "обезжелезивание"],
        "флотация": ["flotation", "пенная сепарация"],
        "электролиз": ["electrolysis", "электролитическое рафинирование"],
        "гидрометаллургия": ["hydrometallurgy", "гидрометаллургический процесс"],
        "пирометаллургия": ["pyrometallurgy", "пирометаллургический процесс"],
    },
    "Equipment": {
        "печь взвешенной плавки": ["ПВП", "fluidized bed furnace", "печь взвешенной слой", "печь Кипящего слоя"],
        "ванна электроэкстракции": ["электролизная ванна", "электролитическая ванна", "electrowinning cell"],
        "диафрагменная ячейка": ["диафрагменная камера", "diaphragm cell"],
        "система очистки газов": ["газоочистка", "gas cleaning system", "дымоочистка"],
    },
    "Property": {
        "микротвёрдость": ["microhardness", "твёрдость по Виккерсу", "hv"],
        "усталостная прочность": ["fatigue strength", "предел усталости", "выносливость"],
        "проводимость": ["conductivity", "электропроводность", "удельная проводимость"],
        "сухой остаток": ["dry residue", "общая минерализация", "солесодержание"],
        "извлечение металла": ["metal recovery", "выход металла", "степень извлечения"],
    },
    "Condition": {
        "холодный климат": ["низкие температуры", "северные условия", "арктический климат", "cold climate"],
        "атмосфера аргона": ["argon atmosphere", "защитная атмосфера Ar", "инертная атмосфера"],
    },
}


def normalize_entity(name: str, entity_type: str | None = None) -> str:
    """Нормализация названия сущности по словарю синонимов"""
    name_lower = name.lower().strip()
    
    types_to_search = [entity_type] if entity_type else list(SYNONYMS.keys())
    
    for etype in types_to_search:
        if etype not in SYNONYMS:
            continue
        for canonical, synonyms_list in SYNONYMS[etype].items():
            if name_lower == canonical.lower():
                return canonical
            for syn in synonyms_list:
                if name_lower == syn.lower():
                    return canonical
                
    return EntityType.UNKNOWN


def get_synonyms(canonical_name: str, entity_type: str) -> list[str]:
    """Получить список синонимов для канонического названия"""
    if entity_type in SYNONYMS and canonical_name in SYNONYMS[entity_type]:
        return SYNONYMS[entity_type][canonical_name]
    return []


def add_synonym(canonical_name: str, entity_type: str, synonym: str):
    """Добавить синоним в словарь"""
    if entity_type not in SYNONYMS:
        SYNONYMS[entity_type] = {}
    if canonical_name not in SYNONYMS[entity_type]:
        SYNONYMS[entity_type][canonical_name] = []
    if synonym not in SYNONYMS[entity_type][canonical_name]:
        SYNONYMS[entity_type][canonical_name].append(synonym)