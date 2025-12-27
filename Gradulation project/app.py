from flask import Flask, render_template, Response, jsonify, request, redirect, url_for, session
import cv2
import mediapipe as mp
import numpy as np
import time
import pygame
import threading
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'yu_smart_focus_secret'

# ---------------- DATABASE ----------------
def get_db_connection():
    conn = sqlite3.connect('smart_focus.db')
    conn.row_factory = sqlite3.Row
    return conn

# ---------------- SOUND ----------------
pygame.mixer.init()
alert_sound = "static/alert.mp3"
alert_played = False

# ---------------- MEDIAPIPE ----------------
mp_face_mesh = mp.solutions.face_mesh
mp_face_detection = mp.solutions.face_detection

mesh = mp_face_mesh.FaceMesh(
    refine_landmarks=True,
    max_num_faces=5,
    min_detection_confidence=0.7,
    min_tracking_confidence=0.7
)

face_detector = mp_face_detection.FaceDetection(
    model_selection=1,
    min_detection_confidence=0.7
)

# ---------------- GLOBALS ----------------
focus_dict = {}
closed_start = {}
tilt_start = {}
tilt_recovery = {}
highlighted_student_id = None
focus_lock = threading.Lock()
last_face_time = time.time()
is_monitoring = False  # هاد المفتاح اللي رح يطفي ويشغل الكاميرا

# ---------------- CAMERA ----------------
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 750)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 450)

