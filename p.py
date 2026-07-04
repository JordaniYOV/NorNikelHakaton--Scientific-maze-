# test_conn.py — создайте этот файл рядом с проектом
import psycopg2

try:
    conn = psycopg2.connect(
        host="localhost",
        port=5432,
        database="kg_mvp",
        user="postgres",
        password="1234"
    )
    print("OK! Connected.")
    conn.close()
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()