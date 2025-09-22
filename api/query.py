import json
import sqlite3
from http.server import BaseHTTPRequestHandler
from openai import OpenAI

client = OpenAI()  # uses OPENAI_API_KEY from Vercel Project → Settings → Environment Variables

SYSTEM_PROMPT = """
You are an expert at converting English questions into a SINGLE valid SQLite SELECT query.
Database table: STUDENT
Columns: NAME, CLASS, SECTION, MARKS

Rules:
- Output ONLY the SQL query (no backticks, no prose, no "sql" label).
- Use correct SQLite syntax.
- Only SELECT statements; never modify data.
- If counting, use SELECT COUNT(*).
"""

def get_openai_sql(question: str) -> str:
    resp = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": question},
        ],
    )
    sql = resp.choices[0].message.content.strip()
    if sql.startswith("```"):
        sql = sql.replace("```sql", "").replace("```", "").strip()
    if not sql.lower().startswith("select"):
        raise ValueError("Only SELECT queries are allowed.")
    return sql

def build_inmemory_db():
    conn = sqlite3.connect(":memory:")
    cur = conn.cursor()
    cur.execute("CREATE TABLE STUDENT(NAME VARCHAR(25), CLASS VARCHAR(25), SECTION VARCHAR(25), MARKS INT)")
    rows = [
        ("John","10","A",88), ("Mary","10","B",92), ("Ali","11","A",81), ("Sara","12","C",95),
        ("Omar","10","C",77), ("Lina","11","B",93), ("Rami","12","A",68), ("Jana","10","A",84),
        ("Maher","10","B",76), ("Noor","10","C",90), ("Hadi","11","A",88), ("Maya","11","C",71),
        ("Samir","12","B",95), ("Farah","12","C",80), ("Youssef","11","B",82), ("Nour","12","A",73),
        ("Karim","10","A",91), ("Leila","11","B",86), ("Tarek","12","C",79), ("Dima","10","B",94),
    ]
    cur.executemany("INSERT INTO STUDENT(NAME,CLASS,SECTION,MARKS) VALUES(?,?,?,?)", rows)
    conn.commit()
    return conn

class handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict):
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode("utf-8"))

    def do_POST(self):
        try:
            length = int(self.headers.get("content-length", 0))
            body = self.rfile.read(length) if length else b"{}"
            data = json.loads(body)
            question = (data.get("question") or "").strip()
            if not question:
                return self._send_json(400, {"error": "Missing 'question'."})

            sql = get_openai_sql(question)

            conn = build_inmemory_db()
            cur = conn.cursor()
            cur.execute(sql)
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description] if cur.description else []
            conn.close()

            return self._send_json(200, {"sql": sql, "columns": cols, "rows": rows})
        except Exception as e:
            return self._send_json(400, {"error": str(e)})

    # Optional simple GET
    def do_GET(self):
        return self._send_json(200, {"ok": True})
