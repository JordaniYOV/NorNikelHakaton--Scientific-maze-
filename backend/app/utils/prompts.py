"""Промпты для LLM"""

ENTITY_EXTRACTION_PROMPT = '''Ты — эксперт по горно-металлургическим исследованиям. Извлеки из текста все значимые сущности.

Типы сущностей:
- Material: материалы, вещества, химические соединения, сплавы, руды, шлаки, штейны
- Process: технологические процессы, методы, операции
- Equipment: оборудование, установки, аппараты
- Property: измеряемые свойства, характеристики
- Parameter: числовые параметры процесса с единицами измерения
- Condition: условия, ограничения, факторы среды
- Expert: люди, авторы, исследователи
- Organization: организации, лаборатории, университеты
- Publication: названия статей, отчётов, патентов

ВАЖНО:
1. Извлекай ТОЛЬКО явно упомянутые сущности
2. Для каждой сущности укажи точную цитату
3. Нормализуй названия
4. Для числовых параметров ОБЯЗАТЕЛЬНО указывай единицы
5. Не придумывай сущности

Текст:
{text}

Ответ в формате JSON:
{{
  "entities": [
    {{
      "name": "точное название из текста",
      "canonical_name": "нормализованное название",
      "type": "Material|Process|Equipment|Property|Parameter|Condition|Expert|Organization|Publication",
      "context": "цитата из текста"
    }}
  ]
}}
'''


RELATION_EXTRACTION_PROMPT = '''Ты — эксперт по горно-металлургическим исследованиям. Извлеки связи между сущностями из текста.

Типы связей:
- USES: процесс использует материал/оборудование
- PRODUCES: процесс/оборудование производит результат/материал
- OPERATES_AT: процесс/оборудование работает при условии/параметре
- MEASURES: эксперимент/процесс измеряет свойство
- DESCRIBED_IN: факт/метод описан в публикации
- PERFORMED_BY: эксперимент выполнен экспертом/организацией
- HAS_PROPERTY: материал обладает свойством
- APPLIES_TO: метод/процесс применяется к материалу
- LOCATED_AT: объект/процесс связан с местоположением
- RESULTED_IN: эксперимент привёл к результату

ВАЖНО:
1. Связи ТОЛЬКО между явно упомянутыми сущностями
2. Каждая связь подтверждена цитатой
3. Не создавай косвенные связи
4. Указывай уверенность: 1.0 — прямая, 0.7 — подразумеваемая, 0.5 — косвенная

Текст:
{text}

Известные сущности:
{entities_list}

Ответ в формате JSON:
{{
  "relations": [
    {{
      "source": "имя сущности-источника",
      "target": "имя сущности-цели",
      "relation_type": "USES|PRODUCES|OPERATES_AT|MEASURES|DESCRIBED_IN|PERFORMED_BY|HAS_PROPERTY|APPLIES_TO|LOCATED_AT|RESULTED_IN",
      "context": "цитата",
      "confidence": 0.9
    }}
  ]
}}
'''


QUERY_ANALYSIS_PROMPT = '''Проанализируй запрос пользователя и определи его структуру.

Запрос: {query}

Определи:
1. Тип запроса: factual, comparative, review, gap_analysis, navigational
2. Основные сущности
3. Числовые ограничения (диапазоны, пороги)
4. Условия (география, климат, временной период)
5. Намерение пользователя

Ответ в формате JSON:
{{
  "query_type": "factual|comparative|review|gap_analysis|navigational",
  "entities": [
    {{"name": "...", "type": "Material|Process|Equipment|Property|Condition"}}
  ],
  "numeric_constraints": [
    {{"parameter": "...", "operator": ">|<|>=|<=|=|range", "value": "...", "unit": "..."}}
  ],
  "conditions": [
    {{"type": "geography|climate|time|other", "value": "..."}}
  ],
  "intent": "описание намерения",
  "search_strategy": "описание стратегии"
}}
'''


