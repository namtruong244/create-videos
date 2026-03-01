import os
import cv2
import mediapipe as mp
from moviepy.editor import VideoFileClip
from config import INPUT_DIR, TEMP_DIR, ICON_PATH
from modules.utils import overlay_transparent

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
    mp_face_detection = mp.solutions.face_detection
    face_detection = mp_face_detection.FaceDetection(
        model_selection=1,
        min_detection_confidence=0.35
    )

    try:
        clip = VideoFileClip(input_path).without_audio()

        # ================= THÊM BƯỚC PHÓNG TO & CẮT TÂM =================
        # 1. Lưu lại kích thước chuẩn ban đầu (VD: 1080x1920)
        original_w, original_h = clip.w, clip.h

        # 2. Hệ số phóng to (1.15 tương đương phóng to 15%)
        # Không nên để quá to (như 1.5) vì sẽ làm mờ video và mất nhân vật ở rìa
        zoom_factor = 1.15

        # 3. Phóng to toàn bộ video
        zoomed_clip = clip.resize(zoom_factor)

        # 4. Xén lấy hình chữ nhật ở giữa, ép lại về đúng kích thước gốc
        clip_processed = zoomed_clip.crop(
            x_center=zoomed_clip.w / 2,
            y_center=zoomed_clip.h / 2,
            width=original_w,
            height=original_h
        )
        # ================= CẤU HÌNH LÀM MƯỢT (SMOOTHING) =================
        # Biến lưu trạng thái vị trí cũ (dùng dictionary để lưu state trong hàm fl)
        smooth_config = {
            'last_x': None, 'last_y': None,
            'last_w': None, 'last_h': None,
            'frames_lost': 0  # Đếm số frame bị mất dấu mặt
        }

        # Hệ số làm mượt (ALPHA). Giá trị từ 0.1 đến 1.0
        # 0.1: Rất mượt nhưng icon sẽ "đuổi theo" mặt chậm (lag).
        # 0.9: Ít mượt hơn nhưng bám sát mặt nhanh.
        # 0.3 là mức cân bằng tốt cho tự nhiên.
        tracked_faces = []
        ALPHA = 0.3
        MAX_FRAMES_LOST = 5  # Nếu mất dấu mặt quá 5 frames thì mới ẩn icon đi

        def process_frame_smooth(get_frame, t):
            frame = get_frame(t).copy()
            ih, iw, _ = frame.shape
            results = face_detection.process(frame)

            current_detections = []

            # 1. Lấy TẤT CẢ các khuôn mặt trong frame hiện tại
            if results.detections:
                for detection in results.detections:
                    bboxC = detection.location_data.relative_bounding_box
                    raw_w, raw_h = int(bboxC.width * iw), int(bboxC.height * ih)
                    raw_x, raw_y = int(bboxC.xmin * iw), int(bboxC.ymin * ih)
                    padding = int(raw_w * 0.25)

                    target_w, target_h = raw_w + padding * 2, raw_h + padding * 2
                    target_x, target_y = max(0, raw_x - padding), max(0, raw_y - padding)

                    # Tính tâm của khuôn mặt để lát nữa ghép cặp
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

                    # Tính khoảng cách giữa tâm mặt cũ và tâm mặt mới
                    dist = (tracked['cx'] - det['cx']) ** 2 + (tracked['cy'] - det['cy']) ** 2

                    # Nếu khoảng cách đủ gần (cùng là 1 người) -> Ghép cặp
                    if dist < (tracked['w'] * 2) ** 2 and dist < min_dist:
                        min_dist = dist
                        best_match = det

                if best_match:
                    # Nếu tìm thấy người cũ, áp dụng làm mượt (EMA)
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
                    # Nếu không thấy mặt cũ đâu (người đó quay đi), tăng biến đếm
                    tracked['frames_lost'] += 1

            # 3. Thêm những người MỚI xuất hiện vào danh sách theo dõi
            for det in current_detections:
                if not det['matched']:
                    tracked_faces.append({
                        'x': det['x'], 'y': det['y'], 'w': det['w'], 'h': det['h'],
                        'cx': det['cx'], 'cy': det['cy'],
                        'frames_lost': 0, 'matched': True
                    })

            # 4. Lọc và Vẽ Icon lên toàn bộ các khuôn mặt còn hoạt động
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

            # Cập nhật lại danh sách theo dõi cho frame tiếp theo
            tracked_faces.clear()
            tracked_faces.extend(active_faces)

            return frame

        # Áp dụng hàm xử lý mượt
        processed_clip = clip_processed.fl(process_frame_smooth)

        # --- (Phần code cắt 15s giữ nguyên như cũ từ đây trở xuống) ---
        duration = processed_clip.duration
        clip_intervals = []  # Danh sách chứa các mốc thời gian (start, end) cần cắt

        # Trường hợp 1: Video dài từ 20s đến dưới 30s
        if 20 < duration < 30:
            clip_intervals.append((0, 15))
            # Lấy lùi lại từ đuôi video để đủ tròn 15s
            clip_intervals.append((duration - 15, duration))

        # Trường hợp 2: Video dài trên 30s
        elif duration >= 30:
            # Lấy trước các đoạn 15s chẵn
            num_full_clips = int(duration // 15)
            for i in range(num_full_clips):
                start_t = i * 15
                clip_intervals.append((start_t, start_t + 15))

            # Xử lý đoạn thời gian dư thừa ở cuối (remainder)
            remainder = duration % 15
            # Nếu đoạn dư từ 10s trở lên (tức là chỉ thiếu <= 5s)
            if remainder >= 10:
                # Cắt một đoạn lấy từ sát rạt đuôi video lùi lại 15s
                clip_intervals.append((duration - 15, duration))

        # Trường hợp 3: Video dài từ 15s đến 20s (Chỉ lấy được 1 đoạn đầu)
        elif duration >= 15:
            clip_intervals.append((0, 15))

        else:
            print(f"[{file_name}] - Hệ thống bỏ qua do video quá ngắn ({duration:.1f}s)")

        # ================= TIẾN HÀNH CẮT VÀ RENDER =================
        clip_paths = []
        for start_t, end_t in clip_intervals:
            # Làm tròn tên file để tránh lỗi lưu file có quá nhiều số thập phân
            out_name = f"{file_name.split('.')[0]}_part_{int(start_t)}.mp4"
            out_path = os.path.join(TEMP_DIR, out_name)

            print(f"[{file_name}] - Hệ thống: Đang cắt đoạn {start_t:.1f}s -> {end_t:.1f}s")

            part_clip = processed_clip.subclip(start_t, end_t)
            # Dùng CPU render đoạn nhỏ (ultrafast) cho an toàn và ổn định luồng âm/hình
            part_clip.write_videofile(out_path, codec="libx264", preset="ultrafast", audio=False, verbose=False,
                                      logger=None)

            clip_paths.append(out_path)
            part_clip.close()

        # Đóng clip gốc giải phóng RAM
        clip.close()
        return clip_paths

    except Exception as e:
        print(f"[Lỗi] Xử lý file {file_name} thất bại: {e}")
        import traceback
        traceback.print_exc()
        return []