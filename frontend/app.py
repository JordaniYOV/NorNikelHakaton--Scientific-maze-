"""Streamlit UI для Knowledge Graph MVP"""
import streamlit as st
import requests
import json
from datetime import datetime

API_URL = "http://localhost:8000"

st.set_page_config(
    page_title="Knowledge Graph — Горно-металлургические исследования",
    page_icon="🔬",
    layout="wide"
)

st.title("🔬 Knowledge Graph MVP")
st.markdown("Интеллектуальная система поиска и анализа научно-технических данных")

# Sidebar
st.sidebar.header("Навигация")
page = st.sidebar.radio("Раздел", ["Поиск", "Загрузка документов", "Граф знаний", "Статус системы"])

if page == "Поиск":
    st.header("🔍 Интеллектуальный поиск")
    
    query = st.text_area(
        "Введите ваш вопрос",
        placeholder="Например: Сравни методы обессоливания воды при содержании сульфатов 200-300 мг/л",
        height=100
    )
    
    col1, col2, col3 = st.columns(3)
    with col1:
        include_sources = st.checkbox("Показывать источники", value=True)
    with col2:
        include_graph = st.checkbox("Показывать граф", value=True)
    with col3:
        show_reasoning = st.checkbox("Показать рассуждения RLM", value=False)
    
    if st.button("🔍 Найти", type="primary"):
        if not query:
            st.warning("Введите запрос")
        else:
            with st.spinner("RLM анализирует запрос..."):
                try:
                    # Быстрый поиск
                    r_search = requests.post(
                        f"{API_URL}/search/",
                        json={"query": query, "top_k": 10}
                    )
                    
                    # Полный ответ через RLM
                    r_answer = requests.post(
                        f"{API_URL}/search/answer",
                        json={
                            "query": query,
                            "include_sources": include_sources,
                            "include_graph": include_graph
                        }
                    )
                    
                    if r_answer.status_code == 200:
                        data = r_answer.json()
                        
                        # Ответ
                        st.subheader("📋 Ответ")
                        st.markdown(data["answer"])
                        
                        # Источники
                        if include_sources and data.get("sources"):
                            st.subheader("📚 Источники")
                            for i, src in enumerate(data["sources"], 1):
                                with st.expander(f"Источник {i}: {src.get('doc_id', 'unknown')[:8]}..."):
                                    st.text(src.get("text", "Нет текста"))
                                    st.caption(f"Уверенность: {src.get('confidence', 0):.2f}")
                        
                        # Пробелы
                        if data.get("gaps"):
                            st.subheader("⚠️ Выявленные пробелы")
                            for gap in data["gaps"]:
                                st.warning(gap)
                        
                        # Граф
                        if include_graph and data.get("graph"):
                            st.subheader("🕸️ Связанные сущности")
                            graph = data["graph"]
                            
                            # Статистика графа
                            st.caption(f"Узлов: {len(graph.get('nodes', []))}, связей: {len(graph.get('edges', []))}")
                            
                            # Таблица узлов
                            if graph.get("nodes"):
                                nodes_df = [{"Имя": n["name"], "Тип": n["type"]} 
                                          for n in graph["nodes"][:20]]
                                st.dataframe(nodes_df, use_container_width=True)
                        
                        # Рассуждения RLM
                        if show_reasoning:
                            st.subheader("🧠 Рассуждения RLM")
                            r_reasoning = requests.post(
                                f"{API_URL}/search/reasoning",
                                json={"query": query, "include_graph": False}
                            )
                            if r_reasoning.status_code == 200:
                                reasoning_data = r_reasoning.json()
                                st.text(reasoning_data.get("reasoning_trace", "Нет данных"))
                                st.caption(f"Подзадач выполнено: {reasoning_data.get('subtasks_executed', 0)}")
                                st.caption(f"Уверенность: {reasoning_data.get('confidence', 0):.2f}")
                    
                    else:
                        st.error(f"Ошибка: {r_answer.status_code}")
                        
                except Exception as e:
                    st.error(f"Ошибка соединения: {str(e)}")