ANSWER_SYNTHESIS_PROMPT = '''Ты — эксперт-аналитик. На основе найденных фактов подготовь структурированный ответ.

Запрос: "{query}"

Найденные факты:
{facts}

Инструкции:
1. Ответь чётко и структурированно
2. Используй ТОЛЬКО предоставленные факты
3. Укажи противоречия явно
4. При недостатке информации скажи честно
5. Каждое утверждение с источником
6. Выдели консенсус и разногласия
7. Укажи пробелы в данных

Формат:
## Краткий ответ
...

## Детализация
### [Тема 1]
- ...
- Источник: [документ, цитата]

### [Тема 2]
...

## Сравнительная таблица
| Параметр | Вариант 1 | Вариант 2 |
|----------|-----------|-----------|
| ...      | ...       | ...       |

## Выявленные пробелы
- ...

## Степень уверенности
- Высокая: ...
- Средняя: ...
- Требует подтверждения: ...
'''

# from dataclasses import dataclass
# from typing import Any
# from enum import Enum


# class PromptType(str, Enum):
#     ENTITY_EXTRACTION_PROMPT = "entity_extraction_prompt"
#     RELATION_EXTRACTION_PROMPT = "relation_extraction_prompt"
#     QUERY_ANALYSIS_PROMPT = "query_analysis_prompt"
#     ANSWER_SYNTHESIS_PROMPT = "answer_synthesis_prompt"

# @dataclass
# class PromptTemplate:
#     type: PromptType
#     template: str
#     required_vars: list[str]
#     # system_role: str 
#     temperature: float = 0.1
#     max_tokens: int = 2000
#     json_mode: bool = True


# class PromptFactory:
#     """
#     Фабрика для генерации промптов на основе типа.
#     Все промпты хранятся в едином реестре.
#     """
    
#     _templates: dict[PromptType, PromptTemplate] = {}
    
#     @classmethod
#     def register(cls, template: PromptTemplate) -> None:
#         """Зарегистрировать шаблон промпта"""
#         cls._templates[template.type] = template
    
#     @classmethod
#     def get_prompt(cls, prompt_type: PromptType, **kwargs) -> str:
#         """
#         Получить сгенерированный промпт с подставленными переменными.
        
#         Args:
#             prompt_type: Тип промпта
#             **kwargs: Переменные для подстановки
        
#         Returns:
#             Сгенерированный промпт
            
#         Raises:
#             ValueError: Если шаблон не зарегистрирован или не хватает переменных
#         """
#         template = cls._templates.get(prompt_type)
#         if not template:
#             raise ValueError(f"Промпт '{prompt_type.value}' не зарегистрирован")
        
#         # Проверяем, что все необходимые переменные переданы
#         missing_vars = set(template.required_vars) - set(kwargs.keys())
#         if missing_vars:
#             raise ValueError(
#                 f"Не хватает переменных для '{prompt_type.value}': {missing_vars}"
#             )
        
#         # Подставляем переменные
#         try:
#             return template.template.format(**kwargs)
#         except KeyError as e:
#             raise ValueError(f"Ошибка подстановки переменной: {e}")
        
#     @classmethod
#     def get_config(cls, prompt_type: PromptType) -> dict[str, Any]:
#         """Получить конфиг (температура, max_tokens, json_mode)"""
#         template = cls._templates.get(prompt_type)
#         if not template:
#             raise ValueError(f"Промпт '{prompt_type.value}' не зарегистрирован")
#         return {
#             "temperature": template.temperature,
#             "max_tokens": template.max_tokens,
#             "json_mode": template.json_mode
#         }
    
# def register_all_prompts():
#     """Регистрация всех шаблонов промптов"""

# class PromptManager:
#     """
#     Менеджер промптов с удобным интерфейсом.
#     """
    
#     def __init__(self):
#         # Убеждаемся, что все промпты зарегистрированы
#         register_all_prompts()
    
#     def get(self, prompt_type: PromptType, **kwargs) -> str:
#         """Получить промпт"""
#         return PromptFactory.get_prompt(prompt_type, **kwargs)
    
#     def get_config(self, prompt_type: PromptType) -> dict[str, Any]:
#         """Получить конфиг для промпта"""
#         return PromptFactory.get_config(prompt_type)
  
#     def get_with_config(self, prompt_type: PromptType, **kwargs) -> Dict[str, Any]:
#         """
#         Получить промпт + конфиг в одном словаре.
#         Удобно для передачи в LLM клиент.
#         """
#         return {
#             "user_prompt": self.get(prompt_type, **kwargs),
#             **self.get_config(prompt_type)
#         }