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

# --- 認証設定 (Streamlit Secretsから読み込む) ---
try:
    # Secretsから辞書として読み込む
    key_dict = dict(st.secrets["gcp_service_account"])
except Exception:
    st.error("設定エラー: Secretsに [gcp_service_account] が設定されていません。")
    st.stop()

# --- 関数群 ---
def get_drive_service():
    creds = service_account.Credentials.from_service_account_info(
        key_dict, scopes=['https://www.googleapis.com/auth/drive'])
    return build('drive', 'v3', credentials=creds)

def extract_folder_id(url):
    match = re.search(r'folders/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None

def sanitize(text):
    return re.sub(r'[\\/:*?"<>|]', '_', text).strip()[:100]

def save_to_drive(service, folder_id, name, content):
    meta = {'name': name, 'parents': [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(content), mimetype='application/pdf')
    service.files().create(body=meta, media_body=media, fields='id').execute()

# --- アプリ画面 ---
st.set_page_config(page_title="PDF Hunter", page_icon="📂")
st.title("📂 PDF Hunter")

with st.form("form"):
    target = st.text_input("WebページURL", "https://www.nta.go.jp/about/organization/ntc/soshoshiryo/kazei/2023/index.htm")
    drive = st.text_input("保存先DriveフォルダURL")
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
        
        # PDFリンクを抽出
        links = [l for l in soup.find_all('a', href=True) if l['href'].lower().endswith('.pdf')]
        
        if not links:
            st.warning("PDFが見つかりませんでした")
            st.stop()
            
        bar = st.progress(0)
        for i, l in enumerate(links):
            bar.progress((i+1)/len(links))
            url = urljoin(target, l['href'])
            name = sanitize(l.get_text(strip=True)) + ".pdf" if l.get_text(strip=True) else os.path.basename(l['href'])
            
            status.text(f"保存中: {name}")
            try:
                save_to_drive(svc, fid, name, requests.get(url).content)
            except Exception as e:
                st.warning(f"失敗: {name} ({e})")
        
        status.success(f"完了！ {len(links)} 件保存しました")
        st.balloons()
        
    except Exception as e:
        st.error(f"エラー: {e}")
