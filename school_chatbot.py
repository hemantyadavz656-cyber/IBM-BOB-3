# -*- coding: utf-8 -*-
"""
School Chatbot - Multilingual (English / Hindi / Hinglish)
Supports: timetable, assignments, marks queries
Role-based access: Student (own data only) | Parent (up to 2 children)
"""

import os
import sys

# Force UTF-8 output so Hindi/emoji print correctly on Windows
if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr.encoding and sys.stderr.encoding.lower() != "utf-8":
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

import sqlite3
import csv
import re
from datetime import datetime

# ─────────────────────────────────────────────
# 1. DATABASE SETUP
# ─────────────────────────────────────────────

DB_PATH = "school_chatbot.db"


def init_db():
    """Create normalized schema and load data from CSV."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            student_id   INTEGER PRIMARY KEY,
            student_name TEXT NOT NULL,
            class        INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parents (
            parent_id   INTEGER PRIMARY KEY,
            parent_name TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS parent_student (
            parent_id  INTEGER REFERENCES parents(parent_id),
            student_id INTEGER REFERENCES students(student_id),
            PRIMARY KEY (parent_id, student_id)
        );

        CREATE TABLE IF NOT EXISTS marks (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER REFERENCES students(student_id),
            subject    TEXT NOT NULL,
            marks      INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS timetable (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            class      INTEGER NOT NULL,
            day        TEXT NOT NULL,
            subject    TEXT NOT NULL,
            time       TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS assignments (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            class      INTEGER NOT NULL,
            subject    TEXT NOT NULL,
            due_date   TEXT NOT NULL,
            task       TEXT NOT NULL
        );
    """)

    # Load CSV only if tables are empty
    cur.execute("SELECT COUNT(*) FROM students")
    if cur.fetchone()[0] > 0:
        conn.close()
        return

    csv_file = "school_chatbot_dataset.csv"
    if not os.path.exists(csv_file):
        conn.close()
        return

    students_seen  = set()
    parents_seen   = set()
    ps_seen        = set()
    marks_seen     = set()
    timetable_seen = set()
    assignments_seen = set()

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            sid   = int(row["student_id"])
            sname = row["student_name"].strip()
            cls   = int(row["class"])

            if sid not in students_seen:
                cur.execute("INSERT OR IGNORE INTO students VALUES (?,?,?)", (sid, sname, cls))
                students_seen.add(sid)

            pid_raw = row["parent_id"].strip()
            if pid_raw:
                pid   = int(float(pid_raw))
                pname = row["parent_name"].strip()
                if pid not in parents_seen:
                    cur.execute("INSERT OR IGNORE INTO parents VALUES (?,?)", (pid, pname))
                    parents_seen.add(pid)
                if (pid, sid) not in ps_seen:
                    cur.execute("INSERT OR IGNORE INTO parent_student VALUES (?,?)", (pid, sid))
                    ps_seen.add((pid, sid))

            # marks — deduplicate (student_id, subject)
            msubj  = row["marks_subject"].strip()
            mmarks = int(row["marks"])
            mk_key = (sid, msubj)
            if mk_key not in marks_seen:
                cur.execute("INSERT INTO marks (student_id, subject, marks) VALUES (?,?,?)",
                            (sid, msubj, mmarks))
                marks_seen.add(mk_key)

            # timetable — deduplicate (class, day, subject, time)
            tt_key = (cls, row["day"].strip(), row["subject"].strip(), row["time"].strip())
            if tt_key not in timetable_seen:
                cur.execute("INSERT INTO timetable (class, day, subject, time) VALUES (?,?,?,?)",
                            (cls, row["day"].strip(), row["subject"].strip(), row["time"].strip()))
                timetable_seen.add(tt_key)

            # assignments — deduplicate (class, subject, due_date)
            asubj = row["assignment_subject"].strip()
            adate = row["date"].strip()
            atask = row["task"].strip()
            asgn_key = (cls, asubj, adate)
            if asgn_key not in assignments_seen:
                cur.execute("INSERT INTO assignments (class, subject, due_date, task) VALUES (?,?,?,?)",
                            (cls, asubj, adate, atask))
                assignments_seen.add(asgn_key)

    conn.commit()
    conn.close()
    print("[OK] Database initialised from CSV.\n")


