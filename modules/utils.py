import os
import shutil

def overlay_transparent(background, overlay, x, y):
    """Hàm dán ảnh PNG có nền trong suốt đè lên video frame"""
    bg_h, bg_w, _ = background.shape
    h, w, _ = overlay.shape

    if x >= bg_w or y >= bg_h or x + w <= 0 or y + h <= 0:
        return background

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

def setup_directories(dirs):
    """Tạo thư mục nếu chưa tồn tại"""
    for d in dirs:
        os.makedirs(d, exist_ok=True)

def cleanup_directory(dir_path):
    """Xóa sạch nội dung trong thư mục"""
    try:
        shutil.rmtree(dir_path)
        os.makedirs(dir_path, exist_ok=True)
        print(f"[Hệ thống] - Đã dọn dẹp sạch sẽ thư mục '{dir_path}'")
    except Exception as e:
        print(f"[Cảnh báo] - Có lỗi khi dọn dẹp thư mục {dir_path}: {e}")