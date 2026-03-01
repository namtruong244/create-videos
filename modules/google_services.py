import os
import gspread
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import CLIENT_SECRET_FILE, TOKEN_FILE

# Cấp quyền truy cập cho cả Sheet và Drive
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]


def authenticate():
    """Xác thực bằng OAuth 2.0 (Thay cho Service Account)"""
    creds = None
    # Nếu đã có token lưu từ lần đăng nhập trước
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    # Nếu chưa có token hoặc token đã hết hạn
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Mở trình duyệt để người dùng tự đăng nhập và cấp quyền
            print("\n[Google API] Trình duyệt sẽ mở ra. Vui lòng đăng nhập tài khoản Google của bạn...")
            flow = InstalledAppFlow.from_client_secrets_file(
                CLIENT_SECRET_FILE, SCOPES)
            creds = flow.run_local_server(port=0)

        # Lưu token lại cho những lần chạy script sau
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    return creds


def get_tasks_from_sheet(sheet_url_or_id, sheet_name="Sheet1"):
    print("[Google API] Đang kết nối và đọc Google Sheet...")
    try:
        creds = authenticate()
        client = gspread.authorize(creds)

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
            status = row[3].strip() if len(row) > 2 else ""
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
        creds = authenticate()
        client = gspread.authorize(creds)

        if "http" in sheet_url_or_id:
            sheet = client.open_by_url(sheet_url_or_id).worksheet(sheet_name)
        else:
            sheet = client.open_by_key(sheet_url_or_id).worksheet(sheet_name)

        # Cập nhật ô ở tọa độ (row_index, 3). 3 tương đương với cột C
        sheet.update_cell(row_index, 6, status_text)
        print(f"[Google Sheet] Đã cập nhật trạng thái dòng {row_index} -> '{status_text}'")
    except Exception as e:
        print(f"[Lỗi Google Sheet] Không thể cập nhật trạng thái dòng {row_index}: {e}")


def upload_video_to_drive(file_path, folder_id):
    """Upload video thành phẩm lên Google Drive"""
    file_name = os.path.basename(file_path)
    print(f"[Google Drive] Đang tải '{file_name}' lên drive...")
    try:
        creds = authenticate()
        service = build('drive', 'v3', credentials=creds)

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
        return file.get('id'), file.get('webViewLink')
    except Exception as e:
        print(f"[Lỗi Google Drive] Upload thất bại file {file_name}: {e}")
        return None


def create_drive_folder(folder_name, parent_folder_id):
    """Tạo một thư mục con trên Drive và trả về ID cùng Link của thư mục đó"""
    print(f"[Google Drive] Đang tạo thư mục riêng: '{folder_name}'...")
    try:
        credentials = authenticate()
        service = build('drive', 'v3', credentials=credentials)

        file_metadata = {
            'name': folder_name,
            'mimeType': 'application/vnd.google-apps.folder',
            'parents': [parent_folder_id]
        }

        folder = service.files().create(
            body=file_metadata,
            fields='id, webViewLink'
        ).execute()

        print(f"[Google Drive] Đã tạo thư mục thành công! Link: {folder.get('webViewLink')}")
        return folder.get('id'), folder.get('webViewLink')
    except Exception as e:
        print(f"[Lỗi Google Drive] Không thể tạo thư mục '{folder_name}': {e}")
        return None, None


def update_row_folder_link(sheet_url_or_id, row_index, folder_link, sheet_name="Sheet1"):
    """Ghi link thư mục vào cột D (Cột số 4) của dòng đang xử lý"""
    try:
        credentials = authenticate()
        client = gspread.authorize(credentials)

        if "http" in sheet_url_or_id:
            sheet = client.open_by_url(sheet_url_or_id).worksheet(sheet_name)
        else:
            sheet = client.open_by_key(sheet_url_or_id).worksheet(sheet_name)

        # 4 tương đương với cột D
        sheet.update_cell(row_index, 3, folder_link)
        print(f"[Google Sheet] Đã chèn link Drive vào cột D cho dòng {row_index}.")
    except Exception as e:
        print(f"[Lỗi Google Sheet] Không thể chèn link ở dòng {row_index}: {e}")

def update_row_direct_links(sheet_url_or_id, row_index, links_text, sheet_name="Sheet1"):
    """Ghi danh sách link tải trực tiếp vào cột E (Cột số 5)"""
    try:
        credentials = authenticate()
        client = gspread.authorize(credentials)
        sheet = client.open_by_url(sheet_url_or_id).worksheet(sheet_name) if "http" in sheet_url_or_id else client.open_by_key(sheet_url_or_id).worksheet(sheet_name)
        sheet.update_cell(row_index, 4, links_text)
    except Exception as e:
        pass