# ─────────────────────────────────────────────
# 2. LANGUAGE DETECTION
# ─────────────────────────────────────────────

HINDI_CHARS = re.compile(r'[\u0900-\u097F]')

# Words that are EXCLUSIVELY Hinglish/Hindi transliterated — pure English words excluded
HINGLISH_KEYWORDS = {
    "mera", "meri", "mujhe", "muje", "meko", "apna", "apni",
    "kya", "kab", "kaise", "kaun", "konsa", "kitna", "kitne",
    "hai", "hain", "tha", "thi", "ho", "hoga",
    "aaj", "kal", "parso", "ka", "ki", "ke",
    "batao", "batado", "bata", "dikhao", "dikha", "chahiye",
    "kaam", "padhai", "nahi", "pura", "ank", "nambr",
}


def detect_language(text: str) -> str:
    """Returns 'hindi', 'hinglish', or 'english'."""
    if HINDI_CHARS.search(text):
        return "hindi"
    words = set(text.lower().split())
    if words & HINGLISH_KEYWORDS:
        return "hinglish"
    return "english"


# ─────────────────────────────────────────────
# 3. INTENT DETECTION
# ─────────────────────────────────────────────

INTENT_PATTERNS = {
    "timetable": [
        r"\btimetable\b", r"\bschedule\b", r"\btime[ -]?table\b",
        r"\bclass(?:es)?\s+(?:on|for|at)\b", r"\bperiod\b",
        r"\bclasses?\s+today\b", r"\bwhat.*class\b",
        # Hindi / Hinglish
        r"\bsamay[ -]?saarni\b", r"\bsaarani\b", r"\bkab.*class\b",
        r"\bclass.*kab\b", r"\bkab.*padhai\b", r"\bschedule\b",
        r"टाइमटेबल", r"समय[ -]?सारणी",
    ],
    "marks": [
        r"\bmarks?\b", r"\bscore[sd]?\b", r"\bgrades?\b", r"\bresult[s]?\b",
        r"\bperformance\b", r"\btest\b", r"\bexam\b",
        # Hindi / Hinglish
        r"\bnumber[s]?\b", r"\bnambr\b", r"\bank[s]?\b",
        r"\bresult\b", r"\bparinam\b",
        r"अंक", r"मार्क्स", r"नंबर", r"परिणाम",
    ],
    "assignments": [
        r"\bassignment[s]?\b", r"\bhomework\b", r"\bhw\b",
        r"\btask[s]?\b", r"\bdue\b", r"\bsubmit\b",
        # Hindi / Hinglish
        r"\bgrihakarya\b", r"\bkaam\b", r"\bkaam[ -]?kaj\b",
        r"\bghar.*kaam\b",
        r"गृहकार्य", r"होमवर्क", r"असाइनमेंट",
    ],
}


def detect_intent(text: str) -> str:
    lower = text.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, lower):
                return intent
    return "unknown"


# ─────────────────────────────────────────────
# 4. ENTITY EXTRACTION
# ─────────────────────────────────────────────

DAYS_EN = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
DAYS_HI = {
    "सोमवार": "Monday", "मंगलवार": "Tuesday", "बुधवार": "Wednesday",
    "गुरुवार": "Thursday", "शुक्रवार": "Friday", "शनिवार": "Saturday",
    "रविवार": "Sunday",
    "somvar": "Monday", "mangalvar": "Tuesday", "budhvar": "Wednesday",
    "guruvar": "Thursday", "shukravar": "Friday", "shanivar": "Saturday",
    "ravivar": "Sunday",
}

