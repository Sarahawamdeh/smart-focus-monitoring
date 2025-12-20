import sqlite3

def fix_my_db():
    conn = sqlite3.connect('smart_focus.db')
    cursor = conn.cursor()
    
    # 1. تفعيل دعم الـ Foreign Keys
    cursor.execute('PRAGMA foreign_keys = OFF;')

    # 2. إنشاء جدول الكورسات الجديد بالهيكل الاحترافي
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses_new (
            c_id INTEGER PRIMARY KEY AUTOINCREMENT,
            c_code VARCHAR(15) NOT NULL,
            c_name VARCHAR(100) NOT NULL,
            section VARCHAR(10) NOT NULL,
            I_email VARCHAR(100),
            UNIQUE(c_code, section),
            FOREIGN KEY (I_email) REFERENCES instructors (email)
        )
    ''')

    # 3. نقل بياناتك القديمة للجدول الجديد
    cursor.execute('''
        INSERT OR IGNORE INTO courses_new (c_code, c_name, section, I_email)
        SELECT c_code, c_name, section, I_email FROM courses
    ''')

    # 4. مسح الجداول القديمة وتبديلها
    cursor.execute("DROP TABLE IF EXISTS session") # بنمسح السيشن لأننا بنغير طريقة الربط
    cursor.execute("DROP TABLE IF EXISTS courses")
    
    cursor.execute("ALTER TABLE courses_new RENAME TO courses")
    
    # 5. إعادة إنشاء جدول السيشن بالربط الجديد
    cursor.execute('''
        CREATE TABLE session (
            s_id INTEGER PRIMARY KEY AUTOINCREMENT,
            course_id INTEGER,
            duration VARCHAR(50),
            avg_focus REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (course_id) REFERENCES courses (c_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("✅ الخطوة الأولى تمت بنجاح! الداتابيز صارت جاهزة.")

fix_my_db()