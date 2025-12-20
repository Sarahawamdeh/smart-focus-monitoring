from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session
import cv2
import mediapipe as mp
import numpy as np
import time
import pygame
import threading
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'yu_smart_focus_secret' 

# --- 1. إعدادات الداتا بيز ---
def get_db_connection():
    conn = sqlite3.connect('smart_focus.db')
    conn.row_factory = sqlite3.Row
    return conn
# --- إعداد الصوت ---
pygame.mixer.init()
alert_sound = "static/alert.mp3"
alert_played = False

mp_face_mesh = mp.solutions.face_mesh
focus_dict = {}      
closed_start = {}
tilt_start = {}
tilt_recovery = {}
highlighted_student_id = None
focus_lock = threading.Lock()
last_face_time = time.time()

cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 750)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 450)
mesh = mp_face_mesh.FaceMesh(refine_landmarks=True, max_num_faces=5)
def gen_frames():
    global alert_played, last_face_time, highlighted_student_id
    while True:
        ret, frame = cap.read()
        if not ret:
            time.sleep(0.1)
            continue

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = mesh.process(rgb)

        avg_focus = 0
        face_count = 0

        if res.multi_face_landmarks:
            last_face_time = time.time()
            faces_with_pos = []

            for fid, face_landmarks in enumerate(res.multi_face_landmarks):
                xs = [int(l.x * w) for l in face_landmarks.landmark]
                x_min = min(xs)
                faces_with_pos.append((x_min, fid, face_landmarks))

            faces_with_pos.sort(key=lambda x: x[0], reverse=True)

            for idx, (x_min, fid, face_landmarks) in enumerate(faces_with_pos):
                landmarks = face_landmarks.landmark

                if fid not in focus_dict:
                    with focus_lock:
                        focus_dict[fid] = 100.0
                    closed_start[fid] = None
                    tilt_start[fid] = None
                    tilt_recovery[fid] = False

                with focus_lock:
                    focus = focus_dict.get(fid, 100.0)

                movement_detected = False

                # --- العين ---
                left_eye_idx = [33,160,158,133,153,144]
                right_eye_idx = [362,385,387,263,373,380]

                left_eye = [landmarks[i] for i in left_eye_idx]
                right_eye = [landmarks[i] for i in right_eye_idx]

                def eye_aspect_ratio_local(eye_landmarks, w, h):
                    p = [(int(l.x * w), int(l.y * h)) for l in eye_landmarks]
                    vertical1 = np.linalg.norm(np.array(p[1]) - np.array(p[5]))
                    vertical2 = np.linalg.norm(np.array(p[2]) - np.array(p[4]))
                    horizontal = np.linalg.norm(np.array(p[0]) - np.array(p[3]))
                    return (vertical1 + vertical2) / (2.0 * horizontal)

                left_EAR = eye_aspect_ratio_local(left_eye, w, h)
                right_EAR = eye_aspect_ratio_local(right_eye, w, h)
                ear = (left_EAR + right_EAR) / 2.0

                # --- ميل الرأس ---
                def head_tilt_local(landmarks, w, h):
                    left = np.array([landmarks[234].x * w, landmarks[234].y * h])
                    right = np.array([landmarks[454].x * w, landmarks[454].y * h])
                    dx = right[0] - left[0]
                    dy = right[1] - left[1]
                    return abs(np.degrees(np.arctan2(dy, dx)))

                tilt = head_tilt_local(landmarks, w, h)
                now = time.time()

                # --- تحديث التركيز بناءً على العين ---
                if ear < 0.21:
                    movement_detected = True
                    if closed_start[fid] is None:
                        closed_start[fid] = now
                    elif now - closed_start[fid] > 3:
                        focus -= focus * 0.2
                        closed_start[fid] = None
                else:
                    closed_start[fid] = None

                # --- تحديث التركيز بناءً على الميل ---
                if tilt > 25:
                    movement_detected = True
                    if tilt_start[fid] is None:
                        tilt_start[fid] = now
                        focus -= focus * 0.2
                    elif now - tilt_start[fid] > 5:
                        focus -= focus * 0.2
                        tilt_start[fid] = now
                        tilt_recovery[fid] = True
                else:
                    if tilt_recovery.get(fid, False):
                        tilt_recovery[fid] = False
                        movement_detected = True
                    tilt_start[fid] = None

                # --- استعادة التركيز تدريجياً ---
                if not movement_detected and not tilt_recovery.get(fid, False) and focus < 100:
                    focus += 0.3

                focus = max(0.0, min(100.0, focus))

                with focus_lock:
                    focus_dict[fid] = focus

                avg_focus += focus
                face_count += 1

                # --- رسم الصندوق والنسبة ---
                xs = [int(l.x * w) for l in landmarks]
                ys = [int(l.y * h) for l in landmarks]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)
                box_color = (0,0,255) if fid == highlighted_student_id else (0,255,0)
                cv2.rectangle(frame, (x_min-10, y_min-10), (x_max+10, y_max+10), box_color, 2)


                box_color = (0,0,255) if fid == highlighted_student_id else (0,255,0)
                cv2.rectangle(frame, (x_min-10, y_min-10), (x_max+10, y_max+10), box_color, 2)
                color = (0, 255, 0) if focus > 70 else (0,255,255) if focus > 40 else (0,0,255)
                cv2.putText(frame, f"Student {idx+1}: {focus:.0f}%", (x_min, y_min-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # --- متوسط الصف ---
        if face_count > 0:
            avg_focus /= face_count
            if avg_focus < 50 and not alert_played:
                try:
                    pygame.mixer.music.load(alert_sound)
                    pygame.mixer.music.play()
                except:
                    pass
                alert_played = True
            elif avg_focus >= 50:
                alert_played = False

           
        else:
            if time.time() - last_face_time > 0.4:
                cv2.putText(frame,"No Face Detected",(30,50),
                            cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),3)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')
"""
@app.route('/focus-data')
def focus_data():
    with focus_lock:
        students = [{"id": int(fid), "focus": round(float(focus_dict.get(fid, 100.0)), 1)}
                    for fid in sorted(focus_dict.keys())]
        overall = round(sum([s["focus"] for s in students]) / len(students), 1) if students else 100.0

        return jsonify({
            "students": students,
            "overall": overall
        })
"""
@app.route('/highlight_random')
def highlight_random():
    global highlighted_student_id
    if focus_dict:
        highlighted_student_id = np.random.choice(list(focus_dict.keys()))
    return {"selected": int(highlighted_student_id) if highlighted_student_id is not None else None}


@app.route("/report/<int:sess_id>")
def report(sess_id):
    return render_template("last_p.html", session_id=sess_id)

@app.route("/monitor/<course_code>")
def monitor(course_code):
    if 'email' not in session:
        return redirect(url_for('signin'))

    conn = get_db_connection()
    cursor = conn.cursor()
    
    # بجيب السكشن بس لأن الكود (course_code) معي أصلاً
    cursor.execute("SELECT section FROM courses WHERE c_code = ?", (course_code,))
    course_data = cursor.fetchone()
    conn.close()

    # إذا لقى السكشن بياخده، إذا ما لقى بحط نص افتراضي
    section = course_data['section'] if course_data else "Sec 1"

    # بنبعث الكود والسكشن للـ HTML
    return render_template("index.html", course_code=course_code, section=section)
# الصفحة الأولى
@app.route('/f_page')
def f_page():
    return render_template('f_page.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form.get('fullname')
        email = request.form.get('email')
        password = request.form.get('password')
        # تشفير الباسورد قبل التخزين
        hashed_password = generate_password_hash(password)

        conn = get_db_connection()
        try:
            conn.execute('INSERT INTO instructors (email, fullname, password) VALUES (?, ?, ?)',
                         (email, fullname, hashed_password))
            conn.commit()
            return redirect(url_for('signin'))
        except: return "Email already exists!"
        finally: conn.close()  
    return render_template('signup.html')
# صفحة تسجيل الدخول
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM instructors WHERE email = ?', (email,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            # هون السر: لازم تستخدمي نفس الأسماء في الدالتين
            session['email'] = user['email']      # كانت instructor_email
            session['fullname'] = user['fullname'] # كانت instructor_name
            return redirect(url_for('show_courses'))
        
        return "Invalid email or password"
    return render_template('signin.html')
# صفحة الكورسات
@app.route('/courses')
def show_courses():
    # تأكدي إن الاسم 'email' بطابق اللي كتبناه فوق في السيشين
    if 'email' not in session:
        return redirect(url_for('signin'))

    instructor_email = session['email']
    full_name = session['fullname'] 

    conn = get_db_connection() # استخدمي الدالة اللي إنتِ معرفيتها فوق
    cursor = conn.cursor()
    
    cursor.execute("SELECT * FROM courses WHERE I_email = ?", (instructor_email,))
    user_courses = cursor.fetchall()
    conn.close()

    return render_template('courses.html', fullname=full_name, courses=user_courses)


@app.route('/focus-data')
def focus_data():
    with focus_lock:
        students = [{"id": int(fid), "focus": round(float(f), 1)} for fid, f in focus_dict.items()]
        overall = round(sum([s["focus"] for s in students]) / len(students), 1) if students else 100.0
    return jsonify({"students": students, "overall": overall})
# صفحة التاريخ
@app.route('/history')
def history():
    return render_template('history.html')

# صفحة تفاصيل المحاضرة
@app.route('/lectuers-details') # أو /lecture-details
def lecture_details():
    # تأكدي إن الاسم هون يطابق اسم الملف في مجلد templates بالملي
    return render_template('lecture-details.html')
# صفحة التقرير
@app.route('/report-page')
def report_page():
    return render_template('last_p.html')
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signin'))
if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