SUBJECTS_EN = {
    "math", "maths", "mathematics", "english", "science", "physics",
    "chemistry", "biology", "hindi", "history", "geography", "computer",
}
SUBJECTS_HI = {
    "ganit": "Math", "vigyan": "Science", "bhautiki": "Physics",
    "rasayan": "Chemistry", "jeev": "Biology", "itihas": "History",
    "गणित": "Math", "विज्ञान": "Science", "भौतिकी": "Physics",
    "अंग्रेज़ी": "English", "हिंदी": "Hindi",
}

SUBJECT_NORMALIZE = {
    "math": "Math", "maths": "Math", "mathematics": "Math",
    "english": "English", "science": "Science", "physics": "Physics",
    "chemistry": "Chemistry", "biology": "Biology",
    "hindi": "Hindi", "history": "History", "geography": "Geography",
    "computer": "Computer",
}


def extract_entities(text: str, conn: sqlite3.Connection) -> dict:
    entities = {"student_name": None, "class": None, "subject": None, "day": None, "date": None}
    lower = text.lower()

    # ── Day ──
    for day in DAYS_EN:
        if day in lower:
            entities["day"] = day.capitalize()
            break
    if not entities["day"]:
        for hi, en in DAYS_HI.items():
            if hi.lower() in lower:
                entities["day"] = en
                break

    # ── Subject ──
    for s_key, s_val in SUBJECTS_HI.items():
        if s_key.lower() in lower:
            entities["subject"] = s_val
            break
    if not entities["subject"]:
        for s in SUBJECTS_EN:
            if re.search(rf'\b{s}\b', lower):
                entities["subject"] = SUBJECT_NORMALIZE.get(s, s.capitalize())
                break

    # ── Date ──
    date_match = re.search(r'\d{4}-\d{2}-\d{2}', text)
    if date_match:
        entities["date"] = date_match.group()

    # ── Class ──
    cls_match = re.search(r'(?:class|grade|std|कक्षा)\s*(\d+)', lower)
    if cls_match:
        entities["class"] = int(cls_match.group(1))
    else:
        cls_match2 = re.search(r'\b(\d+)(?:st|nd|rd|th)?\s+(?:class|grade|std)\b', lower)
        if cls_match2:
            entities["class"] = int(cls_match2.group(1))

    # ── Student name — match against DB ──
    cur = conn.cursor()
    cur.execute("SELECT student_id, student_name FROM students")
    for sid, sname in cur.fetchall():
        first = sname.split()[0].lower()
        last  = sname.split()[-1].lower() if len(sname.split()) > 1 else ""
        if first in lower or (last and last in lower) or sname.lower() in lower:
            entities["student_name"] = sname
            entities["_student_id"]  = sid
            break

    return entities


# ─────────────────────────────────────────────
# 5. ROLE-BASED ACCESS CONTROL
# ─────────────────────────────────────────────

def resolve_target_student(role: str, user_id: int, entities: dict,
                            conn: sqlite3.Connection) -> tuple:
    """
    Returns (student_id, student_name, error_msg).
    Enforces:
      - student  → only own student_id
      - parent   → only linked children (max 2)
    """
    cur = conn.cursor()

    if role == "student":
        # Students can only access their own data
        cur.execute("SELECT student_id, student_name FROM students WHERE student_id = ?", (user_id,))
        row = cur.fetchone()
        if not row:
            return None, None, "Student record not found."
        return row[0], row[1], None

    elif role == "parent":
        # Fetch parent's linked children
        cur.execute("""
            SELECT s.student_id, s.student_name
            FROM parent_student ps
            JOIN students s ON s.student_id = ps.student_id
            WHERE ps.parent_id = ?
        """, (user_id,))
        children = cur.fetchall()

        if not children:
            return None, None, "No children linked to this parent account."

        # Enforce max 2 children
        children = children[:2]

        # If query mentions a specific child name, resolve that child
        req_name = entities.get("student_name")
        if req_name:
            for cid, cname in children:
                if req_name.lower() in cname.lower():
                    return cid, cname, None
            return None, None, f"You don't have access to data for '{req_name}'."

        # Single child — return automatically
        if len(children) == 1:
            return children[0][0], children[0][1], None

        # Multiple children — return list for caller to handle
        return None, None, ("MULTI_CHILD", children)

    return None, None, "Unknown role."


