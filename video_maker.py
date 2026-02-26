import os
import random
import itertools
import concurrent.futures
import cv2
import mediapipe as mp
from PIL import Image, ImageDraw, ImageFont
import numpy as np
from moviepy.editor import VideoFileClip, clips_array, vfx, CompositeVideoClip, ImageClip
import shutil

# ================= CẤU HÌNH THƯ MỤC & THÔNG SỐ =================
INPUT_DIR = "inputs"  # Thư mục chứa các clip gốc (20s - 1p)
TEMP_DIR = "processed_15s"  # Thư mục chứa các đoạn 15s đã cắt và che mặt
OUTPUT_DIR = "outputs"  # Thư mục chứa video thành phẩm 2x2
ICON_PATH = "icon.png"  # File ảnh icon trong suốt (PNG) để che mặt

# Tạo thư mục nếu chưa có
for d in [INPUT_DIR, TEMP_DIR, OUTPUT_DIR]:
    os.makedirs(d, exist_ok=True)


# ================= HÀM XỬ LÝ LÕI =================

def overlay_transparent(background, overlay, x, y):
    """Hàm dán ảnh PNG có nền trong suốt đè lên video frame"""
    bg_h, bg_w, _ = background.shape
    h, w, _ = overlay.shape

    if x >= bg_w or y >= bg_h or x + w <= 0 or y + h <= 0:
        return background

    # Cắt phần bị tràn ra ngoài khung hình
    c_y1, c_x1 = max(0, -y), max(0, -x)
    c_y2, c_x2 = min(h, bg_h - y), min(w, bg_w - x)
    y1, x1 = max(0, y), max(0, x)
    y2, x2 = min(bg_h, y + h), min(bg_w, x + w)

    alpha_s = overlay[c_y1:c_y2, c_x1:c_x2, 3] / 255.0
    alpha_l = 1.0 - alpha_s

    for c in range(3):
        background[y1:y2, x1:x2, c] = (alpha_s * overlay[c_y1:c_y2, c_x1:c_x2, c] +
                                       alpha_l * background[y1:y2, x1:x2, c])
    return background


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


def merge_clips_task(combo_data):
    """Bước 3: Ghép 4 clip dọc thành 1 video 9:16 chuẩn (Lưới 2x2)"""
    combo_id, clip_paths, dynamic_text = combo_data
    out_path = os.path.join(OUTPUT_DIR, f"final_output_{combo_id}.mp4")

    try:
        print(f"[Worker {combo_id}] - Hệ thống: Đang ghép 4 video TikTok thành lưới 2x2...")

        # 1. Resize chính xác về 540x960 (Tỷ lệ 9:16 thu nhỏ)
        c1 = VideoFileClip(clip_paths[0]).resize((540, 960))
        c2 = VideoFileClip(clip_paths[1]).resize((540, 960))
        c3 = VideoFileClip(clip_paths[2]).resize((540, 960))
        c4 = VideoFileClip(clip_paths[3]).resize((540, 960))

        # Áp dụng filter chống bản quyền màu sắc
        light_filter = lambda c: c.fx(vfx.colorx, random.uniform(0.95, 1.05))
        c1, c2, c3, c4 = map(light_filter, [c1, c2, c3, c4])

        # 2. Ghép thành lưới 2x2.
        # Tổng kích thước lúc này sẽ tự động khít 1080x1920
        final_grid = clips_array([[c1, c2], [c3, c4]])

        font_absolute_path = os.path.abspath("DancingScript.ttf")

        # 3. Tạo dòng chữ ở giữa
        txt_clip = create_text_clip_pil(
            text=dynamic_text,
            font_path=font_absolute_path,
            initial_font_size=80,
            color=(255, 255, 255),
            stroke_color=(0, 0, 0),
            stroke_width=5,
            duration=final_grid.duration
        )

        # Căn giữa màn hình
        if txt_clip is not None:
            txt_clip = txt_clip.set_position('center')
            final_clip = CompositeVideoClip([final_grid, txt_clip])
        else:
            final_clip = final_grid

        # ================= RENDER =================
        import platform
        # Tự động nhận diện Hackintosh để dùng VideoToolbox
        render_codec = "h264_videotoolbox" if platform.system() == 'Darwin' else "libx264"

        final_clip.write_videofile(
            out_path,
            codec=render_codec,
            audio=False,
            bitrate="4000k",
            verbose=False,
            logger=None
        )

        # Dọn dẹp RAM
        for c in [c1, c2, c3, c4, final_grid, txt_clip, final_clip]:
            c.close()

        print(f"[Worker {combo_id}] - Hệ thống: Render thành công! Lưu tại {out_path}")
    except Exception as e:
        print(f"[Worker {combo_id}] - Lỗi: Không thể ghép video. Chi tiết: {e}")


