import requests
import os
import time
import random
from config import INPUT_DIR


def download_video(tiktok_url):
    """
    Tải video TikTok (bao gồm cả link giỏ hàng) thông qua API trung gian.
    Video tải về sẽ KHÔNG CÓ LOGO (No Watermark).
    """
    print(f"[API] Đang phân tích link: {tiktok_url}")

    # API của TikWM (Miễn phí, chuyên bắt link TikTok App)
    api_endpoint = "https://www.tikwm.com/api/"

    try:
        # 1. Gửi link TikTok cho API "nhai" hộ
        response = requests.post(api_endpoint, data={'url': tiktok_url})
        data = response.json()

        # Code 0 nghĩa là API đã bẻ khóa thành công
        if data.get('code') == 0:
            video_info = data['data']
            video_id = video_info.get('id', 'unknown_id')

            # play: Link video chất lượng thường | hdplay: Link video HD (nếu có)
            mp4_url = video_info.get('hdplay') or video_info.get('play')

            print(f"[API] Đã lấy được link gốc (No Watermark)! Đang tải về...")

            # 2. Bắt đầu tải file MP4 từ link gốc về máy
            output_path = os.path.join(INPUT_DIR, f"tiktok_{video_id}.mp4")

            # Dùng stream=True để tải mượt những file dung lượng lớn
            vid_response = requests.get(mp4_url, stream=True)
            vid_response.raise_for_status()  # Kiểm tra xem tải có bị lỗi mạng không

            with open(output_path, 'wb') as file:
                for chunk in vid_response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)

            print(f"✅ THÀNH CÔNG: Đã lưu tại '{output_path}'")

            # Ngủ một giấc ngẫu nhiên 2 - 5 giây trước khi tải video tiếp theo để tránh bị khóa IP
            sleep_time = random.uniform(2, 5)
            print(f"[Hệ thống] Tạm nghỉ {sleep_time:.1f}s để tránh bị block IP...")
            time.sleep(sleep_time)

            return output_path

        else:
            print(f"❌ Lỗi từ API: {data.get('msg')}")
            return None

    except requests.exceptions.RequestException as e:
        print(f"❌ Lỗi kết nối mạng: {e}")
        return None
    except Exception as e:
        print(f"❌ Lỗi không xác định: {e}")
        return None