elif page == "Загрузка документов":
    st.header("📤 Загрузка документов")
    
    uploaded_files = st.file_uploader(
        "Выберите файлы",
        type=["txt", "md", "pdf", "json"],
        accept_multiple_files=True
    )
    
    if uploaded_files:
        for file in uploaded_files:
            col1, col2 = st.columns([3, 1])
            with col1:
                st.write(f"📄 {file.name} ({file.size} bytes)")
            with col2:
                if st.button(f"Загрузить {file.name}", key=file.name):
                    with st.spinner("Загрузка..."):
                        files = {"file": (file.name, file.getvalue(), "text/plain")}
                        r = requests.post(f"{API_URL}/documents/upload", files=files)
                        if r.status_code == 200:
                            data = r.json()
                            st.success(f"Загружено! ID: {data['doc_id']}")
                            st.info(f"Статус: {data['status']}")
                        else:
                            st.error(f"Ошибка: {r.status_code}")
    
    # Список документов
    st.subheader("📋 Загруженные документы")
    try:
        r = requests.get(f"{API_URL}/documents/")
        if r.status_code == 200:
            docs = r.json()
            if docs.get("items"):
                for doc in docs["items"]:
                    col1, col2, col3 = st.columns([3, 1, 1])
                    with col1:
                        st.write(f"📄 {doc['filename']}")
                    with col2:
                        status_color = {
                            "ready": "🟢",
                            "error": "🔴",
                            "uploaded": "⚪",
                            "parsing": "🟡",
                            "indexing": "🔵"
                        }.get(doc["status"], "⚪")
                        st.write(f"{status_color} {doc['status']}")
                    with col3:
                        if st.button("Удалить", key=f"del_{doc['id']}"):
                            r_del = requests.delete(f"{API_URL}/documents/{doc['id']}")
                            if r_del.status_code == 200:
                                st.success("Удалено")
                                st.rerun()
            else:
                st.info("Нет загруженных документов")
    except Exception as e:
        st.error(f"Ошибка получения списка: {str(e)}")

elif page == "Граф знаний":
    st.header("🕸️ Граф знаний")
    
    search_entity = st.text_input("Поиск сущности", placeholder="Например: никель, электроэкстракция")
    
    if search_entity:
        try:
            r = requests.get(f"{API_URL}/graph/search?q={search_entity}")
            if r.status_code == 200:
                entities = r.json()
                if entities:
                    st.subheader(f"Найдено {len(entities)} сущностей")
                    for ent in entities:
                        col1, col2 = st.columns([2, 1])
                        with col1:
                            st.write(f"**{ent['name']}** ({ent['type']})")
                        with col2:
                            if st.button("Показать связи", key=f"graph_{ent['id']}"):
                                r_graph = requests.get(
                                    f"{API_URL}/graph/entity/{ent['name']}?depth=2"
                                )
                                if r_graph.status_code == 200:
                                    graph_data = r_graph.json()
                                    
                                    # Визуализация
                                    nodes = graph_data.get("nodes", [])
                                    edges = graph_data.get("edges", [])
                                    
                                    st.write(f"Узлов: {len(nodes)}, связей: {len(edges)}")
                                    
                                    # Таблица связей
                                    if edges:
                                        edges_df = [{
                                            "От": e["source"],
                                            "Связь": e["type"],
                                            "К": e["target"]
                                        } for e in edges[:50]]
                                        st.dataframe(edges_df, use_container_width=True)
                else:
                    st.info("Сущности не найдены")
        except Exception as e:
            st.error(f"Ошибка: {str(e)}")
    
    # Cypher запрос
    st.subheader("🔍 Cypher запрос (только чтение)")
    cypher_query = st.text_area(
        "Введите Cypher запрос",
        placeholder="MATCH (e:Entity) WHERE e.type = 'Material' RETURN e LIMIT 10"
    )
    if st.button("Выполнить"):
        try:
            r = requests.post(
                f"{API_URL}/graph/subgraph",
                json={"cypher": cypher_query, "parameters": {}}
            )
            if r.status_code == 200:
                result = r.json()
                st.write(f"Узлов: {len(result.get('nodes', []))}")
                st.json(result)
            else:
                st.error(f"Ошибка: {r.status_code}")
        except Exception as e:
            st.error(f"Ошибка: {str(e)}")

elif page == "Статус системы":
    st.header("📊 Статус системы")
    
    try:
        r = requests.get(f"{API_URL}/health")
        if r.status_code == 200:
            data = r.json()
            
            st.subheader("Общий статус")
            status_color = "🟢" if data["status"] == "healthy" else "🟡"
            st.write(f"{status_color} {data['status']}")
            
            st.subheader("Компоненты")
            for component, status in data.get("checks", {}).items():
                if status == "ok":
                    st.success(f"✅ {component}")
                else:
                    st.error(f"❌ {component}: {status}")
        else:
            st.error("API недоступен")
    except Exception as e:
        st.error(f"Ошибка соединения: {str(e)}")