import os
import random
import itertools
import concurrent.futures
from config import INPUT_DIR, TEMP_DIR, OUTPUT_DIR, SHEET_ID, DRIVE_FOLDER_ID
from modules.utils import setup_directories, cleanup_directory
from modules.video_processor import process_single_clip
from modules.video_merger import merge_clips_task
from modules.downloader import download_video
from modules.google_services import get_tasks_from_sheet, upload_video_to_drive, update_row_status


def main():
    # 1. Khởi tạo thư mục
    setup_directories([INPUT_DIR, TEMP_DIR, OUTPUT_DIR])

    # 2. Đọc kịch bản từ Google Sheet (Sắp triển khai)
    tasks = get_tasks_from_sheet(SHEET_ID)

    if not tasks:
        print("[Hệ thống] Không có dữ liệu trong Sheet hoặc lỗi kết nối. Dừng chương trình.")
        return

    for task_idx, task in enumerate(tasks, start=1):
        product_text = task['text']
        video_urls = task['urls']
        row_idx = task['row_index']

        print(f"\n{'=' * 50}")
        print(f"BẮT ĐẦU XỬ LÝ SẢN PHẨM {task_idx}/{len(tasks)}: '{product_text}'")
        print(f"{'=' * 50}")

        update_row_status(SHEET_ID, row_idx, "Processing...")

        # Bước 3.1: Dọn sạch INPUT và OUTPUT cũ để tránh lẫn lộn giữa các sản phẩm
        cleanup_directory(INPUT_DIR)
        cleanup_directory(TEMP_DIR)
        cleanup_directory(OUTPUT_DIR)

        # Bước 3.2: Tải toàn bộ video của sản phẩm này về
        for url in video_urls:
            download_video(url)

        # Quét các file vừa tải
        input_files = [f for f in os.listdir(INPUT_DIR) if f.endswith(('.mp4', '.mov', '.avi'))]
        if not input_files:
            print(f"[Cảnh báo] Không tải được video nào cho '{product_text}'. Bỏ qua sản phẩm này.")
            update_row_status(SHEET_ID, row_idx, "Error")
            continue

        # 4. Xử lý video (Che mặt, cắt 15s)
        all_15s_clips = []
        with concurrent.futures.ProcessPoolExecutor(max_workers=8) as executor:
            results = executor.map(process_single_clip, input_files)
            for sub_clips in results:
                all_15s_clips.extend(sub_clips)

        print(f"[Hệ thống] Đã thu thập được {len(all_15s_clips)} đoạn 15s làm nguyên liệu.")

        # 5. Tổ hợp và Ghép video
        if len(all_15s_clips) >= 4:
            all_possible_videos = list(itertools.combinations(all_15s_clips, 4))
            random.shuffle(all_possible_videos)

            actual_target = min(random.randint(20, 30), len(all_possible_videos))

            combo_tasks = []
            for i, combo in enumerate(all_possible_videos[:actual_target]):
                combo_tasks.append((i, combo, product_text))

            with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
                executor.map(merge_clips_task, combo_tasks)

            print(f"[Hệ thống] Hoàn thành render {actual_target} video cho '{product_text}'.")

            output_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.mp4')]
            for out_file in output_files:
                file_path = os.path.join(OUTPUT_DIR, out_file)
                # Đổi tên file để dễ quản lý trên Drive (VD: Váy_Nữ_Xếp_Ly_video_0.mp4)
                safe_product_name = product_text.replace(" ", "_")
                new_file_path = os.path.join(OUTPUT_DIR, f"{safe_product_name}_{out_file}")
                os.rename(file_path, new_file_path)

                upload_video_to_drive(new_file_path, DRIVE_FOLDER_ID)

            update_row_status(SHEET_ID, row_idx, f"Done ({actual_target} videos)")

        else:
            update_row_status(SHEET_ID, row_idx, "Error: Không đủ clip 15s")

    print("\n🎉 Done!")
    cleanup_directory(INPUT_DIR)
    cleanup_directory(TEMP_DIR)
    cleanup_directory(OUTPUT_DIR)

if __name__ == '__main__':
    main()