# ─────────────────────────────────────────────
# 6. SQL QUERY BUILDER
# ─────────────────────────────────────────────

def build_sql(intent: str, student_id: int, student_class: int,
              entities: dict) -> tuple:
    """Returns (sql_string, params_tuple, description)."""

    if intent == "marks":
        subject = entities.get("subject")
        if subject:
            sql = """
                SELECT m.subject, m.marks
                FROM marks m
                WHERE m.student_id = ? AND LOWER(m.subject) = LOWER(?)
            """
            return sql, (student_id, subject), f"marks for {subject}"
        else:
            sql = """
                SELECT m.subject, m.marks
                FROM marks m
                WHERE m.student_id = ?
                ORDER BY m.subject
            """
            return sql, (student_id,), "all marks"

    elif intent == "timetable":
        day = entities.get("day")
        if day:
            sql = """
                SELECT t.day, t.subject, t.time
                FROM timetable t
                WHERE t.class = ? AND LOWER(t.day) = LOWER(?)
                ORDER BY t.time
            """
            return sql, (student_class, day), f"timetable for {day}"
        else:
            sql = """
                SELECT t.day, t.subject, t.time
                FROM timetable t
                WHERE t.class = ?
                ORDER BY CASE t.day
                    WHEN 'Monday'    THEN 1
                    WHEN 'Tuesday'   THEN 2
                    WHEN 'Wednesday' THEN 3
                    WHEN 'Thursday'  THEN 4
                    WHEN 'Friday'    THEN 5
                    WHEN 'Saturday'  THEN 6
                    WHEN 'Sunday'    THEN 7
                    ELSE 8 END, t.time
            """
            return sql, (student_class,), "full timetable"

    elif intent == "assignments":
        subject = entities.get("subject")
        date    = entities.get("date")
        if subject and date:
            sql = """
                SELECT a.subject, a.due_date, a.task
                FROM assignments a
                WHERE a.class = ? AND LOWER(a.subject) = LOWER(?) AND a.due_date = ?
                ORDER BY a.due_date
            """
            return sql, (student_class, subject, date), f"assignment for {subject} on {date}"
        elif subject:
            sql = """
                SELECT a.subject, a.due_date, a.task
                FROM assignments a
                WHERE a.class = ? AND LOWER(a.subject) = LOWER(?)
                ORDER BY a.due_date
            """
            return sql, (student_class, subject), f"assignment for {subject}"
        elif date:
            sql = """
                SELECT a.subject, a.due_date, a.task
                FROM assignments a
                WHERE a.class = ? AND a.due_date = ?
                ORDER BY a.subject
            """
            return sql, (student_class, date), f"assignments due on {date}"
        else:
            sql = """
                SELECT a.subject, a.due_date, a.task
                FROM assignments a
                WHERE a.class = ?
                ORDER BY a.due_date, a.subject
            """
            return sql, (student_class,), "all assignments"

    return None, None, None


# ─────────────────────────────────────────────
# 7. NATURAL LANGUAGE RESPONSE GENERATOR
# ─────────────────────────────────────────────

