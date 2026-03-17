import os
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Thư mục
INPUT_DIR = "/Volumes/RAMDisk/inputs"
TEMP_DIR = "/Volumes/RAMDisk/processed_15s"
OUTPUT_DIR = "/Volumes/RAMDisk/outputs"

# Tài nguyên
ICONS_DIR = "icons"  # Thư mục chứa các icon
FONTS_DIR = "fonts"  # Thư mục chứa các font chữ
ICON_PATH = os.path.join(BASE_DIR, "icon.png")
FONT_PATH = os.path.join(BASE_DIR, "DancingScript.ttf")

# Google API
CLIENT_SECRET_FILE = os.path.join(BASE_DIR, "client_secret.json")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")

# Tự động nhận diện Hackintosh/Mac để dùng VideoToolbox, nếu Linux/Docker thì dùng libx264
RENDER_CODEC = "h264_videotoolbox" if platform.system() == 'Darwin' else "libx264"

SHEET_ID = "1cdxmFAD4Ogr_WCNSTQdgQkEb6RK0IaHP_gT_l7Xzhm4"

DRIVE_FOLDER_ID = "1qvqsZ-QDOIM7tmK5t2AkqmlQc8_JnwBN"