def create_text_clip_pil(text, font_path, initial_font_size, color, stroke_color, stroke_width, duration,
                         max_width=1000):
    """
    Hàm tự tạo chữ xịn xò bằng Pillow:
    - Tự động thu nhỏ cỡ chữ nếu text quá dài so với max_width
    - Có viền chữ (stroke)
    - Có hộp nền bo tròn bán trong suốt (rounded background box)
    """
    # Cấu hình UI hộp nền
    padding_x = 40
    padding_y = 20
    box_radius = 30
    box_color = (0, 0, 0, 180)

    font_size = initial_font_size
    dummy_img = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy_img)

    # ================= VÒNG LẶP TỰ ĐỘNG THU NHỎ CHỮ =================
    while True:
        try:
            font = ImageFont.truetype(font_path, font_size)
        except IOError:
            print(f"[Lỗi Font] - Không thể đọc file font tại: {font_path}")
            return None

        # Đo thử kích thước chữ với font_size hiện tại
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_width)
        text_w = bbox[2] - bbox[0]

        # Kích thước chiều ngang của cả hộp
        canvas_w = text_w + padding_x * 2

        # Nếu chiều ngang nhỏ hơn max_width (1000px) HOẶC font đã quá nhỏ (ví dụ 30) thì dừng lại
        if canvas_w <= max_width or font_size <= 30:
            text_h = bbox[3] - bbox[1]
            canvas_h = text_h + padding_y * 2
            break

        # Nếu vẫn bị tràn, giảm cỡ chữ đi 2 đơn vị và đo lại
        font_size -= 2
    # ================================================================

    # Tạo ảnh nền trong suốt với kích thước chuẩn vừa chốt
    img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # BƯỚC 1: Vẽ hộp nền bo tròn
    draw.rounded_rectangle(
        [(0, 0), (canvas_w, canvas_h)],
        radius=box_radius,
        fill=box_color
    )

    # BƯỚC 2: Vẽ chữ có viền chồng lên trên
    text_draw_x = padding_x - bbox[0]
    text_draw_y = padding_y - bbox[1]

    draw.text(
        (text_draw_x, text_draw_y),
        text,
        font=font,
        fill=color,
        stroke_width=stroke_width,
        stroke_fill=stroke_color
    )

    # Chuyển sang format cho MoviePy
    img_array = np.array(img)
    txt_clip = ImageClip(img_array).set_duration(duration)
    return txt_clip


# ================= ORCHESTRATOR QUẢN LÝ LUỒNG =================

if __name__ == '__main__':
    input_text = "Vay nu xep ly"


    # BƯỚC 1: Quét file đầu vào
    input_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(('.mp4', '.mov', '.avi'))]
    all_15s_clips = []

    print(f"Bắt đầu xử lý {len(input_files)} video gốc...")

    # BƯỚC 2: Xử lý che mặt và cắt 15s (Mở 8 luồng chạy song song)
    with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
        results = executor.map(process_single_clip, input_files)
        for sub_clips in results:
            all_15s_clips.extend(sub_clips)

    print(f"Đã tạo ra tổng cộng {len(all_15s_clips)} clip 15s nhỏ.")

    # BƯỚC 3: Tạo danh sách các video thành phẩm không trùng lặp NỘI DUNG
    if len(all_15s_clips) >= 4:
        # Dùng COMBINATIONS: 4 clip A-B-C-D xuất hiện cùng nhau sẽ chỉ được tính là 1 video duy nhất
        all_possible_videos = list(itertools.combinations(all_15s_clips, 4))

        # Xáo trộn danh sách để thứ tự render ngẫu nhiên
        random.shuffle(all_possible_videos)

        # Thiết lập mục tiêu render ngẫu nhiên từ 20 đến 30 video
        target_videos = random.randint(20, 30)
        actual_target = min(target_videos, len(all_possible_videos))

        print(f"[Hệ thống] - Đã tính toán được {len(all_possible_videos)} tổ hợp nội dung khác biệt 100%.")

        if actual_target < 20:
            print(
                "[Cảnh báo] - Số lượng video gốc hơi ít, không đủ để tạo ra 20 video. Hãy thêm video gốc vào thư mục 'inputs' ở lần chạy sau nhé!")

        print(f"[Hệ thống] - Sẽ tiến hành bốc ngẫu nhiên và render {actual_target} video...")

        tasks = []
        for i, combo in enumerate(all_possible_videos[:actual_target]):
            tasks.append((i, combo, input_text))

        # BƯỚC 4: Render ghép bằng Card Đồ Họa (Mở 4 luồng)
        with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
            executor.map(merge_clips_task, tasks)

        print(f"🎉 HOÀN THÀNH TOÀN BỘ WORKFLOW! Đã xuất xưởng {actual_target} video độc bản.")

        # ================= BƯỚC 5: DỌN DẸP RÁC =================
        print("\n[Hệ thống] - Đang tiến hành dọn dẹp các file video 15s tạm thời...")
        try:
            # Xóa toàn bộ thư mục tạm và các file bên trong
            shutil.rmtree(TEMP_DIR)
            # Tạo lại một thư mục trống rỗng để sẵn sàng cho lần chạy tiếp theo
            os.makedirs(TEMP_DIR, exist_ok=True)
            print(f"[Hệ thống] - Đã dọn dẹp sạch sẽ thư mục '{TEMP_DIR}'. Giải phóng thành công dung lượng ổ cứng!")
        except Exception as e:
            print(f"[Cảnh báo] - Có lỗi khi dọn dẹp thư mục tạm: {e}")
    else:
        print("Không đủ số lượng clip 15s để tạo thành 1 video 2x2.")