import sqlite3
from werkzeug.security import generate_password_hash

def seed_yu_data():
    # الاتصال بنفس قاعدة البيانات التي أنشأتيها
    conn = sqlite3.connect('smart_focus.db')
    cursor = conn.cursor()
    cursor.execute('PRAGMA foreign_keys = ON;')

    # 1. تشفير كلمة السر الافتراضية '123'
    hashed_pw = generate_password_hash('123')

    try:
        # 2. إضافة الدكاترة (باستخدام الهاش)
        instructors = [
            ('Sarah Hawamdeh', 'sarahhawamdeh@yu.edu.jo', hashed_pw),
            ('Abrar Abedalhaq', 'AbrarAbedalhaq@yu.edu.jo', hashed_pw)
        ]
        # استخدمنا REPLACE لتحديث كلمة السر إذا كانت موجودة مسبقاً
        cursor.executemany("INSERT OR REPLACE INTO instructors (fullname, email, password) VALUES (?, ?, ?)", instructors)

        # 3. إضافة المواد
        courses = [
            ('cs332', 'Network'),
            ('cis342', 'System'),
            ('cs111L', 'Lab Python'),
            ('cis468', 'Big Data'),
            ('cis260', 'Database')
        ]
        cursor.executemany("INSERT OR IGNORE INTO courses (course_code, course_name) VALUES (?, ?)", courses)

        # 4. إضافة الشعب (ربط المواد بالدكاترة)
        # سارة (id: 1)، أبرار (id: 2)
        sections = [
            ('cs332', 1, 1), 
            ('cis342', 1, 2), 
            ('cs111L', 1, 1), 
            ('cis468', 2, 1), 
            ('cis468', 2, 2), 
            ('cis260', 2, 1)
        ]
        cursor.executemany("INSERT OR IGNORE INTO sections (course_code, ins_id, section_num) VALUES (?, ?, ?)", sections)

        # 5. إضافة الطلاب الـ 5
        students = [
            (20210001, 'Student 1'),
            (20210002, 'Student 2'),
            (20210003, 'Student 3'),
            (20210004, 'Student 4'),
            (20210005, 'Student 5')
        ]
        cursor.executemany("INSERT OR IGNORE INTO students (student_id, student_name) VALUES (?, ?)", students)

        conn.commit()
        print("✅ تم تعبئة البيانات وتشفير كلمات السر بنجاح!")
    
    except sqlite3.Error as e:
        print(f"❌ حدث خطأ أثناء إضافة البيانات: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    seed_yu_data()