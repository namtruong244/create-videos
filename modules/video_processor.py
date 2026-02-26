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
        ALPHA = 0.3
        MAX_FRAMES_LOST = 5  # Nếu mất dấu mặt quá 5 frames thì mới ẩn icon đi

        def process_frame_smooth(get_frame, t):
            frame = get_frame(t).copy()
            ih, iw, _ = frame.shape
            results = face_detection.process(frame)

            target_x, target_y, target_w, target_h = None, None, None, None
            box_found = False

            # 1. Tìm tọa độ mục tiêu (Raw coords)
            if results.detections:
                box_found = True
                smooth_config['frames_lost'] = 0  # Reset bộ đếm mất dấu
                # Lấy khuôn mặt đầu tiên (hoặc to nhất)
                detection = results.detections[0]
                bboxC = detection.location_data.relative_bounding_box

                # Tính tọa độ thô và padding
                raw_w, raw_h = int(bboxC.width * iw), int(bboxC.height * ih)
                raw_x, raw_y = int(bboxC.xmin * iw), int(bboxC.ymin * ih)
                padding = int(raw_w * 0.25)  # Tăng padding lên một chút (25%) cho thoải mái

                target_w, target_h = raw_w + padding * 2, raw_h + padding * 2
                target_x, target_y = max(0, raw_x - padding), max(0, raw_y - padding)

            # 2. Áp dụng thuật toán làm mượt (EMA)
            current_x, current_y, current_w, current_h = None, None, None, None

            if box_found:
                # Nếu đây là frame đầu tiên tìm thấy mặt, khởi tạo ngay lập tức
                if smooth_config['last_x'] is None:
                    smooth_config['last_x'], smooth_config['last_y'] = target_x, target_y
                    smooth_config['last_w'], smooth_config['last_h'] = target_w, target_h
                else:
                    # Công thức EMA: Giá trị mới = Alpha * Mục tiêu + (1-Alpha) * Giá trị cũ
                    smooth_config['last_x'] = ALPHA * target_x + (1 - ALPHA) * smooth_config['last_x']
                    smooth_config['last_y'] = ALPHA * target_y + (1 - ALPHA) * smooth_config['last_y']
                    smooth_config['last_w'] = ALPHA * target_w + (1 - ALPHA) * smooth_config['last_w']
                    smooth_config['last_h'] = ALPHA * target_h + (1 - ALPHA) * smooth_config['last_h']
            else:
                # Nếu không thấy mặt, tăng bộ đếm
                smooth_config['frames_lost'] += 1

            # 3. Quyết định có vẽ icon không
            # Chỉ vẽ nếu đang có vị trí cũ VÀ chưa bị mất dấu quá lâu
            if smooth_config['last_x'] is not None and smooth_config['frames_lost'] < MAX_FRAMES_LOST:
                # Chuyển đổi về số nguyên để vẽ
                current_x = int(smooth_config['last_x'])
                current_y = int(smooth_config['last_y'])
                current_w = int(smooth_config['last_w'])
                current_h = int(smooth_config['last_h'])

                try:
                    # Đảm bảo kích thước resize hợp lệ (lớn hơn 0)
                    if current_w > 0 and current_h > 0:
                        resized_icon = cv2.resize(icon_img, (current_w, current_h), interpolation=cv2.INTER_LINEAR)
                        frame = overlay_transparent(frame, resized_icon, current_x, current_y)
                except Exception as e:
                    pass  # Bỏ qua lỗi resize frame lẻ tẻ

            return frame

        # Áp dụng hàm xử lý mượt
        processed_clip = clip_processed.fl(process_frame_smooth)

        # --- (Phần code cắt 15s giữ nguyên như cũ từ đây trở xuống) ---
        duration = int(processed_clip.duration)
        clip_paths = []
        # ... (phần còn lại của hàm giữ nguyên) ...
        for start_t in range(0, duration, 15):
            end_t = start_t + 15
            if end_t <= duration:
                part_clip = processed_clip.subclip(start_t, end_t)
                out_name = f"{file_name.split('.')[0]}_part_{start_t}.mp4"
                out_path = os.path.join(TEMP_DIR, out_name)
                # Dùng preset ultrafast để cắt nhanh hơn chút
                part_clip.write_videofile(out_path, codec="libx264", preset="ultrafast", audio=False,
                                          verbose=False, logger=None)
                clip_paths.append(out_path)

        clip_processed.close()
        clip.close()
        return clip_paths

    except Exception as e:
        print(f"[Lỗi] Xử lý file {file_name} thất bại: {e}")
        import traceback
        traceback.print_exc()
        return []