# ---------------- GENERATOR ----------------
def gen_frames():
    global alert_played, last_face_time, highlighted_student_id, is_monitoring
    while is_monitoring:  # بدل True خليها تعتمد على المفتاح
        ret, frame = cap.read()
        if not ret:
            break
            

        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        detections = face_detector.process(rgb)

        avg_focus = 0
        face_count = 0

        if detections.detections:
            last_face_time = time.time()
            faces_with_pos = []

            for fid, detection in enumerate(detections.detections):
                bbox = detection.location_data.relative_bounding_box
                x_min = int(bbox.xmin * w)
                y_min = int(bbox.ymin * h)
                box_w = int(bbox.width * w)
                box_h = int(bbox.height * h)

                # ---- فلترة الأجسام الصغيرة (إيد / أشياء) ----
                if box_w < 80 or box_h < 80:
                    continue

                face_roi = rgb[y_min:y_min + box_h, x_min:x_min + box_w]
                if face_roi.size == 0:
                    continue

                face_res = mesh.process(face_roi)
                if not face_res.multi_face_landmarks:
                    continue

                faces_with_pos.append((x_min, fid, face_res.multi_face_landmarks[0], x_min, y_min, box_w, box_h))

            faces_with_pos.sort(key=lambda x: x[0], reverse=True)

            for idx, (x_sort, fid, face_landmarks, x_min, y_min, box_w, box_h) in enumerate(faces_with_pos):

                if fid not in focus_dict:
                    with focus_lock:
                        focus_dict[fid] = 100.0
                    closed_start[fid] = None
                    tilt_start[fid] = None
                    tilt_recovery[fid] = False

                with focus_lock:
                    focus = focus_dict.get(fid, 100.0)

                landmarks = face_landmarks.landmark
                movement_detected = False
                now = time.time()

                # --------- العين ---------
                left_eye_idx = [33,160,158,133,153,144]
                right_eye_idx = [362,385,387,263,373,380]

                def eye_aspect_ratio(eye_landmarks, w, h):
                    p = [(int(l.x * w), int(l.y * h)) for l in eye_landmarks]
                    v1 = np.linalg.norm(np.array(p[1]) - np.array(p[5]))
                    v2 = np.linalg.norm(np.array(p[2]) - np.array(p[4]))
                    h1 = np.linalg.norm(np.array(p[0]) - np.array(p[3]))
                    return (v1 + v2) / (2.0 * h1)

                left_eye = [landmarks[i] for i in left_eye_idx]
                right_eye = [landmarks[i] for i in right_eye_idx]

                ear = (eye_aspect_ratio(left_eye, box_w, box_h) +
                       eye_aspect_ratio(right_eye, box_w, box_h)) / 2.0

                # ---- فلترة ذكية (إيد مستحيل تمر) ----
                if ear < 0.1 or ear > 0.4:
                    continue

                # --------- ميل الرأس ---------
                def head_tilt(landmarks, w, h):
                    left = np.array([landmarks[234].x * w, landmarks[234].y * h])
                    right = np.array([landmarks[454].x * w, landmarks[454].y * h])
                    dx = right[0] - left[0]
                    dy = right[1] - left[1]
                    return abs(np.degrees(np.arctan2(dy, dx)))

                tilt = head_tilt(landmarks, box_w, box_h)

                # --------- منطق التركيز ---------
                if ear < 0.21:
                    movement_detected = True
                    if closed_start[fid] is None:
                        closed_start[fid] = now
                    elif now - closed_start[fid] > 3:
                        focus -= focus * 0.2
                        closed_start[fid] = None
                else:
                    closed_start[fid] = None

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

                if not movement_detected and not tilt_recovery.get(fid, False) and focus < 100:
                    focus += 0.3

                focus = max(0.0, min(100.0, focus))

                with focus_lock:
                    focus_dict[fid] = focus

                avg_focus += focus
                face_count += 1

                # --------- الرسم ---------
                box_color = (0,0,255) if fid == highlighted_student_id else (0,255,0)
                cv2.rectangle(frame,
                              (x_min-10, y_min-10),
                              (x_min+box_w+10, y_min+box_h+10),
                              box_color, 2)

                color = (0,255,0) if focus > 70 else (0,255,255) if focus > 40 else (0,0,255)
                cv2.putText(frame, f"Student {idx+1}: {focus:.0f}%",
                            (x_min, y_min-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # --------- متوسط الصف ---------
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
                cv2.putText(frame, "No Face Detected", (30,50),
                            cv2.FONT_HERSHEY_SIMPLEX, 1, (0,0,255), 3)

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

"""
@app.route("/report/<int:sess_id>")
def report(sess_id):
    return render_template("last_p.html", session_id=sess_id)
"""
@app.route("/monitor/<int:section_id>")
def monitor(section_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    conn = get_db_connection()
    # جلب معلومات المادة بناءً على رقم الشعبة
    course_data = conn.execute('''
        SELECT c.course_code, c.course_name, s.section_num
        FROM sections s
        JOIN courses c ON s.course_code = c.course_code
        WHERE s.section_id = ?
    ''', (section_id,)).fetchone()
    conn.close()

    if course_data:
        return render_template("index.html", 
                               course_code=course_data['course_code'], 
                               course_name=course_data['course_name'],
                               section=course_data['section_num'],
                               section_id=section_id)
    return "Section Not Found", 404
# الصفحة الأولى
@app.route('/f_page')
def f_page():
    return render_template('f_page.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        fullname = request.form['fullname']
        email = request.form['email']
        password = request.form['password']
        
        # الخطوة الأهم: تشفير كلمة السر قبل إرسالها للداتابيز
        hashed_password = generate_password_hash(password)
        
        conn = sqlite3.connect('smart_focus.db')
        cursor = conn.cursor()
        try:
            # نخزن hashed_password وليس password
            cursor.execute("INSERT INTO instructors (fullname, email, password) VALUES (?, ?, ?)", 
                           (fullname, email, hashed_password))
            conn.commit()
            return redirect(url_for('signin'))
        except sqlite3.IntegrityError:
            return "Email already exists!"
        finally:
            conn.close()
    return render_template('signup.html')
# صفحة تسجيل الدخول
@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        email = request.form['email']
        password_candidate = request.form['password']
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM instructors WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()

        # نتحقق: هل المستخدم موجود؟ وهل الهاش المخزن يطابق الكلمة المدخلة؟
        if user and check_password_hash(user['password'], password_candidate):
            session['user_id'] = user['ins_id']
            session['fullname'] = user['fullname']
            return redirect(url_for('show_courses'))
        else:
            # بدلاً من return نص عادي، نرجع الصفحة ومعها رسالة خطأ
            return render_template('signin.html', error="Invalid email or password")
            
    # هذا السطر مهم جداً: ليعرض الصفحة عند فتح الرابط أول مرة (GET)
    return render_template('signin.html')
# صفحة الكورسات
@app.route('/courses')
def show_courses():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    conn = get_db_connection()
    # جلب المواد والشعب التابعة لهذا الدكتور بالذات باستخدام الربط الجديد
    user_courses = conn.execute('''
        SELECT s.section_id, c.course_code, c.course_name, s.section_num
        FROM sections s
        JOIN courses c ON s.course_code = c.course_code
        WHERE s.ins_id = ?
    ''', (session['user_id'],)).fetchall()
    conn.close()

    return render_template('courses.html', fullname=session['fullname'], courses=user_courses)

@app.route('/focus-data')
def focus_data():
    with focus_lock:
        students = [{"id": int(fid), "focus": round(float(f), 1)} for fid, f in focus_dict.items()]
        overall = round(sum([s["focus"] for s in students]) / len(students), 1) if students else 100.0
    return jsonify({"students": students, "overall": overall})
# صفحة التاريخ
@app.route('/history/<int:section_id>')
def history(section_id):
    if 'user_id' not in session:
        return redirect(url_for('signin'))
    
    conn = get_db_connection()
    # جلب كل المحاضرات المسجلة لهي الشعبة
    sessions_list = conn.execute('''
        SELECT s.*, c.course_name, c.course_code 
        FROM sessions s
        JOIN sections sec ON s.section_id = sec.section_id
        JOIN courses c ON sec.course_code = c.course_code
        WHERE s.section_id = ?
        ORDER BY s.created_at DESC
    ''', (section_id,)).fetchall()
    conn.close()
    
    return render_template('history.html', sessions=sessions_list)

@app.route('/last-report')
def last_report():
    sess_id = request.args.get('id')
    conn = get_db_connection()
    
    # جلب بيانات المادة والشعبة
    report_data = conn.execute('''
        SELECT s.*, c.course_code, c.course_name, sec.section_num, sec.section_id
        FROM sessions s
        JOIN sections sec ON s.section_id = sec.section_id
        JOIN courses c ON sec.course_code = c.course_code
        WHERE s.session_id = ?
    ''', (sess_id,)).fetchone()

    # جلب بيانات الطلاب (تأكدي من الاسم focus_score)
    students_data = conn.execute('''
        SELECT st.student_name, fd.focus_score
        FROM student_focus_data fd
        JOIN students st ON fd.student_id = st.student_id
        WHERE fd.session_id = ?
    ''', (sess_id,)).fetchall()
    
    conn.close()
    return render_template('last_p.html', report=report_data, students=students_data)
# صفحة التقرير
@app.route('/report-page')
def lecture_details():
    if 'user_id' not in session:
        return redirect(url_for('signin'))

    sess_id = request.args.get('id')
    conn = get_db_connection()
    
    # التعديل الأول: أضفنا sec.section_id وأيضاً s.course_id (إذا كان مستخدماً في الروابط)
    report_data = conn.execute('''
        SELECT s.*, c.course_code, c.course_name, sec.section_num, sec.section_id
        FROM sessions s
        JOIN sections sec ON s.section_id = sec.section_id
        JOIN courses c ON sec.course_code = c.course_code
        WHERE s.session_id = ?
    ''', (sess_id,)).fetchone()

    # التعديل الثاني: حذفنا "as focus" ليبقى الاسم "focus_score" ليتطابق مع الـ HTML
    students_data = conn.execute('''
        SELECT st.student_name, fd.focus_score
        FROM student_focus_data fd
        JOIN students st ON fd.student_id = st.student_id
        WHERE fd.session_id = ?
    ''', (sess_id,)).fetchall()
    
    conn.close()

    if report_data:
        # تأكدي أن اسم الملف lecture-details.html (بالشرطة الوسطى) كما هو في مجلد templates
        return render_template('lecture-details.html', report=report_data, students=students_data)
    
    return "Report not found", 404

@app.route('/save_session', methods=['POST'])
def save_session():
    data = request.get_json()
    sec_id = data.get('course_id') 
    dur = data.get('duration', '00:00:00')
    avg = data.get('avg_focus', 0.0)
    students_list = data.get('students_data', []) 
    
    local_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. حفظ الجلسة
        cursor.execute('''
            INSERT INTO sessions (section_id, duration, avg_focus, created_at)
            VALUES (?, ?, ?, ?)
        ''', (sec_id, dur, avg, local_time))
        
        new_sess_id = cursor.lastrowid
        
        # 2. حفظ تفاصيل الطلاب (هنا التعديل)
        for s in students_list:
            cursor.execute("SELECT student_id FROM students WHERE student_name = ?", (s['name'],))
            row = cursor.fetchone()
            std_id = row['student_id'] if row else None

            # نأخذ s['focus'] من الجافاسكريبت ونخزنها في عمود focus_score
            cursor.execute('''
                INSERT INTO student_focus_data (session_id, student_id, focus_score)
                VALUES (?, ?, ?)
            ''', (new_sess_id, std_id, s['focus']))
        
        conn.commit()
        conn.close()
        return jsonify({"status": "success", "session_id": new_sess_id})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('signin'))
@app.route('/start_camera')
def start_camera():
    global is_monitoring, cap
    is_monitoring = True
    if not cap.isOpened():
        cap.open(0)
    return jsonify({"status": "camera started"})

@app.route('/stop_camera')
def stop_camera():
    global is_monitoring, cap
    is_monitoring = False
    # لإطفاء الضوء الأخضر نهائياً:
    if cap.isOpened():
        cap.release() 
    return jsonify({"status": "camera stopped"})

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