def format_response(intent: str, rows: list, student_name: str,
                    entities: dict, lang: str, description: str) -> str:

    first_name = student_name.split()[0] if student_name else "Student"

    if not rows:
        if lang == "hindi":
            return f"{first_name} के लिए कोई {description} नहीं मिला।"
        elif lang == "hinglish":
            return f"{first_name} ke liye koi {description} nahi mila."
        else:
            return f"No {description} found for {first_name}."

    # -- MARKS --
    if intent == "marks":
        if lang == "hindi":
            lines = [f"[Marks] {first_name} ke ank:"]
            for subj, score in rows:
                lines.append(f"  - {subj}: {score}")
        elif lang == "hinglish":
            lines = [f"[Marks] {first_name} ke marks:"]
            for subj, score in rows:
                lines.append(f"  - {subj}: {score}")
        else:
            lines = [f"[Marks] Marks for {first_name}:"]
            for subj, score in rows:
                lines.append(f"  - {subj}: {score}")
        return "\n".join(lines)

    # -- TIMETABLE --
    elif intent == "timetable":
        day = entities.get("day")
        if lang == "hindi":
            header = (f"[Timetable] {first_name} ka {day} ka timetable:"
                      if day else f"[Timetable] {first_name} ka pura timetable:")
        elif lang == "hinglish":
            header = (f"[Timetable] {first_name} ka {day} ka timetable:"
                      if day else f"[Timetable] {first_name} ka full timetable:")
        else:
            header = (f"[Timetable] {first_name}'s timetable for {day}:"
                      if day else f"[Timetable] {first_name}'s full timetable:")

        lines = [header]
        current_day = None
        for row in rows:
            rday, subj, time_ = row
            if not day and rday != current_day:
                lines.append(f"\n  [{rday}]")
                current_day = rday
            lines.append(f"  - {time_}  :  {subj}")
        return "\n".join(lines)

    # -- ASSIGNMENTS --
    elif intent == "assignments":
        if lang == "hindi":
            lines = [f"[Assignments] {first_name} ke assignments:"]
            for subj, due, task in rows:
                lines.append(f"  - {subj} | due: {due} | kaam: {task}")
        elif lang == "hinglish":
            lines = [f"[Assignments] {first_name} ke assignments:"]
            for subj, due, task in rows:
                lines.append(f"  - {subj} | due: {due} | kaam: {task}")
        else:
            lines = [f"[Assignments] Assignments for {first_name}:"]
            for subj, due, task in rows:
                lines.append(f"  - {subj} | Due: {due} | Task: {task}")
        return "\n".join(lines)

    return "Data retrieved successfully."


# ─────────────────────────────────────────────
# 8. MAIN CHATBOT ENGINE
# ─────────────────────────────────────────────

def process_query(query: str, role: str, user_id: int, conn: sqlite3.Connection) -> str:
    """
    Core pipeline:
      detect_language → detect_intent → extract_entities
      → RBAC → build_sql → execute → format_response
    """
    lang   = detect_language(query)
    intent = detect_intent(query)

    if intent == "unknown":
        msgs = {
            "hindi":    "माफ़ करें, मैं आपका प्रश्न नहीं समझ पाया। कृपया timetable, marks, या assignment के बारे में पूछें।",
            "hinglish": "Sorry, mujhe samajh nahi aaya. Please timetable, marks, ya assignment ke baare mein pucho.",
            "english":  "Sorry, I didn't understand your query. Please ask about timetable, marks, or assignments.",
        }
        return msgs[lang]

    entities = extract_entities(query, conn)

    # RBAC resolution
    result = resolve_target_student(role, user_id, entities, conn)
    student_id, student_name, error = result

    # Handle multi-child case for parents
    if isinstance(error, tuple) and error[0] == "MULTI_CHILD":
        children = error[1]
        names = ", ".join(c[1] for c in children)
        if lang == "hindi":
            return f"आपके कई बच्चे हैं: {names}। किस बच्चे के बारे में जानना है?"
        elif lang == "hinglish":
            return f"Aapke multiple bachche hain: {names}. Kis baare mein jaanna hai?"
        else:
            return f"You have multiple children: {names}. Please specify which child you're asking about."

    if error:
        return f"⚠️ Access denied: {error}"

    # Fetch student class
    cur = conn.cursor()
    cur.execute("SELECT class FROM students WHERE student_id = ?", (student_id,))
    row = cur.fetchone()
    student_class = row[0] if row else None

    # Build SQL
    sql, params, description = build_sql(intent, student_id, student_class, entities)
    if not sql:
        return "Could not generate a query for your request."

    # Log the generated SQL (visible in terminal)
    print(f"\n  [SQL] {sql.strip()}")
    print(f"  [Params] {params}")

    # Execute
    cur.execute(sql, params)
    rows = cur.fetchall()

    # Format response
    return format_response(intent, rows, student_name, entities, lang, description)


