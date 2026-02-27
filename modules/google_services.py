import os
import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import CREDENTIALS_FILE

# Cấp quyền truy cập cho cả Sheet và Drive
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def get_tasks_from_sheet(sheet_url_or_id, sheet_name="Sheet1"):
    print("[Google API] Đang kết nối và đọc Google Sheet...")
    try:
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(credentials)

        if "http" in sheet_url_or_id:
            sheet = client.open_by_url(sheet_url_or_id).worksheet(sheet_name)
        else:
            sheet = client.open_by_key(sheet_url_or_id).worksheet(sheet_name)

        data = sheet.get_all_values()
        tasks = []

        for i, row in enumerate(data):
            if i == 0: continue  # Bỏ qua dòng 1 (Header)

            # Tính toán số thứ tự dòng thực tế trên Sheet (gspread bắt đầu từ 1)
            row_index = i + 1

            # Kiểm tra xem dòng đó đã có trạng thái "Hoàn thành" chưa, nếu có rồi thì bỏ qua không làm lại
            status = row[2].strip() if len(row) > 2 else ""
            if len(status) != 0:
                continue

            if len(row) >= 2:
                product_name = row[0].strip()
                links_raw = row[1]
                video_links = [link.strip() for link in links_raw.split(';') if link.strip()]

                if product_name and video_links:
                    tasks.append({
                        'row_index': row_index,  # <-- Lưu lại vị trí dòng
                        'text': product_name,
                        'urls': video_links
                    })

        print(f"[Google API] Đã lấy thành công {len(tasks)} sản phẩm cần xử lý.")
        return tasks

    except Exception as e:
        print(f"[Lỗi Google Sheet] Không thể đọc dữ liệu: {e}")
        return []

def update_row_status(sheet_url_or_id, row_index, status_text, sheet_name="Sheet1"):
    """Ghi trạng thái vào cột C (Cột số 3) của dòng đang xử lý"""
    try:
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        client = gspread.authorize(credentials)

        if "http" in sheet_url_or_id:
            sheet = client.open_by_url(sheet_url_or_id).worksheet(sheet_name)
        else:
            sheet = client.open_by_key(sheet_url_or_id).worksheet(sheet_name)

        # Cập nhật ô ở tọa độ (row_index, 3). 3 tương đương với cột C
        sheet.update_cell(row_index, 3, status_text)
        print(f"[Google Sheet] Đã cập nhật trạng thái dòng {row_index} -> '{status_text}'")
    except Exception as e:
        print(f"[Lỗi Google Sheet] Không thể cập nhật trạng thái dòng {row_index}: {e}")

def upload_video_to_drive(file_path, folder_id):
    """Upload video thành phẩm lên Google Drive"""
    file_name = os.path.basename(file_path)
    print(f"[Google Drive] Đang tải '{file_name}' lên drive...")
    try:
        credentials = Credentials.from_service_account_file(CREDENTIALS_FILE, scopes=SCOPES)
        service = build('drive', 'v3', credentials=credentials)

        file_metadata = {
            'name': file_name,
            'parents': [folder_id]  # ID của thư mục Drive bạn muốn lưu
        }
        # resumable=True giúp upload file lớn không bị lỗi mạng giữa chừng
        media = MediaFileUpload(file_path, mimetype='video/mp4', resumable=True)

        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()

        print(f"[Google Drive] Thành công! Link xem: {file.get('webViewLink')}")
        return file.get('webViewLink')
    except Exception as e:
        print(f"[Lỗi Google Drive] Upload thất bại file {file_name}: {e}")
        return None