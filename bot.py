import os
import io
import requests
import random
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

# --- Configuration ---
HISTORY_FILE = "posted_urls.txt"
SOURCE_URL = "https://www.pornpics.com/tags/indian-pussy/"
WATERMARK_TEXT = "freepornx.site"
DRIVE_FOLDER_ID = "YOUR_GOOGLE_DRIVE_FOLDER_ID" # Yahan apna Folder ID dalo

# Google Drive Scopes
SCOPES = ['https://www.googleapis.com/auth/drive.file']

def authenticate_drive():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('drive', 'v3', credentials=creds)

def add_watermark(image_content):
    img = Image.open(io.BytesIO(image_content)).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    # Font settings (Size adjustment)
    width, height = img.size
    font_size = int(width / 15)
    try:
        # Linux/GitHub Actions ke liye default font
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        font = ImageFont.load_default()

    # Position: Bottom Right
    text_bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    text_height = text_bbox[3] - text_bbox[1]
    x = width - text_width - 20
    y = height - text_height - 20

    # Shadow/Outline for visibility
    draw.text((x+2, y+2), WATERMARK_TEXT, fill="black", font=font)
    draw.text((x, y), WATERMARK_TEXT, fill="white", font=font)
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG')
    return img_byte_arr.getvalue()

def upload_to_drive(service, image_data, filename):
    file_metadata = {
        'name': filename,
        'parents': [DRIVE_FOLDER_ID]
    }
    media = MediaIoBaseUpload(io.BytesIO(image_data), mimetype='image/jpeg', resumable=True)
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"Uploaded to Drive: {filename} (ID: {file.get('id')})")

def main():
    service = authenticate_drive()
    print("--- Scraping 10 Images ---")
    
    headers = {'User-Agent': 'Mozilla/5.0'}
    r = requests.get(SOURCE_URL, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    
    # Get gallery links
    links = [a['href'] for a in soup.find_all('a', href=True) if "/galleries/" in a['href']]
    posted = open(HISTORY_FILE, "r").read().splitlines() if os.path.exists(HISTORY_FILE) else []
    
    count = 0
    random.shuffle(links)

    for gal_link in links:
        if count >= 10: break
        
        full_gal_url = gal_link if gal_link.startswith('http') else "https://www.pornpics.com" + gal_link
        r_gal = requests.get(full_gal_url, headers=headers)
        gal_soup = BeautifulSoup(r_gal.text, 'html.parser')
        
        imgs = [img.get('data-src') or img.get('src') for img in gal_soup.find_all('img') if "pornpics.com" in (img.get('data-src') or img.get('src', ''))]
        
        for img_url in imgs:
            if count >= 10: break
            full_img_url = img_url if img_url.startswith('http') else "https:" + img_url
            
            if full_img_url not in posted:
                try:
                    print(f"Processing: {full_img_url}")
                    img_data = requests.get(full_img_url).content
                    
                    # Add Watermark
                    watermarked_img = add_watermark(img_data)
                    
                    # Upload
                    upload_to_drive(service, watermarked_img, f"desi_item_{random.randint(1000,9999)}.jpg")
                    
                    # Update History
                    with open(HISTORY_FILE, "a") as f: f.write(full_img_url + "\n")
                    
                    count += 1
                    time.sleep(2)
                except Exception as e:
                    print(f"Error: {e}")

if __name__ == "__main__":
    main()
