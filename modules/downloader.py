# import yt_dlp
# import os
# from config import INPUT_DIR
#
# def download_video(url):
#     """Tải video từ link (YouTube, TikTok, Facebook...) về thư mục INPUT_DIR"""
#     print(f"[Tải xuống] Bắt đầu tải: {url}")
#     ydl_opts = {
#         'outtmpl': os.path.join(INPUT_DIR, '%(id)s.%(ext)s'),
#         'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
#     }
#     try:
#         with yt_dlp.YoutubeDL(ydl_opts) as ydl:
#             info = ydl.extract_info(url, download=True)
#             filename = ydl.prepare_filename(info)
#             print(f"[Tải xuống] Thành công: {filename}")
#             return filename
#     except Exception as e:
#         print(f"[Lỗi Tải xuống] {url} - {e}")
#         return None