import os
import time
import glob
import uiautomator2 as u2

# ================= CẤU HÌNH =================
LOCAL_OUTPUT_DIR = "outputs"
TIKTOK_PKG = "com.ss.android.ugc.trill"  # Gói ứng dụng TikTok VN/Quốc tế
ANDROID_TEMP_VIDEO = "/sdcard/DCIM/Camera/auto_draft_temp.mp4"  # Đường dẫn lưu tạm trên Mi 8 SE


def clean_android_temp_files():
    """Bước 0: Dọn dẹp rác trên điện thoại trước khi bắt đầu để tránh bấm nhầm"""
    print("[Hệ thống] Đang dọn dẹp thư viện ảnh trên điện thoại...")
    os.system(f"adb shell rm -f {ANDROID_TEMP_VIDEO}")
    # Xóa thêm bộ nhớ cache mờ (thumbnail) nếu có để Gallery cập nhật chuẩn xác
    os.system("adb shell rm -rf /sdcard/DCIM/.thumbnails/*")
    time.sleep(1)


def upload_to_draft(d, local_video_path, video_index, total_videos):
    """Quy trình xử lý 1 video duy nhất"""
    file_name = os.path.basename(local_video_path)
    print(f"\n[{video_index}/{total_videos}] Đang xử lý video: {file_name}")

    try:
        # 1. BƠM ĐẠN: Đẩy file vào điện thoại
        print("  -> Đang đẩy file vào Mi 8 SE...")
        # Dùng dấu ngoặc kép bọc đường dẫn phòng trường hợp tên file có dấu cách
        push_cmd = f'adb push "{local_video_path}" "{ANDROID_TEMP_VIDEO}"'
        os.system(push_cmd)

        # 2. ĐÁNH THỨC GALLERY: Ép Android nhận diện file ngay lập tức
        print("  -> Đang quét thư viện ảnh...")
        scan_cmd = f'adb shell am broadcast -a android.intent.action.MEDIA_SCANNER_SCAN_FILE -d file://{ANDROID_TEMP_VIDEO}'
        os.system(scan_cmd)
        time.sleep(2)  # Đợi 2s cho Android xử lý xong

        # 3. NẠP ĐẠN (UI AUTOMATION): Mở TikTok và thao tác
        print("  -> Mở TikTok (Khởi động lại app để tránh kẹt giao diện cũ)...")
        d.app_start(TIKTOK_PKG, stop=True)
        time.sleep(6)  # Đợi trang chủ TikTok load xong

        # Bấm [+] (Dùng tọa độ giữa đáy màn hình)
        print("  -> Bấm nút [+]")
        d.click(0.5, 0.972)
        time.sleep(2)

        # Bấm [Tải lên / Upload]
        print("  -> Bấm nút [Tải lên]")
        d.click(0.076, 0.93)
        time.sleep(2)

        # Bấm chọn video đầu tiên (Tọa độ ô đầu tiên góc trái trên cùng)
        print("  -> Chọn video đầu tiên")
        d.click	(0.291, 0.165)
        time.sleep(1)

        # Bấm [Tiếp / Next] lần 1
        print("  -> Tìm và bấm nút Next (1)...")
        # Dùng textContains để tóm gọn mọi nút có chữ "Next"
        if d(textContains="Next").wait(timeout=5.0):
            print("Click Next")
            d(textContains="Next").click()
        else:
            print("  ⚠️ Cảnh báo: Không tìm thấy chữ Next. Đang thử bấm tọa độ góc dưới phải...")
            # Backup: Nếu mờ text, bấm cưỡng chế vào góc dưới cùng bên phải (vị trí mặc định của nút Next)
            d.click(0.732, 0.96)

        # Đợi TikTok xử lý/nén video (Có thể mất thời gian)
        print("  -> Đợi TikTok xử lý video...")
        time.sleep(6)

        # Bấm [Tiếp / Next] lần 2 ở màn hình edit
        print("  -> Bấm [Tiếp] sang trang Đăng...")
        if d(textContains="Next").wait(timeout=10.0):
            d(textContains="Next").click()
        else:
            print("  ⚠️ Không thấy chữ Next lần 2. Bấm cưỡng chế góc phải dưới...")
            d.click(0.85, 0.95)
        time.sleep(3)

        # Bấm [Bản nháp / Drafts]
        print("  -> Bấm Lưu [Bản nháp]...")
        if d(text="Drafts").wait(timeout=5.0):
            d(text="Drafts").click()
            print("  ✅ Đã lưu vào Bản nháp thành công!")
        else:
            raise Exception("Không tìm thấy nút Bản nháp")

        # Đợi 2s để TikTok hoàn tất việc lưu vào bộ nhớ cục bộ
        time.sleep(2)

    except Exception as e:
        print(f"  ❌ Lỗi khi xử lý video {file_name}: {e}")

    finally:
        # 4. DỌN RÁC: Luôn luôn xóa file trên điện thoại dù thành công hay lỗi
        print("  -> Đang dọn dẹp file trên điện thoại...")
        os.system(f"adb shell rm -f {ANDROID_TEMP_VIDEO}")
        time.sleep(1)


if __name__ == '__main__':
    # Kiểm tra thư mục outputs
    if not os.path.exists(LOCAL_OUTPUT_DIR):
        print(f"Lỗi: Không tìm thấy thư mục '{LOCAL_OUTPUT_DIR}' trên máy Mac.")
        exit()

    # Lấy danh sách tất cả file mp4
    video_files = glob.glob(os.path.join(LOCAL_OUTPUT_DIR, "*.mp4"))
    total_vids = len(video_files)

    if total_vids == 0:
        print(f"Thư mục '{LOCAL_OUTPUT_DIR}' đang trống. Không có video nào để xử lý.")
        exit()

    print(f"Tìm thấy {total_vids} video. Đang kết nối với Mi 8 SE...")

    try:
        # Kết nối với thiết bị Android
        d = u2.connect()
        print(f"Kết nối thành công! Thiết bị: {d.info.get('brand')} {d.info.get('model')}")

        # Bật sáng màn hình nếu đang tắt
        d.screen_on()

        # Dọn dẹp máy trước khi chạy
        clean_android_temp_files()

        # Chạy vòng lặp từng video
        for i, video_path in enumerate(video_files, 1):
            upload_to_draft(d, video_path, i, total_vids)

            # Nghỉ 3 giây giữa các video cho app xả RAM
            time.sleep(3)

        print("\n🎉 HOÀN THÀNH CHIẾN DỊCH! TẤT CẢ VIDEO ĐÃ LÊN DRAFT.")

    except Exception as e:
        print(f"\n❌ Lỗi kết nối thiết bị: {e}")
        print("Vui lòng kiểm tra lại cáp kết nối và đã bật USB Debugging chưa.")