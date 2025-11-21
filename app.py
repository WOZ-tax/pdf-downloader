# 1. リポジトリをクローンしてフォルダに入る
git clone https://github.com/WOZ-tax/pdf-downloader.git
cd pdf-downloader

# 2. requirements.txt を作成
cat <<EOF > requirements.txt
streamlit
requests
beautifulsoup4
google-api-python-client
google-auth
EOF

# 3. Dockerfile を作成
cat <<EOF > Dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8080

CMD ["streamlit", "run", "app.py", "--server.port=8080", "--server.address=0.0.0.0"]
EOF

# 4. app.py を作成 (Pythonコードを書き込み)
cat <<EOF > app.py
import streamlit as st
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload
import io
import re
import os
import json

# --- 認証情報の設定 ---
KEY_FILE = 'key.json'

def load_key_dict():
    try:
        # Cloud環境 (Secrets)
        if "gcp_service_account" in st.secrets:
             return dict(st.secrets["gcp_service_account"])
        # ローカル環境 (key.json)
        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, 'r') as f:
                return json.load(f)
        st.error("認証情報が見つかりません。")
        st.stop()
    except Exception as e:
        st.error(f"認証エラー: {e}")
        st.stop()

key_dict = load_key_dict()

def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive'])
    return build('drive', 'v3', credentials=creds)

def extract_folder_id(url):
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None

def sanitize(text):
    return re.sub(r'[\\\\/:*?"<>|]', '_', text).strip()[:100]

def save_to_drive(service, folder_id, name, content):
    meta = {'name': name, 'parents': [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype='application/pdf')
    service.files().create(body=meta, media_body=media, fields='id').execute()

st.set_page_config(page_title="PDF Hunter", page_icon="📂")
st.title("📂 PDF Hunter")

with st.form("form"):
    target = st.text_input("WebページURL", "https://www.nta.go.jp/about/organization/ntc/soshoshiryo/kazei/2023/index.htm")
    drive = st.text_input("DriveフォルダURL")
    btn = st.form_submit_button("開始")

if btn:
    fid = extract_folder_id(drive)
    if not fid:
        st.error("Drive URLが無効です")
        st.stop()
    
    status = st.empty()
    try:
        svc = get_drive_service()
        res = requests.get(target)
        res.encoding = res.apparent_encoding
        soup = BeautifulSoup(res.text, 'html.parser')
        links = [l for l in soup.find_all('a', href=True) if l['href'].lower().endswith('.pdf')]
        
        if not links:
            st.warning("PDFなし")
            st.stop()
            
        bar = st.progress(0)
        for i, l in enumerate(links):
            bar.progress((i+1)/len(links))
            url = urljoin(target, l['href'])
            name = sanitize(l.get_text(strip=True)) + ".pdf" if l.get_text(strip=True) else os.path.basename(l['href'])
            status.text(f"保存中: {name}")
            try:
                save_to_drive(svc, fid, name, requests.get(url).content)
            except:
                pass
        status.success("完了")
    except Exception as e:
        st.error(f"エラー: {e}")
EOF
