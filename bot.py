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

# --- Configuration (GitHub Secrets se data uthayega) ---
CLIENT_ID = os.environ.get('CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET')
REFRESH_TOKEN = os.environ.get('REFRESH_TOKEN')
DRIVE_FOLDER_ID = os.environ.get('DRIVE_FOLDER_ID')

HISTORY_FILE = "posted_urls.txt"
SOURCE_URL = "https://www.pornpics.com/tags/indian-pussy/"
WATERMARK_TEXT = "freepornx.site"

def get_drive_service():
    # Refresh token aur credentials se Drive API connect karna
    info = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "refresh_token": REFRESH_TOKEN,
    }
    creds = Credentials.from_authorized_user_info(info)
    return build('drive', 'v3', credentials=creds)

def add_watermark(image_content):
    # Image open karna
    img = Image.open(io.BytesIO(image_content)).convert("RGB")
    draw = ImageDraw.Draw(img)
    
    width, height = img.size
    # Image size ke hisaab se dynamic font size (width ka 5%)
    font_size = int(width / 20) 
    
    try:
        # GitHub Actions (Linux) par ye font path hamesha chalta hai
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except:
        # Agar font na mile toh default load karega
        font = ImageFont.load_default()

    # Position: Bottom Right (Margin ke sath)
    text_bbox = draw.textbbox((0, 0), WATERMARK_TEXT, font=font)
    tw, th = text_bbox[2] - text_bbox[0], text_bbox[3] - text_bbox[1]
    x, y = width - tw - 30, height - th - 30

    # 1. Black Shadow (Border effect ke liye)
    for offset in range(1, 4):
        draw.text((x+offset, y+offset), WATERMARK_TEXT, fill="black", font=font)
    
    # 2. White Main Text
    draw.text((x, y), WATERMARK_TEXT, fill="white", font=font)
    
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='JPEG', quality=90) # Thoda compress karke save
    return img_byte_arr.getvalue()

def upload_to_drive(service, image_data, filename):
    file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
    media = MediaIoBaseUpload(io.BytesIO(image_data), mimetype='image/jpeg')
    file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print(f"✅ Drive par upload ho gaya: {filename}")

def main():
    if not all([CLIENT_ID, CLIENT_SECRET, REFRESH_TOKEN, DRIVE_FOLDER_ID]):
        print("❌ Error: GitHub Secrets mein saari details nahi mili!")
        return

    service = get_drive_service()
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    
    print("--- Scraping shuru ho raha hai ---")
    r = requests.get(SOURCE_URL, headers=headers)
    soup = BeautifulSoup(r.text, 'html.parser')
    links = [a['href'] for a in soup.find_all('a', href=True) if "/galleries/" in a['href']]
    
    if not os.path.exists(HISTORY_FILE):
        open(HISTORY_FILE, "w").close()
    
    with open(HISTORY_FILE, "r") as f:
        posted = f.read().splitlines()

    count = 0
    random.shuffle(links)

    for gal_link in links:
        if count >= 10: break # Din ki 10 images limit
        
        full_gal = gal_link if gal_link.startswith('http') else "https://www.pornpics.com" + gal_link
        res = requests.get(full_gal, headers=headers)
        gal_soup = BeautifulSoup(res.text, 'html.parser')
        
        # Gallery ke andar se bade size ki images uthana
        imgs = [img.get('data-src') or img.get('src') for img in gal_soup.find_all('img') if "pornpics.com" in (img.get('data-src') or img.get('src', ''))]
        
        for img_url in imgs:
            if count >= 10: break
            full_img = img_url if img_url.startswith('http') else "https:" + img_url
            
            # Agar image pehle upload nahi hui
            if full_img not in posted:
                try:
                    print(f"Processing Image {count+1}...")
                    img_res = requests.get(full_img)
                    if img_res.status_code == 200:
                        # 1. Watermark lagao
                        final_img_data = add_watermark(img_res.content)
                        
                        # 2. Drive par upload karo
                        filename = f"desi_{int(time.time())}_{count}.jpg"
                        upload_to_drive(service, final_img_data, filename)
                        
                        # 3. History update karo
                        with open(HISTORY_FILE, "a") as f:
                            f.write(full_img + "\n")
                        
                        count += 1
                        time.sleep(2) # Speed control
                except Exception as e:
                    print(f"⚠️ Error processing: {e}")

if __name__ == "__main__":
    main()
