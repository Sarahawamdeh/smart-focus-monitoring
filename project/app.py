from flask import Flask, render_template, Response, jsonify
import cv2
import mediapipe as mp
import numpy as np
import time
import pygame
import json
import threading

app = Flask(__name__)

# --- إعداد الصوت ---
pygame.mixer.init()
alert_sound = "static/alert.mp3"
alert_played = False

# --- Mediapipe ---
mp_face_mesh = mp.solutions.face_mesh

# --- بيانات التركيز ---
focus_dict = {}      # key = fid (int), value = focus_percentage (float)
closed_start = {}
tilt_start = {}
tilt_recovery = {}
highlighted_student_id = None

# --- قفل لحماية الوصول المتزامن إلى focus_dict ---
focus_lock = threading.Lock()

# --- تايمر لمنع No Face سريع ---
last_face_time = time.time()

# --- كاميرا OpenCV ---
cap = cv2.VideoCapture(0)
cap.set(cv2.CAP_PROP_FRAME_WIDTH, 750)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 450)

# --- أنشئ FaceMesh مرة واحدة فقط ---
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

            # ترتيب للعرض (اختياري)
            faces_with_pos.sort(key=lambda x: x[0], reverse=True)

            for idx, (x_min, fid, face_landmarks) in enumerate(faces_with_pos):
                landmarks = face_landmarks.landmark

                # تأكد وجود مفاتيح الافتراضية
                if fid not in focus_dict:
                    with focus_lock:
                        focus_dict[fid] = 100.0
                    closed_start[fid] = None
                    tilt_start[fid] = None
                    tilt_recovery[fid] = False

                # اقرأ القيمة الحالية بأمان
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

                # عدّل القيمة في القاموس بأمان
                with focus_lock:
                    focus_dict[fid] = focus

                avg_focus += focus
                face_count += 1

                xs = [int(l.x * w) for l in landmarks]
                ys = [int(l.y * h) for l in landmarks]
                x_min, x_max = min(xs), max(xs)
                y_min, y_max = min(ys), max(ys)

                # رسم الصندوق والنسبة
                box_color = (0,0,255) if fid == highlighted_student_id else (0,255,0)
                cv2.rectangle(frame, (x_min-10, y_min-10), (x_max+10, y_max+10), box_color, 2)
                color = (0, 255, 0) if focus > 70 else (0,255,255) if focus > 40 else (0,0,255)
                cv2.putText(frame, f"Student {idx+1}: {focus:.0f}%", (x_min, y_min-10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        # --- متوسط الصف ---
        if face_count > 0:
            avg_focus /= face_count
            if avg_focus < 50:
                if not alert_played:
                    try:
                        pygame.mixer.music.load(alert_sound)
                        pygame.mixer.music.play()
                    except:
                        pass
                    alert_played = True
            else:
                alert_played = False

            cv2.rectangle(frame,(10,h-60),(300,h-20),(50,50,50),-1)
            cv2.putText(frame,f"Class Avg: {avg_focus:.1f}%",(20,h-30),
                        cv2.FONT_HERSHEY_SIMPLEX,0.8,(0,255,255),2)

        else:
            if time.time() - last_face_time > 0.4:
                cv2.putText(frame,"No Face Detected",(30,50),
                            cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,255),3)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame_bytes = buffer.tobytes()

        # لا تحتاج لإرسال overlay_data هنا لأن الواجهة ستجلبها من /focus-data
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/video_feed')
def video_feed():
    return Response(gen_frames(),
                    mimetype='multipart/x-mixed-replace; boundary=frame')

# --- endpoint لإرجاع نسب التركيز الحالية ---
@app.route('/focus-data')
def focus_data():
    with focus_lock:
        # حوّل القاموس إلى قائمة مرتبة لعرض (يمكن تغيير العدد حسب الحاجة)
        students = [{"id": int(fid), "focus": round(float(focus_dict.get(fid, 100.0)), 1)} for fid in sorted(focus_dict.keys())]
        overall = round(sum([s["focus"] for s in students]) / len(students), 1) if students else 100.0
        return jsonify({"students": students, "overall": overall})

@app.route('/highlight_random')
def highlight_random():
    global highlighted_student_id
    if focus_dict:
        highlighted_student_id = np.random.choice(list(focus_dict.keys()))
    return {"selected": int(highlighted_student_id) if highlighted_student_id is not None else None}

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000, debug=True)
