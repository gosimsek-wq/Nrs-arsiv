import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib
from datetime import datetime
import uuid
import time

st.set_page_config(page_title="Nrs-Arsiv", layout="wide", page_icon="🧠")
SHEET_NAME = "Nrs-arsiv"

def make_hashes(password): return hashlib.sha256(str.encode(password)).hexdigest()
def check_hashes(password, hashed_text): return make_hashes(password) == hashed_text

@st.cache_resource
def connect_gsheet():
    try:
        if "gcp_service_account" not in st.secrets:
            st.error("Hata: Streamlit Secrets ayarlanmamış.")
            st.stop()
        creds_dict = dict(st.secrets["gcp_service_account"])
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        return client.open(SHEET_NAME)
    except Exception as e:
        st.error(f"Bağlantı Hatası: {e}")
        st.stop()

def get_data(sheet_obj, worksheet_name):
    try: return pd.DataFrame(sheet_obj.worksheet(worksheet_name).get_all_records())
    except: return pd.DataFrame()

def add_data(sheet_obj, worksheet_name, data_dict):
    try:
        ws = sheet_obj.worksheet(worksheet_name)
        if not ws.get_all_values(): ws.append_row(list(data_dict.keys()))
        ws.append_row(list(data_dict.values()))
        return True
    except: return False

if 'logged_in' not in st.session_state: st.session_state['logged_in'] = False

if not st.session_state['logged_in']:
    st.title("☁️ Nrs-Arsiv Giriş")
    user = st.text_input("Kullanıcı Adı")
    pw = st.text_input("Şifre", type='password')
    if st.button("Sisteme Gir"):
        try:
            sheet = connect_gsheet()
            users_df = get_data(sheet, "users")
            if users_df.empty:
                try:
                    ws = sheet.worksheet("users")
                    ws.append_row(["username", "password", "role"])
                    ws.append_row(["admin", make_hashes("noro2026"), "Yönetici"])
                    st.success("Admin oluşturuldu. Lütfen tekrar girin.")
                except: st.error("Google Sheet'te 'users' sekmesi yok.")
            else:
                uf = users_df[users_df['username'] == user]
                if not uf.empty and check_hashes(pw, uf.iloc[0]['password']):
                    st.session_state.update({'logged_in': True, 'username': user, 'user_role': uf.iloc[0]['role']})
                    st.rerun()
                else: st.error("Hatalı Kullanıcı veya Şifre")
        except: st.error("Bağlantı kurulamadı.")
else:
    st.sidebar.title("Nrs-Arsiv")
    st.sidebar.info(f"👤 Dr. {st.session_state['username']}")
    menu = ["Dashboard", "Vasküler", "Nöro-Onkoloji", "Epilepsi", "Omurga", "Pediatrik", "Fonksiyonel", "Travma"]
    if st.session_state['user_role'] == "Yönetici": menu.append("Kullanıcı Yönetimi")
    choice = st.sidebar.radio("Menü", menu + ["Çıkış"])
    
    bugun = datetime.now().strftime("%d/%m/%Y")
    sheet = connect_gsheet()

    def hasta_kimlik_ui():
        c1, c2, c3 = st.columns(3)
        protokol = c1.text_input("Protokol No")
        ad = c2.text_input("Adı Soyadı")
        yatis = c3.date_input("Yatış Tarihi")
        c4, c5 = st.columns(2)
        yas = c4.number_input("Yaş", 0, 120, 50)
        cinsiyet = c5.selectbox("Cinsiyet", ["Erkek", "Kadın"])
        st.divider()
        return protokol, ad, yas, cinsiyet, yatis.strftime("%d/%m/%Y")

    def kaydet(ws_name, data):
        final_data = {"id": str(uuid.uuid4())[:8], **data}
        if add_data(sheet, ws_name, final_data): st.success(f"Kaydedildi: {ws_name}")

    if choice == "Dashboard":
        st.title("📊 Nrs-Arsiv Paneli")
        c1, c2 = st.columns(2)
        try:
            c1.metric("Vasküler", len(get_data(sheet, "vaskuler")))
            c2.metric("Onkoloji", len(get_data(sheet, "onkoloji")))
        except: pass
    elif choice == "Vasküler":
        st.header("🩸 Serebrovasküler")
        with st.form("v_form"):
            protokol, ad, yas, cinsiyet, yatis = hasta_kimlik_ui()
            tani = st.text_input("Tanı")
            notlar = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"): kaydet("vaskuler", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "tani": tani, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "vaskuler").tail(5))
    elif choice == "Nöro-Onkoloji":
        st.header("🧬 Nöro-Onkoloji")
        with st.form("o_form"):
            protokol, ad, yas, cinsiyet, yatis = hasta_kimlik_ui()
            tip = st.selectbox("Tip", ["GBM", "Menenjiyom", "Metastaz"])
            notlar = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"): kaydet("onkoloji", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "tip": tip, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "onkoloji").tail(5))
    elif choice == "Kullanıcı Yönetimi":
        st.title("👥 Kadro Yönetimi")
        with st.form("add_user"):
            u = st.text_input("Kullanıcı")
            p = st.text_input("Şifre", type='password')
            r = st.selectbox("Rol", ["Asistan", "Yönetici"])
            if st.form_submit_button("Ekle"):
                try:
                    ws = sheet.worksheet("users")
                    if u in ws.col_values(1): st.error("Mevcut!")
                    else: ws.append_row([u, make_hashes(p), r]); st.success("Eklendi!"); time.sleep(1); st.rerun()
                except: pass
    elif choice == "Çıkış":
        st.session_state.clear()
        st.rerun()
