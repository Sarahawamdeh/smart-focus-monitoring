import sqlite3

def create_database():
    conn = sqlite3.connect('smart_focus.db')
    cursor = conn.cursor()

    # جدول الدكاترة
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS instructors (
            email VARCHAR(100) PRIMARY KEY,
            fullname VARCHAR(150) NOT NULL,
            password VARCHAR(255) NOT NULL
        )
    ''')
    # جدول الكورسات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS courses (
            c_code VARCHAR(15) PRIMARY KEY,
            c_name VARCHAR(100) NOT NULL,
            section VARCHAR(10),
            I_email VARCHAR(100),
            FOREIGN KEY (I_email) REFERENCES instructors (email)
        )
    ''')

    # جدول الجلسات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS session (
            s_id INTEGER PRIMARY KEY AUTOINCREMENT,
            c_code VARCHAR(15),
            duration VARCHAR(50),]
            avg_focus REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (c_code) REFERENCES courses (c_code)
        )
    ''')

    # جدول تركيز الطلاب
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS std_focus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            s_id INTEGER,
            student_name VARCHAR(100),
            focus REAL,
            FOREIGN KEY (s_id) REFERENCES session (s_id)
        )
    ''')

    conn.commit()
    conn.close()
    print("تم إنشاء قاعدة البيانات بأفضل المعايير!")

if __name__ == "__main__":
    create_database()