import sqlite3

def refresh_courses():
    conn = sqlite3.connect('smart_focus.db')
    cursor = conn.cursor()

    instructor_email = 'sarahawamdehh@gmail.com'

    # 1. مسح المواد القديمة لهذا الإيميل أولاً للتأكد من نظافة البيانات
    cursor.execute("DELETE FROM courses WHERE I_email = ?", (instructor_email,))

    # 2. المواد الجديدة مع التعديل المطلوب (Sec 2 للشبكات)
    courses_to_add = [
        ('CS111', 'Python Programming', 'Sec 1', instructor_email),
        ('CS332', 'Network', 'Sec 2', instructor_email), # التعديل هنا
        ('CS111L', 'Lab Python', 'Sec 1', instructor_email)
    ]

    try:
        cursor.executemany('''
            INSERT INTO courses (c_code, c_name, section, I_email)
            VALUES (?, ?, ?, ?)
        ''', courses_to_add)
        
        conn.commit()
        print("✅ تم تحديث البيانات بنجاح! نيتورك الآن Sec 2")
    except sqlite3.Error as e:
        print(f"❌ خطأ: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    refresh_courses()