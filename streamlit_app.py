import streamlit as st import pandas as pd import gspread from oauth2client.service_account import ServiceAccountCredentials import hashlib from datetime import datetime import uuid import time

--- AYARLAR ---
st.set_page_config(page_title="Nrs-Arsiv", layout="wide", page_icon="🧠") SHEET_NAME = "Nrs-arsiv"

--- GÜVENLİK ---
def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

--- GOOGLE SHEETS BAĞLANTISI ---
@st.cache_resource def connect_gsheet(): try: if "gcp_service_account" in st.secrets: creds_dict = dict(st.secrets["gcp_service_account"]) scope = ["", ""] creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope) client = gspread.authorize(creds) sheet = client.open(SHEET_NAME) return sheet else: st.error("Hata: Streamlit Secrets ayarlanmamış.") st.stop() except Exception as e: st.error(f"Google Sheets Bağlantı Hatası: {e}") st.stop()

def get_data(sheet_obj, worksheet_name): try: ws = sheet_obj.worksheet(worksheet_name) data = ws.get_all_records() return pd.DataFrame(data) except: return pd.DataFrame()

def add_data(sheet_obj, worksheet_name, data_dict): try: ws = sheet_obj.worksheet(worksheet_name) if not ws.get_all_values(): ws.append_row(list(data_dict.keys())) ws.append_row(list(data_dict.values())) return True except Exception as e: st.error(f"Kayıt Hatası: {e}") return False

--- GİRİŞ EKRANI ---
if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']: st.title("☁️ Nrs-Arsiv Giriş") user = st.text_input("Kullanıcı Adı") pw = st.text_input("Şifre", type='password')

else: # --- ANA UYGULAMA --- st.sidebar.title("Nrs-Arsiv") st.sidebar.info(f"👤 Dr. {st.session_state['username']}")
