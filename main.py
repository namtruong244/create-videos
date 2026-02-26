import os
import random
import itertools
import concurrent.futures
from config import INPUT_DIR, TEMP_DIR, OUTPUT_DIR
from modules.utils import setup_directories, cleanup_directory
from modules.video_processor import process_single_clip
from modules.video_merger import merge_clips_task
#from modules.downloader import download_video
#from modules.google_services import get_tasks_from_sheet, upload_video_to_drive


def main():
    # 1. Khởi tạo thư mục
    setup_directories([INPUT_DIR, TEMP_DIR, OUTPUT_DIR])

    # 2. Đọc kịch bản từ Google Sheet (Sắp triển khai)
    # tasks = get_tasks_from_sheet("link_sheet_cua_ban")

    # [GIẢ LẬP DỮ LIỆU TỪ SHEET CHO TỚI KHI CÓ API]
    tasks = [
        {"url": "link_tiktok_1", "text": "Vay nu xep ly"},
        # ...
    ]

    for task in tasks:
        dynamic_text = task['text']
        video_url = task['url']

        # 3. Tải video bằng yt-dlp
        # downloaded_file = download_video(video_url)
        # Nếu chưa xong API, code sẽ lấy file có sẵn trong INPUT_DIR như cũ
        input_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(('.mp4', '.mov', '.avi'))]

        # 4. Xử lý video (Che mặt, cắt 15s)
        all_15s_clips = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
            results = executor.map(process_single_clip, input_files)
            for sub_clips in results:
                all_15s_clips.extend(sub_clips)

        # 5. Tổ hợp và Ghép video
        if len(all_15s_clips) >= 4:
            all_possible_videos = list(itertools.combinations(all_15s_clips, 4))
            random.shuffle(all_possible_videos)

            actual_target = min(random.randint(20, 30), len(all_possible_videos))

            combo_tasks = []
            for i, combo in enumerate(all_possible_videos[:actual_target]):
                combo_tasks.append((i, combo, dynamic_text))  # Truyền text từ Sheet vào đây

            with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
                executor.map(merge_clips_task, combo_tasks)

            # 6. Upload lên Google Drive (Sắp triển khai)
            # for out_file in os.listdir(OUTPUT_DIR):
            #     upload_video_to_drive(os.path.join(OUTPUT_DIR, out_file), "DRIVE_FOLDER_ID")

        # 7. Dọn dẹp sau mỗi Task
        cleanup_directory(TEMP_DIR)
        # cleanup_directory(INPUT_DIR) # Có thể xóa luôn video gốc nếu muốn tiết kiệm ổ cứng


if __name__ == '__main__':
    main()
