import sqlite3

def init_pro_db():
    conn = sqlite3.connect('smart_focus.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')

    # ... (الجداول من 1 إلى 6 كما هي عندك) ...

    # 7. جدول التسجيل (Enrollment) - الإضافة الجديدة هنا
    cursor.execute('''CREATE TABLE IF NOT EXISTS enrollment (
        enrollment_id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER,
        section_id INTEGER,
        enroll_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (student_id) REFERENCES students (student_id),
        FOREIGN KEY (section_id) REFERENCES sections (section_id),
        UNIQUE(student_id, section_id) 
    )''')

    conn.commit()
    conn.close()
    

if __name__ == "__main__":
    init_pro_db()