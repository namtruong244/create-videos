import yt_dlp
import os
import time
import random
from config import INPUT_DIR


def download_video(url):
    """Tải video siêu cấp, chống block và tự động retry"""
    print(f"\n[Tải xuống] Bắt đầu xử lý: {url}")

    ydl_opts = {
        # 1. Quản lý File
        'outtmpl': os.path.join(INPUT_DIR, '%(id)s.%(ext)s'),
        # Ưu tiên lấy MP4 chất lượng tốt nhất, nếu không được thì lấy cái tốt nhất có sẵn
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',

        # 2. Xử lý mạng chập chờn (Retry)
        'retries': 10,  # Thử lại 10 lần nếu rớt kết nối
        'fragment_retries': 10,  # Thử lại 10 lần cho từng mảnh video nhỏ
        'socket_timeout': 30,  # Chờ tối đa 30s cho mỗi request

        # 3. Lách hệ thống Anti-Bot (Rất quan trọng)
        'http_headers': {
            # Giả dạng trình duyệt Google Chrome trên Windows
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7',
        },

        # 4. Tránh bị văng lỗi dừng toàn bộ script
        'ignoreerrors': True,  # Bỏ qua lỗi (hữu ích nếu tải playlist có video bị ẩn)
        'no_warnings': True,

        # --- CÁC TÙY CHỌN NÂNG CAO (Mở comment nếu cần) ---
        # Lấy cookie từ trình duyệt (Bắt buộc nếu tải video Facebook Group kín hoặc video TikTok bị giới hạn)
        # 'cookiesfrombrowser': ('chrome',), # Có thể đổi 'chrome' thành 'safari', 'edge', 'firefox'

        # Khắc phục lỗi API riêng của TikTok
        'extractor_args': {
            'tiktok': {'api_hostname': 'api22-normal-c-useast1a.tiktokv.com'}
        }
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # Chỉ extract info trước để kiểm tra
            info = ydl.extract_info(url, download=True)

            if info is None:
                print(f"[Lỗi Tải xuống] Bị chặn hoặc URL không hợp lệ: {url}")
                return None

            # Xử lý trường hợp URL là một playlist/series
            if 'entries' in info:
                # Nếu là playlist, ta lấy video đầu tiên (hoặc bạn có thể loop để lấy hết)
                info = info['entries'][0]

            # Lấy đường dẫn file dự kiến
            filename = ydl.prepare_filename(info)

            # Kiểm tra xem file có thực sự tồn tại không (yt-dlp đôi khi đổi đuôi .webm/.mkv sau khi gộp)
            if not os.path.exists(filename):
                base, _ = os.path.splitext(filename)
                for ext in ['.mp4', '.mkv', '.webm']:
                    if os.path.exists(base + ext):
                        filename = base + ext
                        break

            print(f"[Tải xuống] Thành công: {filename}")

            # Ngủ một giấc ngẫu nhiên 2 - 5 giây trước khi tải video tiếp theo để tránh bị khóa IP
            sleep_time = random.uniform(2, 5)
            print(f"[Hệ thống] Tạm nghỉ {sleep_time:.1f}s để tránh bị block IP...")
            time.sleep(sleep_time)

            return filename

    except Exception as e:
        print(f"[Lỗi Tải xuống] Gặp sự cố cực mạnh với {url} - Chi tiết: {e}")
        return None