# ─────────────────────────────────────────────
# 9. USER SESSION MANAGEMENT
# ─────────────────────────────────────────────

def login(conn: sqlite3.Connection) -> tuple:
    """Simple CLI login — returns (role, user_id, display_name)."""
    print("\n" + "=" * 55)
    print("   [School Chatbot]  Multilingual AI Assistant")
    print("=" * 55)
    print("\nAvailable accounts:")
    print("  STUDENTS:")
    cur = conn.cursor()
    cur.execute("SELECT student_id, student_name, class FROM students ORDER BY student_id")
    for sid, sname, cls in cur.fetchall():
        print(f"    [{sid}] {sname} — Class {cls}")
    print("\n  PARENTS:")
    cur.execute("SELECT p.parent_id, p.parent_name, GROUP_CONCAT(s.student_name, ' & ') AS children "
                "FROM parents p JOIN parent_student ps ON ps.parent_id = p.parent_id "
                "JOIN students s ON s.student_id = ps.student_id "
                "GROUP BY p.parent_id")
    for pid, pname, children in cur.fetchall():
        print(f"    [{pid}] {pname} — Parent of: {children}")

    print()
    while True:
        role = input("Login as (student/parent): ").strip().lower()
        if role in ("student", "parent"):
            break
        print("  Please type 'student' or 'parent'.")

    while True:
        try:
            uid = int(input(f"Enter your {'student' if role == 'student' else 'parent'} ID: ").strip())
        except ValueError:
            print("  Please enter a valid numeric ID.")
            continue

        if role == "student":
            cur.execute("SELECT student_name FROM students WHERE student_id = ?", (uid,))
        else:
            cur.execute("SELECT parent_name FROM parents WHERE parent_id = ?", (uid,))

        row = cur.fetchone()
        if row:
            print(f"\n[OK] Welcome, {row[0]}!")
            return role, uid, row[0]
        print("  ID not found. Please try again.")


# ─────────────────────────────────────────────
# 10. MAIN LOOP
# ─────────────────────────────────────────────

HELP_TEXT = """
Commands:
  help     - show this message
  lang     - current language detection info
  logout   - switch account
  exit     - quit

Ask about:
  [Timetable]   "Show my timetable for Monday"
                "Mera Monday ka schedule dikhao"
                "somvar ka timetable batao"
  [Marks]       "What are my Math marks?"
                "Mujhe mere marks batao"
                "mere ank kya hain?"
  [Assignments] "Show my homework"
                "Mera assignment kab submit karna hai?"
                "mera homework kya hai?"
"""


def main():
    init_db()
    conn = sqlite3.connect(DB_PATH)

    role, user_id, display_name = login(conn)

    print(HELP_TEXT)
    print("-" * 55)

    while True:
        try:
            query = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye! / अलविदा!")
            break

        if not query:
            continue

        cmd = query.lower()
        if cmd in ("exit", "quit", "bye"):
            print("Goodbye! / Alvida!")
            break
        elif cmd == "help":
            print(HELP_TEXT)
            continue
        elif cmd == "logout":
            role, user_id, display_name = login(conn)
            print(HELP_TEXT)
            print("-" * 55)
            continue
        elif cmd == "lang":
            print(f"  Detected language: {detect_language(query)}")
            continue

        response = process_query(query, role, user_id, conn)
        print(f"\nBot: {response}")

    conn.close()


if __name__ == "__main__":
    main()
