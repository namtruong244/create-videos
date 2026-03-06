import os
import cv2
import mediapipe as mp
from moviepy.editor import VideoFileClip
from config import INPUT_DIR, TEMP_DIR, ICON_PATH
from modules.utils import overlay_transparent
import moviepy.video.fx.all as vfx


def process_single_clip(file_name):
    print(f"[Hệ thống]: Đang tiếp nhận và xử lý gốc - {file_name}")
    input_path = os.path.join(INPUT_DIR, file_name)

    # Chuẩn bị icon
    icon_img_bgra = cv2.imread(ICON_PATH, cv2.IMREAD_UNCHANGED)
    if icon_img_bgra is None or icon_img_bgra.shape[2] != 4:
        print(f"[Cảnh báo]: File {ICON_PATH} lỗi hoặc thiếu kênh Alpha. Bỏ qua.")
        return []
    icon_img = cv2.cvtColor(icon_img_bgra, cv2.COLOR_BGRA2RGBA)

    # Khởi tạo MediaPipe
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        max_num_faces=5,  # Hỗ trợ nhận diện tối đa 5 người trong 1 khung hình
        refine_landmarks=False,
        min_detection_confidence=0.5,  # Cứ để 0.5 vì lưới 468 điểm đã quá chính xác rồi
        min_tracking_confidence=0.5
    )

    try:
        clip = VideoFileClip(input_path).without_audio()

        # ================= THÊM BƯỚC PHÓNG TO & CẮT TÂM =================
        original_w, original_h = clip.w, clip.h
        zoom_factor = 1.15
        zoomed_clip = clip.resize(zoom_factor)

        clip_processed = zoomed_clip.crop(
            x_center=zoomed_clip.w / 2,
            y_center=zoomed_clip.h / 2,
            width=original_w,
            height=original_h
        )

        # ================= THÊM BƯỚC LẬT NGANG (MIRROR) =================
        print(f"[{file_name}] - Hệ thống: Đang lật ngang video (Mirror)...")
        clip_processed = clip_processed.fx(vfx.mirror_x)

        # ================= CẤU HÌNH LÀM MƯỢT (SMOOTHING) =================
        tracked_faces = []
        ALPHA = 0.3
        MAX_FRAMES_LOST = 5

        def process_frame_smooth(get_frame, t):
            frame = get_frame(t).copy()
            ih, iw, _ = frame.shape
            # Lấy lưới khuôn mặt từ Face Mesh
            # Lưu ý: MoviePy truyền frame dạng RGB, MediaPipe FaceMesh cũng đọc RGB nên rất khớp
            results = face_mesh.process(frame)

            current_detections = []

            if results.multi_face_landmarks:
                for face_landmarks in results.multi_face_landmarks:

                    # 1. Trích xuất tất cả tọa độ X và Y của 468 điểm
                    x_coords = [landmark.x * iw for landmark in face_landmarks.landmark]
                    y_coords = [landmark.y * ih for landmark in face_landmarks.landmark]

                    # 2. Tìm điểm biên để tạo thành cái hộp (Bounding Box)
                    raw_xmin = int(min(x_coords))
                    raw_xmax = int(max(x_coords))
                    raw_ymin = int(min(y_coords))
                    raw_ymax = int(max(y_coords))

                    # Tính chiều rộng và chiều cao thực tế
                    raw_w = raw_xmax - raw_xmin
                    raw_h = raw_ymax - raw_ymin

                    # Bỏ qua những mặt quá nhỏ (nhỏ hơn 3% khung hình)
                    if raw_w < iw * 0.03:
                        continue

                    raw_x = raw_xmin
                    raw_y = raw_ymin

                    # 3. Tính toán Padding và mở rộng Icon như cũ
                    padding = int(raw_w * 0.25)
                    target_w, target_h = raw_w + padding * 2, raw_h + padding * 2
                    target_x, target_y = max(0, raw_x - padding), max(0, raw_y - padding)

                    cx, cy = target_x + target_w / 2, target_y + target_h / 2

                    current_detections.append({
                        'x': target_x, 'y': target_y, 'w': target_w, 'h': target_h,
                        'cx': cx, 'cy': cy, 'matched': False
                    })

            # 2. Ghép cặp (Matching) khuôn mặt cũ và mới
            for tracked in tracked_faces:
                tracked['matched'] = False
                best_match = None
                min_dist = float('inf')

                for det in current_detections:
                    if det['matched']: continue

                    dist = (tracked['cx'] - det['cx']) ** 2 + (tracked['cy'] - det['cy']) ** 2

                    if dist < (tracked['w'] * 2) ** 2 and dist < min_dist:
                        min_dist = dist
                        best_match = det

                if best_match:
                    tracked['x'] = ALPHA * best_match['x'] + (1 - ALPHA) * tracked['x']
                    tracked['y'] = ALPHA * best_match['y'] + (1 - ALPHA) * tracked['y']
                    tracked['w'] = ALPHA * best_match['w'] + (1 - ALPHA) * tracked['w']
                    tracked['h'] = ALPHA * best_match['h'] + (1 - ALPHA) * tracked['h']
                    tracked['cx'] = tracked['x'] + tracked['w'] / 2
                    tracked['cy'] = tracked['y'] + tracked['h'] / 2
                    tracked['frames_lost'] = 0
                    tracked['matched'] = True
                    best_match['matched'] = True
                else:
                    tracked['frames_lost'] += 1

            # 3. Thêm những người MỚI xuất hiện
            for det in current_detections:
                if not det['matched']:
                    tracked_faces.append({
                        'x': det['x'], 'y': det['y'], 'w': det['w'], 'h': det['h'],
                        'cx': det['cx'], 'cy': det['cy'],
                        'frames_lost': 0, 'matched': True
                    })

            # 4. Vẽ Icon
            active_faces = []
            for tracked in tracked_faces:
                if tracked['frames_lost'] < MAX_FRAMES_LOST:
                    active_faces.append(tracked)

                    current_x, current_y = int(tracked['x']), int(tracked['y'])
                    current_w, current_h = int(tracked['w']), int(tracked['h'])

                    if current_w > 0 and current_h > 0:
                        try:
                            resized_icon = cv2.resize(icon_img, (current_w, current_h), interpolation=cv2.INTER_LINEAR)
                            frame = overlay_transparent(frame, resized_icon, current_x, current_y)
                        except Exception:
                            pass

            tracked_faces.clear()
            tracked_faces.extend(active_faces)

            return frame

        # Áp dụng hàm xử lý mượt
        processed_clip = clip_processed.fl(process_frame_smooth)

        # --- PHẦN CẮT THỜI GIAN GIỮ NGUYÊN ---
        duration = processed_clip.duration
        clip_intervals = []

        if 20 < duration < 30:
            clip_intervals.append((0, 15))
            clip_intervals.append((duration - 15, duration))
        elif duration >= 30:
            num_full_clips = int(duration // 15)
            for i in range(num_full_clips):
                start_t = i * 15
                clip_intervals.append((start_t, start_t + 15))
            remainder = duration % 15
            if remainder >= 10:
                clip_intervals.append((duration - 15, duration))
        elif duration >= 15:
            clip_intervals.append((0, 15))
        else:
            print(f"[{file_name}] - Hệ thống bỏ qua do video quá ngắn ({duration:.1f}s)")

        # ================= TIẾN HÀNH CẮT VÀ RENDER =================
        clip_paths = []
        for start_t, end_t in clip_intervals:
            out_name = f"{file_name.split('.')[0]}_part_{int(start_t)}.mp4"
            out_path = os.path.join(TEMP_DIR, out_name)

            print(f"[{file_name}] - Hệ thống: Đang cắt đoạn {start_t:.1f}s -> {end_t:.1f}s")

            part_clip = processed_clip.subclip(start_t, end_t)
            part_clip.write_videofile(out_path, codec="libx264", preset="ultrafast", audio=False, verbose=False,
                                      logger=None)

            clip_paths.append(out_path)
            part_clip.close()

        clip.close()
        return clip_paths

    except Exception as e:
        print(f"[Lỗi] Xử lý file {file_name} thất bại: {e}")
        import traceback
        traceback.print_exc()
        return []