import os
import platform

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Thư mục
INPUT_DIR = os.path.join(BASE_DIR, "inputs")
TEMP_DIR = os.path.join(BASE_DIR, "processed_15s")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")

# Tài nguyên
ICON_PATH = os.path.join(BASE_DIR, "icon.png")
FONT_PATH = os.path.join(BASE_DIR, "DancingScript.ttf")

# Google API
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")

# Tự động nhận diện Hackintosh/Mac để dùng VideoToolbox, nếu Linux/Docker thì dùng libx264
RENDER_CODEC = "h264_videotoolbox" if platform.system() == 'Darwin' else "libx264"

SHEET_ID = "1cdxmFAD4Ogr_WCNSTQdgQkEb6RK0IaHP_gT_l7Xzhm4"

DRIVE_FOLDER_ID = "1qvqsZ-QDOIM7tmK5t2AkqmlQc8_JnwBN"
