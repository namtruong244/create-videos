import os
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip, clips_array, vfx, CompositeVideoClip, ImageClip
from config import OUTPUT_DIR, FONT_PATH, RENDER_CODEC

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
        final_clip.write_videofile(
            out_path,
            codec=RENDER_CODEC,
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
