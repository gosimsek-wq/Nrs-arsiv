import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import hashlib
from datetime import datetime
import uuid
import time

# --- AYARLAR ---
st.set_page_config(page_title="Nrs-Arsiv", layout="wide", page_icon="🧠")
SHEET_NAME = "Nrs-arsiv"

# --- GÜVENLİK ---
def make_hashes(password):
    return hashlib.sha256(str.encode(password)).hexdigest()

def check_hashes(password, hashed_text):
    return make_hashes(password) == hashed_text

# --- GOOGLE SHEETS BAĞLANTISI ---
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
    try:
        ws = sheet_obj.worksheet(worksheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def add_data(sheet_obj, worksheet_name, data_dict):
    try:
        ws = sheet_obj.worksheet(worksheet_name)
        if not ws.get_all_values():
            ws.append_row(list(data_dict.keys()))
        ws.append_row(list(data_dict.values()))
        return True
    except Exception as e:
        st.error(f"Kayıt Hatası: {e}")
        return False

# --- GİRİŞ EKRANI ---
if 'logged_in' not in st.session_state:
    st.session_state['logged_in'] = False

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
                    st.success("Admin oluşturuldu. Tekrar deneyin.")
                except:
                    st.error("Lütfen Google Sheet'te 'users' sayfasını oluşturun.")
            else:
                user_found = users_df[users_df['username'] == user]
                if not user_found.empty:
                    if check_hashes(pw, user_found.iloc[0]['password']):
                        st.session_state.update({'logged_in': True, 'username': user, 'user_role': user_found.iloc[0]['role']})
                        st.rerun()
                    else:
                        st.error("Hatalı Şifre")
                else:
                    st.error("Kullanıcı Bulunamadı")
        except Exception as e:
            st.error(f"Bağlantı Hatası: {e}")

else:
    # --- ANA UYGULAMA ---
    st.sidebar.title("Nrs-Arsiv")
    st.sidebar.info(f"👤 Dr. {st.session_state['username']}")
    
    menu = ["Dashboard", "Vasküler", "Nöro-Onkoloji", "Epilepsi", "Omurga", "Pediatrik", "Fonksiyonel", "Travma"]
    
    # Sadece Yöneticiye Gözüken Modüller
    if st.session_state['user_role'] == "Yönetici":
        menu.append("👨‍🏫 Süpervizör Paneli")
        menu.append("👥 Kullanıcı Yönetimi")
    
    menu.append("Çıkış")
    choice = st.sidebar.radio("Modül Seçiniz", menu)
    
    bugun = datetime.now().strftime("%d/%m/%Y")
    sheet = connect_gsheet()

    # DICOM/Video linki eklendi
    def hasta_kimlik_ui():
        c1, c2, c3 = st.columns(3)
        protokol = c1.text_input("Protokol No")
        ad = c2.text_input("Adı Soyadı")
        yatis = c3.date_input("Yatış Tarihi")
        c4, c5, c6 = st.columns(3)
        yas = c4.number_input("Yaş", 0, 120, 50)
        cinsiyet = c5.selectbox("Cinsiyet", ["Erkek", "Kadın"])
        dosya_linki = c6.text_input("📁 DICOM / Video Linki")
        st.divider()
        return protokol, ad, yas, cinsiyet, yatis.strftime("%d/%m/%Y"), dosya_linki

    # Süpervizör alanları otomatik eklendi
    def kaydet(worksheet, data):
        final_data = {
            "id": str(uuid.uuid4())[:8], 
            **data,
            "onay_durumu": "Bekliyor",
            "supervizor_notu": ""
        }
        if add_data(sheet, worksheet, final_data):
            st.success(f"✅ Kayıt '{worksheet.upper()}' modülüne eklendi. Süpervizör onayı bekleniyor.")

    if choice == "Dashboard":
        st.title("📊 Nrs-Arsiv Paneli")
        try:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Vasküler Vaka", len(get_data(sheet, "vaskuler")))
            col2.metric("Onkoloji Vaka", len(get_data(sheet, "onkoloji")))
            col3.metric("Spinal Vaka", len(get_data(sheet, "omurga")))
            col4.metric("Pediatrik Vaka", len(get_data(sheet, "pediatrik")))
        except:
            pass

    elif choice == "Vasküler":
        st.header("🩸 Serebrovasküler")
        with st.form("v_form"):
            protokol, ad, yas, cinsiyet, yatis, dosya_linki = hasta_kimlik_ui()
            gks = st.slider("GKS", 3, 15, 15)
            tani = st.text_input("Tanı")
            notlar = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"):
                kaydet("vaskuler", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "gks": gks, "tani": tani, "dosya_linki": dosya_linki, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "vaskuler").tail(5))

    elif choice == "Nöro-Onkoloji":
        st.header("🧬 Nöro-Onkoloji")
        with st.form("o_form"):
            protokol, ad, yas, cinsiyet, yatis, dosya_linki = hasta_kimlik_ui()
            tip = st.selectbox("Tip", ["GBM", "Menenjiyom", "Metastaz", "Schwannom", "Diğer"])
            lokasyon = st.text_input("Lokasyon")
            notlar = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"):
                kaydet("onkoloji", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "tip": tip, "lokasyon": lokasyon, "dosya_linki": dosya_linki, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "onkoloji").tail(5))

    elif choice == "Epilepsi":
        st.header("🧠 Epilepsi Cerrahisi")
        with st.form("e_form"):
            protokol, ad, yas, cinsiyet, yatis, dosya_linki = hasta_kimlik_ui()
            cerrahi = st.selectbox("Cerrahi", ["VNS", "Amigdalohipokampektomi", "Lezyonektomi", "Korpus Kallozotomi", "Diğer"])
            notlar = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"):
                kaydet("epilepsi", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "cerrahi": cerrahi, "dosya_linki": dosya_linki, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "epilepsi").tail(5))

    elif choice == "Omurga":
        st.header("🦴 Spinal Cerrahi")
        with st.form("s_form"):
            protokol, ad, yas, cinsiyet, yatis, dosya_linki = hasta_kimlik_ui()
            patoloji = st.selectbox("Patoloji", ["Lomber Disk Hernisi", "Servikal Disk Hernisi", "Spinal Stenoz", "Spondilolistezis", "Spinal Travma", "Spinal Tümör"])
            seviye = st.text_input("Seviye (Örn: L4-L5)")
            notlar = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"):
                kaydet("omurga", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "patoloji": patoloji, "seviye": seviye, "dosya_linki": dosya_linki, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "omurga").tail(5))

    elif choice == "Pediatrik":
        st.header("👶 Pediatrik Nöroşirürji")
        with st.form("p_form"):
            protokol, ad, yas, cinsiyet, yatis, dosya_linki = hasta_kimlik_ui()
            kategori = st.selectbox("Kategori", ["Hidrosefali", "Kraniosinostoz", "Meningomyelosel", "Tethered Cord", "Pediatrik Tümör", "Diğer"])
            notlar = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"):
                kaydet("pediatrik", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "kategori": kategori, "dosya_linki": dosya_linki, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "pediatrik").tail(5))

    elif choice == "Fonksiyonel":
        st.header("⚙️ Fonksiyonel Nöroşirürji")
        with st.form("f_form"):
            protokol, ad, yas, cinsiyet, yatis, dosya_linki = hasta_kimlik_ui()
            tur = st.selectbox("Tür", ["DBS (Derin Beyin Stimülasyonu)", "Baklofen Pompası", "Ağrı Cerrahisi / Pil", "Diğer"])
            hedef = st.text_input("Hedef / Hedef Çekirdek (Örn: STN, GPi)")
            notlar = st.text_area("Notlar")
            if st.form_submit_button("Kaydet"):
                kaydet("fonksiyonel", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "tur": tur, "hedef": hedef, "dosya_linki": dosya_linki, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "fonksiyonel").tail(5))

    elif choice == "Travma":
        st.header("🚑 Nörotravma")
        with st.form("t_form"):
            protokol, ad, yas, cinsiyet, yatis, dosya_linki = hasta_kimlik_ui()
            gks = st.slider("Geliş GKS", 3, 15, 15)
            marshall = st.selectbox("Marshall Skoru", ["Grade I", "Grade II", "Grade III", "Grade IV", "Grade V", "Grade VI"])
            notlar = st.text_area("Notlar / Cerrahi İşlem")
            if st.form_submit_button("Kaydet"):
                kaydet("travma", {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, "gks": gks, "marshall": marshall, "dosya_linki": dosya_linki, "kaydeden": st.session_state['username'], "notlar": notlar})
        st.dataframe(get_data(sheet, "travma").tail(5))

    elif choice == "👨‍🏫 Süpervizör Paneli":
        st.title("👨‍🏫 Süpervizör Onay Paneli")
        modul = st.selectbox("İncelenecek Modül", ["vaskuler", "onkoloji", "epilepsi", "omurga", "pediatrik", "fonksiyonel", "travma"])
        
        df = get_data(sheet, modul)
        if not df.empty and 'onay_durumu' in df.columns:
            bekleyenler = df[df['onay_durumu'] != "Onaylandı"]
            if not bekleyenler.empty:
                for index, row in bekleyenler.iterrows():
                    with st.expander(f"📌 Hasta: {row.get('ad', 'Bilinmiyor')} | Ekleyen: {row.get('kaydeden', 'Bilinmiyor')} | Tarih: {row.get('tarih', '')}"):
                        # Gizli verileri ekranda göstermemek için filtrele
                        gosterilecek = {k: v for k, v in row.items() if k not in ['id', 'onay_durumu', 'supervizor_notu']}
                        st.write(gosterilecek)
                        
                        if row.get('dosya_linki'):
                            st.markdown(f"**🔗 Dosya/Görüntü Bağlantısı:** [Tıklayıp Görüntüle]({row['dosya_linki']})")
                        
                        s_not = st.text_area("Süpervizör Notu", key=f"not_{row['id']}")
                        
                        if st.button("Onayla ve Kaydet", key=f"btn_{row['id']}"):
                            try:
                                ws = sheet.worksheet(modul)
                                cell = ws.find(str(row['id']))
                                
                                # Sütun numaralarını bul
                                col_onay = ws.find("onay_durumu").col
                                col_not = ws.find("supervizor_notu").col
                                
                                # Güncelleme
                                ws.update_cell(cell.row, col_onay, "Onaylandı")
                                ws.update_cell(cell.row, col_not, s_not)
                                st.success("Vaka Onaylandı!"); time.sleep(1); st.rerun()
                            except Exception as e:
                                st.error(f"Onaylama sırasında hata oluştu: {e}")
            else:
                st.info("✅ Harika! Bu modülde onay bekleyen vaka bulunmuyor.")
        else:
            st.warning("Bu modülde henüz hiç kayıt yok veya eski yapıdan kalma veriler var.")

    elif choice == "👥 Kullanıcı Yönetimi":
        st.title("👥 Kadro Yönetimi")
        with st.form("add_user"):
            u = st.text_input("Kullanıcı")
            p = st.text_input("Şifre", type='password')
            r = st.selectbox("Rol", ["Asistan", "Yönetici"])
            if st.form_submit_button("Ekle"):
                try:
                    ws = sheet.worksheet("users")
                    if u in ws.col_values(1):
                        st.error("Mevcut!")
                    else:
                        ws.append_row([u, make_hashes(p), r])
                        st.success("Eklendi!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(str(e))
        
        st.divider()
        users_df = get_data(sheet, "users")
        if not users_df.empty:
            silinecekler = users_df[users_df['username'] != 'admin']['username'].tolist()
            if silinecekler:
                sil = st.selectbox("Silinecek Kişi", silinecekler)
                if st.button("❌ Sil"):
                    ws = sheet.worksheet("users")
                    cell = ws.find(sil)
                    ws.delete_rows(cell.row)
                    st.success("Silindi")
                    time.sleep(1)
                    st.rerun()

    elif choice == "Çıkış":
        st.session_state.clear()
        st.rerun()
