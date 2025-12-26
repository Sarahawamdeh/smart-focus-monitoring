import sqlite3

def check():
    conn = sqlite3.connect('smart_focus.db')
    cursor = conn.cursor()
    
    print("--- Instructors Table ---")
    cursor.execute("SELECT * FROM instructors")
    for row in cursor.fetchall():
        print(dict(zip([column[0] for column in cursor.description], row)))
        
    print("\n--- Courses Table ---")
    cursor.execute("SELECT * FROM courses")
    for row in cursor.fetchall():
        print(dict(zip([column[0] for column in cursor.description], row)))
        
    conn.close()

if __name__ == "__main__":
    check()