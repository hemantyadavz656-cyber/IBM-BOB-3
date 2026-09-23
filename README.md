# 🏫 School Chatbot — Multilingual AI Assistant

An AI-powered multilingual school chatbot that understands queries in **English**, **Hindi**, and **Hinglish**. It identifies user intent, extracts entities, generates SQL queries, enforces role-based access control, and responds in the same language the user asked in.

---

## 📁 Project Structure

```
harsh/
├── school_chatbot.py           # Main chatbot application
├── school_chatbot_dataset.csv  # Source data (students, marks, timetable, assignments)
├── school_chatbot.db           # Auto-generated SQLite database (created on first run)
└── README.md                   # This file
```

---

## ⚙️ Requirements

- **Python 3.8+** (no external libraries needed)
- Built-in modules only: `sqlite3`, `csv`, `re`, `os`, `sys`

Verify your Python version:

```powershell
py --version
```

---

## 🚀 How to Run

### Step 1 — Open the project folder in PowerShell

```powershell
cd "C:\Users\HEMANT YADAV\OneDrive\Desktop\harsh"
```

### Step 2 — Run the chatbot

```powershell
py school_chatbot.py
```

> ⚠️ Always run from the `harsh` folder so the app can find `school_chatbot_dataset.csv` and create `school_chatbot.db` in the correct location.

---

## 🔐 Login

On startup, all available accounts are displayed. Choose your role and enter your ID:

```
=======================================================
   [School Chatbot]  Multilingual AI Assistant
=======================================================

Available accounts:
  STUDENTS:
    [1] Aarav Sharma  — Class 5
    [2] Diya Verma    — Class 5
    [3] Rohan Singh   — Class 6
    [4] Ananya Gupta  — Class 7
    [5] Kabir Khan    — Class 8
    [6] Meera Joshi   — Class 9

  PARENTS:
    [1] Rajesh Sharma  — Parent of: Aarav Sharma
    [2] Sneha Verma    — Parent of: Diya Verma
    [3] Amit Singh     — Parent of: Rohan Singh
    [4] Pooja Gupta    — Parent of: Ananya Gupta & Kabir Khan

Login as (student/parent): student
Enter your student ID: 1

[OK] Welcome, Aarav Sharma!
```

---

## 💬 Sample Queries

### Timetable

| Language   | Query |
|------------|-------|
| English    | `Show my timetable for Monday` |
| Hinglish   | `Mera Monday ka schedule dikhao` |
| Hinglish   | `somvar ka timetable batao` |
| English    | `What is my full timetable` |

### Marks

| Language   | Query |
|------------|-------|
| English    | `What are my Math marks?` |
| English    | `Show my results` |
| Hinglish   | `Mujhe mere marks batao` |
| Hinglish   | `mere ank kya hain?` |

### Assignments

| Language   | Query |
|------------|-------|
| English    | `Show my homework` |
| English    | `Science assignment` |
| Hinglish   | `Mera assignment kab submit karna hai?` |
| Hinglish   | `mera homework kya hai?` |

---

## 🛡️ Role-Based Access Control

| Role | Access Rule |
|------|-------------|
| **Student** | Can only view their own marks, timetable, and assignments |
| **Parent** | Can only view data for their linked child/children (max 2) |
| **Parent (2 children)** | Must specify the child's name — e.g. `Show marks for Ananya` |
| **Cross-access attempt** | Blocked immediately with an `Access denied` message |

### Example — RBAC in action

```
# Parent (Rajesh, ID=1) trying to access Diya's data:
Query: "Show marks for Diya"
Bot:   ⚠️ Access denied: You don't have access to data for 'Diya Verma'.

# Parent (Pooja, ID=4) with 2 children, accessing each:
Query: "What are Ananya marks"   → Shows Ananya's marks only
Query: "What are Kabir marks"    → Shows Kabir's marks only
```

---

## 🗄️ Database Schema

The CSV is normalised into 6 tables on first run:

```
students        (student_id PK, student_name, class)
parents         (parent_id PK, parent_name)
parent_student  (parent_id FK, student_id FK)   ← many-to-many link
marks           (id PK, student_id FK, subject, marks)
timetable       (id PK, class, day, subject, time)
assignments     (id PK, class, subject, due_date, task)
```

---

## 🧠 How It Works (Pipeline)

```
User Query
   │
   ▼
detect_language()      → English / Hindi / Hinglish
   │
   ▼
detect_intent()        → timetable / marks / assignments
   │
   ▼
extract_entities()     → student name, class, subject, day, date
   │
   ▼
resolve_target_student()  → RBAC check (student/parent rules)
   │
   ▼
build_sql()            → Parametrised SQL query
   │
   ▼
SQLite Execute         → Fetch rows from DB
   │
   ▼
format_response()      → Natural language reply in user's language
```

---

## ⌨️ Special Commands

| Command  | Description |
|----------|-------------|
| `help`   | Show sample queries and command list |
| `lang`   | Display detected language of your last message |
| `logout` | Switch to a different student/parent account |
| `exit`   | Quit the chatbot |

---

## 🔧 Troubleshooting

| Problem | Solution |
|---------|----------|
| `Python was not found` | Use `py` instead of `python` on Windows |
| `FileNotFoundError: school_chatbot_dataset.csv` | Run from the `harsh` folder, not a different directory |
| Hindi text shows `?` characters | Use **Windows Terminal** (supports UTF-8) instead of the old CMD |
| Want to reset the database | Delete `school_chatbot.db` and re-run — it rebuilds from the CSV |
| Intent not recognised | Rephrase using keywords: `timetable`, `marks`, `result`, `homework`, `assignment` |

---

## 📊 Data Overview

| Entity | Count |
|--------|-------|
| Students | 6 (Classes 5–9) |
| Parents | 4 |
| Parent–child links | 5 (Pooja Gupta has 2 children) |
| Mark records | 8 |
| Timetable slots | 8 |
| Assignments | 6 |

---

## 📝 License

This project is for educational purposes.
