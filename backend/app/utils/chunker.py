import re
from ..core.config import settings


def split_by_headers(text: str) -> list[str]:
    """Разбиение по заголовкам Markdown/текстовым"""
    header_pattern = r'\n(?:#{1,6}\s+[^\n]+|(?:[А-ЯA-Z][А-ЯA-Z\s\-]{2,}[А-ЯA-Z])\s*\n)'
    parts = re.split(header_pattern, text)
    return [p.strip() for p in parts if p.strip()]


def split_by_paragraphs(text: str, max_length: int = None) -> list[str]:
    max_length = max_length or settings.CHUNK_SIZE
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    chunks = []
    current_chunk = []
    current_length = 0
    
    for para in paragraphs:
        para_len = len(para)
        
        # Если один параграф больше max_length - принудительно разбиваем
        if para_len > max_length:
            # Сохраняем текущий чанк если есть
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
            
            # Разбиваем длинный параграф на части (можно по предложениям)
            # Здесь упрощенно - просто добавляем как есть
            chunks.append(para)
            current_chunk = []
            current_length = 0
            continue
        
        # Если не влезает - сохраняем чанк и начинаем новый с перекрытием
        if current_length + para_len > max_length and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            
            # Перекрытие: берем последние 1-2 параграфа из ТЕКУЩЕГО чанка
            overlap_size = 2
            overlap = current_chunk[-overlap_size:] if len(current_chunk) >= overlap_size else current_chunk[:]
            
            # Новый чанк начинается с перекрытия + новый параграф
            current_chunk = overlap + [para]
            current_length = sum(len(p) for p in current_chunk)
        else:
            current_chunk.append(para)
            current_length += para_len
    
    # Добавляем последний чанк
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def chunk_document(text: str, chunk_size: int = None, overlap: int = None) -> list[tuple[int, int, str]]:
    """
    Разбиение документа на чанки с позициями.
    Возвращает список (start_pos, end_pos, text)
    """
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP
    
    # Сначала пробуем разбить по заголовкам
    header_chunks = split_by_headers(text)
    
    if len(header_chunks) >= 3:
        # Достаточно заголовков — используем их
        result = []
        pos = 0
        for chunk_text in header_chunks:
            start = text.find(chunk_text, pos)
            end = start + len(chunk_text)
            result.append((start, end, chunk_text))
            pos = end
        return result
    
    # Иначе разбиваем по параграфам
    chunks = split_by_paragraphs(text, chunk_size)
    result = []
    pos = 0
    for chunk_text in chunks:
        start = text.find(chunk_text, pos)
        end = start + len(chunk_text)
        result.append((start, end, chunk_text))
        pos = max(start + 1, end - overlap)  # Перекрытие
    
    return result



