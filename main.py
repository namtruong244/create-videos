import os
import random
import itertools
import uuid
import concurrent.futures
from config import INPUT_DIR, TEMP_DIR, OUTPUT_DIR, SHEET_ID, DRIVE_FOLDER_ID
from modules.utils import setup_directories, cleanup_directory
from modules.video_processor import process_single_clip
from modules.video_merger import merge_clips_task
from modules.downloader import download_video
from modules.google_services import get_tasks_from_sheet, upload_video_to_drive, update_row_status, create_drive_folder, update_row_folder_link, update_row_direct_links


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

            target_videos = 17

            actual_target = min(target_videos, len(all_possible_videos))

            combo_tasks = []
            for i, combo in enumerate(all_possible_videos[:actual_target]):
                combo_tasks.append((i, combo, product_text))

            with concurrent.futures.ProcessPoolExecutor(max_workers=4) as executor:
                executor.map(merge_clips_task, combo_tasks)

            print(f"[Hệ thống] Hoàn thành render {actual_target} video cho '{product_text}'.")

            print(f"\n[Hệ thống] Bắt đầu đẩy video của '{product_text}' lên Drive...")

            # Xử lý tên thư mục an toàn (bỏ các ký tự dễ gây lỗi hệ thống)
            safe_product_name = product_text.replace("/", "_").replace("\\", "_")

            # 1. Tạo folder con dành riêng cho sản phẩm này
            sub_folder_id, sub_folder_link = create_drive_folder(uuid.uuid4().hex, DRIVE_FOLDER_ID)

            if sub_folder_id:
                output_files = [f for f in os.listdir(OUTPUT_DIR) if f.endswith('.mp4')]
                direct_download_links = []  # Tạo mảng chứa link tải trực tiếp

                for out_file in output_files:
                    file_path = os.path.join(OUTPUT_DIR, out_file)
                    new_file_path = os.path.join(OUTPUT_DIR, f"{safe_product_name}_{out_file}")
                    os.rename(file_path, new_file_path)

                    # Lấy ID file trả về
                    file_id, view_link = upload_video_to_drive(new_file_path, sub_folder_id)

                    if file_id:
                        # Tạo link tải trực tiếp (Direct Link) thần thánh của Google Drive
                        direct_link = f"https://drive.google.com/uc?export=download&id={file_id}"
                        direct_download_links.append(direct_link)

                # Gộp các link lại, cách nhau bằng dấu Xuống dòng (\n)
                all_links_str = "\n".join(direct_download_links)

                # Cập nhật Sheet
                update_row_status(SHEET_ID, row_idx, f"Done ({actual_target} videos)") # Cot F
                update_row_folder_link(SHEET_ID, row_idx, sub_folder_link)  # Cột C
                update_row_direct_links(SHEET_ID, row_idx, all_links_str)  # Cột D (MỚI)

            else:
                update_row_status(SHEET_ID, row_idx, "Lỗi: Không tạo được thư mục trên Drive")

        else:
            update_row_status(SHEET_ID, row_idx, "Error: Không đủ clip 15s")

    print("\n🎉 Done!")
    cleanup_directory(INPUT_DIR)
    cleanup_directory(TEMP_DIR)
    cleanup_directory(OUTPUT_DIR)

if __name__ == '__main__':
    main()
