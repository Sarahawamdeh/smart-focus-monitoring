import sqlite3


def init_pro_db():
    conn = sqlite3.connect('smart_focus.db')
    cursor = conn.cursor()
    # تفعيل العلاقات بين الجداول
    cursor.execute('PRAGMA foreign_keys = ON;')

    # 1. المدرسين
    cursor.execute('''CREATE TABLE IF NOT EXISTS instructors (
        ins_id INTEGER PRIMARY KEY AUTOINCREMENT,
        fullname TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL
    )''')

    # 2. المواد
    cursor.execute('''CREATE TABLE IF NOT EXISTS courses (
        course_code TEXT PRIMARY KEY, -- مثل CS101
        course_name TEXT NOT NULL
    )''')

    # 3. الشعب (تربط المادة بالمدرس)
    cursor.execute('''CREATE TABLE IF NOT EXISTS sections (
        section_id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_code TEXT,
        ins_id INTEGER,
        section_num INTEGER, -- رقم الشعبة 1، 2، 3
        FOREIGN KEY (course_code) REFERENCES courses (course_code),
        FOREIGN KEY (ins_id) REFERENCES instructors (ins_id)
    )''')

    # 4. الطلاب (ثابتين)
    cursor.execute('''CREATE TABLE IF NOT EXISTS students (
        student_id INTEGER PRIMARY KEY, -- الرقم الجامعي
        student_name TEXT NOT NULL
    )''')

    # 5. الجلسات (المحاضرات)
    cursor.execute('''CREATE TABLE IF NOT EXISTS sessions (
        session_id INTEGER PRIMARY KEY AUTOINCREMENT,
        section_id INTEGER,
        avg_focus REAL,
        duration TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (section_id) REFERENCES sections (section_id)
    )''')

    # 6. تفاصيل التركيز لكل طالب
    cursor.execute('''CREATE TABLE IF NOT EXISTS student_focus_data (
        record_id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id INTEGER,
        student_id INTEGER,
        focus_score REAL,
        FOREIGN KEY (session_id) REFERENCES sessions (session_id),
        FOREIGN KEY (student_id) REFERENCES students (student_id)
    )''')

    conn.commit()
    conn.close()
    print("✅ تم إنشاء الداتابيز بنجاح!")

if __name__ == "__main__":
    init_pro_db()