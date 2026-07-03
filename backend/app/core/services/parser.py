import os
import uuid
from pathlib import Path
import pdfplumber
from app.core.config import settings


class ParserService:
    """Парсинг различных форматов документов"""
    
    SUPPORTED_TYPES = {'.txt', '.md', '.json', '.pdf'}
    
    @classmethod
    def parse_file(cls, file_path: str) -> str:
        """Определить тип файла и распарсить"""
        ext = Path(file_path).suffix.lower()
        
        if ext not in cls.SUPPORTED_TYPES:
            raise ValueError(f"Неподдерживаемый формат: {ext}")
        
        if ext == '.pdf':
            return cls._parse_pdf(file_path)
        elif ext in {'.txt', '.md'}:
            return cls._parse_text(file_path)
        elif ext == '.json':
            return cls._parse_json(file_path)
        
        return ""
    
    @staticmethod
    def _parse_pdf(file_path: str) -> str:
        """Извлечение текста из PDF"""
        text_parts = []
        try:
            with pdfplumber.open(file_path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text_parts.append(page_text)
        except Exception as e:
            raise ValueError(f"Ошибка парсинга PDF: {str(e)}")
        
        return "\\n\\n".join(text_parts)
    
    @staticmethod
    def _parse_text(file_path: str) -> str:
        """Чтение текстового файла"""
        encodings = ['utf-8', 'cp1251', 'latin-1']
        for encoding in encodings:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    return f.read()
            except UnicodeDecodeError:
                continue
        raise ValueError("Не удалось определить кодировку файла")
    
    @staticmethod
    def _parse_json(file_path: str) -> str:
        """Извлечение текста из JSON (предполагаем поле 'text' или 'content')"""
        import json
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        if isinstance(data, str):
            return data
        elif isinstance(data, dict):
            # Ищем поля с текстом
            for key in ['text', 'content', 'body', 'description', 'abstract']:
                if key in data and isinstance(data[key], str):
                    return data[key]
            # Если не нашли — сериализуем весь JSON
            return json.dumps(data, ensure_ascii=False, indent=2)
        elif isinstance(data, list):
            texts = []
            for item in data:
                if isinstance(item, dict):
                    for key in ['text', 'content', 'body']:
                        if key in item and isinstance(item[key], str):
                            texts.append(item[key])
                            break
            return "\\n\\n".join(texts)
        
        return str(data)
    
    @classmethod
    def save_upload(cls, file_content: bytes, original_filename: str) -> str:
        """Сохранить загруженный файл и вернуть путь"""
        os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
        
        # Генерируем уникальное имя
        file_id = str(uuid.uuid4())
        ext = Path(original_filename).suffix
        safe_filename = f"{file_id}{ext}"
        file_path = os.path.join(settings.UPLOAD_DIR, safe_filename)
        
        with open(file_path, 'wb') as f:
            f.write(file_content)
        
        return file_path