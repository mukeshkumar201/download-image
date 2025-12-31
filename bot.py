import os
import io
import requests
import random
import time
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
from google.oauth2.credentials import Credentials

# --- Configuration ---
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('REFRESH_TOKEN')
DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID')

HISTORY_FILE = "posted_urls.txt"
SOURCE_URL = "https://www.pornpics.com/tags/indian-pussy/"
WATERMARK_TEXT = "freepornx.site"

def get_drive_service():
    info = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
    }
    creds = Credentials.from_authorized_user_info(info)
    return build('drive', 'v3', credentials=creds)

def add_watermark(image_content):
    try:
        img = Image.open(io.BytesIO(image_content)).convert("RGB")
        draw = ImageDraw.Draw(img)
        width, height = img.size
        font_size = int(width / 20)
        
        # GitHub Actions (Ubuntu) ke liye multiple font paths check karna
        font = None
        paths = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
            "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf"
        ]
        for path in paths:
            if os.path.exists(path):
                font = ImageFont.truetype(path, font_size)
                break
        
        if not font:
            print("⚠️ Custom font nahi mila, default use kar raha hoon.")
            font = ImageFont.load_default()

        text_bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
        tw, th = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
        x, y = width - tw - 30, height - th - 30

        draw.text((x+2, y+2), WATERMARK_TEXT, fill="black", font=font)
        draw.text((x, y), WATERMARK_TEXT, fill="white", font=font)
        
        img_byte_arr = io.BytesIO()
        img.save(img_byte_arr, format='JPEG', quality=85)
        return img_byte_arr.getvalue()
    except Exception as e:
        print(f"❌ Watermark Error: {e}")
        return None

def upload_to_drive(service, image_data, filename):
    try:
        file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaIoBaseUpload(io.BytesIO(image_data), mimetype='image/jpeg')
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return file.get('id')
    except Exception as e:
        print(f"❌ Drive Upload Error: {e}")
        return None

def main():
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, DRIVE_FOLDER_ID]):
        print("❌ Secrets missing!")
        return

    service = get_drive_service()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    if not os.path.exists(HISTORY_FILE):
        open(HISTORY_FILE, "w").close()
    
    with open(HISTORY_FILE, "r") as f:
        posted = set(f.read().splitlines())

    print(f"--- Scraping started. History has {len(posted)} images. ---")
    
    try:
        r = requests.get(SOURCE_URL, headers=headers, timeout=30)
        soup = BeautifulSoup(r.text, 'html.parser')
        links = [a['href'] for a in soup.find_all('a', href=True) if "/galleries/" in a['href']]
        random.shuffle(links)
    except Exception as e:
        print(f"❌ Scrape Error: {e}"); return

    count = 0
    for gal_link in links:
        if count >= 10: break
        full_gal = gal_link if gal_link.startswith('http') else "https://www.pornpics.com" + gal_link
        
        try:
            res = requests.get(full_gal, headers=headers, timeout=30)
            gal_soup = BeautifulSoup(res.text, 'html.parser')
            imgs = [img.get('data-src') or img.get('src') for img in gal_soup.find_all('img') if "pornpics.com" in (img.get('data-src') or img.get('src', ''))]
            
            for img_url in imgs:
                if count >= 10: break
                full_img = img_url if img_url.startswith('http') else "https:" + img_url
                
                if full_img in posted: continue

                print(f"Trying image {count+1}: {full_img}")
                img_res = requests.get(full_img, timeout=30)
                
                if img_res.status_code == 200:
                    # 1. Watermark lagao
                    final_data = add_watermark(img_res.content)
                    if final_data is None:
                        print("⚠️ Skipping: Watermark failed.")
                        continue
                    
                    # 2. Upload karo
                    filename = f"desi_{int(time.time())}_{count}.jpg"
                    file_id = upload_to_drive(service, final_data, filename)
                    
                    if file_id:
                        with open(HISTORY_FILE, "a") as f:
                            f.write(full_img + "\n")
                        posted.add(full_img)
                        print(f"✅ Success: {filename}")
                        count += 1
                        time.sleep(2)
                    else:
                        print("⚠️ Skipping: Upload failed.")
                else:
                    print(f"⚠️ Skipping: Image Download Error (Status {img_res.status_code})")
        except Exception as e:
            print(f"❌ Gallery Loop Error: {e}")
            continue

if __name__ == "__main__":
    main()
