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
    
    def _split_long_text(text: str, max_len: int) -> list[str]:
        """Жёсткая нарезка длинного текста"""
        result = []
        # Сначала по предложениям
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
        temp = []
        temp_len = 0
        
        for sent in sentences:
            if len(sent) > max_len:
                # Предложение длиннее лимита — режем по словам
                if temp:
                    result.append(' '.join(temp))
                    temp = []
                    temp_len = 0
                
                words = sent.split()
                part = []
                part_len = 0
                for word in words:
                    if part_len + len(word) > max_len and part:
                        result.append(' '.join(part))
                        part = [word]
                        part_len = len(word)
                    else:
                        part.append(word)
                        part_len += len(word) + 1
                if part:
                    result.append(' '.join(part))
            elif temp_len + len(sent) > max_len and temp:
                result.append(' '.join(temp))
                temp = [sent]
                temp_len = len(sent)
            else:
                temp.append(sent)
                temp_len += len(sent) + 1
        
        if temp:
            result.append(' '.join(temp))
        
        return result
    
    for para in paragraphs:
        para_len = len(para)
        
        if para_len > max_length:
            # Сохраняем текущий чанк
            if current_chunk:
                chunks.append('\n\n'.join(current_chunk))
                current_chunk = []
                current_length = 0
            
            # Режем длинный параграф
            sub_chunks = _split_long_text(para, max_length)
            chunks.extend(sub_chunks)
            continue
        
        if current_length + para_len > max_length and current_chunk:
            chunks.append('\n\n'.join(current_chunk))
            # Перекрытие
            overlap = current_chunk[-2:] if len(current_chunk) >= 2 else current_chunk[:]
            current_chunk = overlap + [para]
            current_length = sum(len(p) for p in current_chunk)
        else:
            current_chunk.append(para)
            current_length += para_len
    
    if current_chunk:
        chunks.append('\n\n'.join(current_chunk))
    
    return chunks


def chunk_document(text: str, chunk_size: int = None, overlap: int = None) -> list[tuple[int, int, str]]:
    chunk_size = chunk_size or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP
    
    if len(text) <= chunk_size:
        return [(0, len(text), text)]
    
    # Пробуем по заголовкам
    header_chunks = split_by_headers(text)
    
    if len(header_chunks) >= 3:
        result = []
        pos = 0
        for chunk_text in header_chunks:
            # Проверяем, что заголовочный чанк не слишком длинный
            if len(chunk_text) > chunk_size:
                sub_chunks = split_by_paragraphs(chunk_text, chunk_size)
                for sub in sub_chunks:
                    start = text.find(sub, pos)
                    end = start + len(sub)
                    result.append((start, end, sub))
                    pos = end
            else:
                start = text.find(chunk_text, pos)
                end = start + len(chunk_text)
                result.append((start, end, chunk_text))
                pos = end
        return result
    
    # По параграфам
    chunks = split_by_paragraphs(text, chunk_size)
    result = []
    pos = 0
    for chunk_text in chunks:
        start = text.find(chunk_text, pos)
        end = start + len(chunk_text)
        result.append((start, end, chunk_text))
        pos = end
    
    # === ФИНАЛЬНАЯ ПРОВЕРКА ===
    for i, (s, e, t) in enumerate(result):
        if len(t) > chunk_size * 1.5:  # допуск 50%
            print(f"⚠️ Чанк {i} всё ещё слишком длинный: {len(t)} символов")
    
    return result