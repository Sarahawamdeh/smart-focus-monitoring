import sqlite3

def add_courses():
    conn = sqlite3.connect('smart_focus.db')
    cursor = conn.cursor()

    # الإيميل اللي شفناه في الصورة
    instructor_email = 'sarahawamdehh@gmail.com'

    # المواد اللي طلبتيها
    courses_to_add = [
        ('CS111', 'Python Programming', 'Sec 1', instructor_email),
        ('CS332', 'Network', 'Sec 2', instructor_email),
        ('CS111L', 'Lab Python', 'Sec 1', instructor_email)
    ]

    try:
        cursor.executemany('''
            INSERT OR REPLACE INTO courses (c_code, c_name, section, I_email)
            VALUES (?, ?, ?, ?)
        ''', courses_to_add)
        conn.commit()
        print(f"✅ Done! Courses added to: {instructor_email}")
    except sqlite3.Error as e:
        print(f"❌ Error: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    add_courses()