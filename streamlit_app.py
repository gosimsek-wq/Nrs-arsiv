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

# --- GOOGLE SHEETS BAĞLANTISI VE OTOMATİK SAYFA OLUŞTURUCU ---
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

def ensure_worksheet(sheet_obj, ws_name):
    # Sayfa yoksa otomatik olarak oluşturur
    try:
        existing_sheets = [ws.title for ws in sheet_obj.worksheets()]
        if ws_name not in existing_sheets:
            sheet_obj.add_worksheet(title=ws_name, rows="1000", cols="40")
        return sheet_obj.worksheet(ws_name)
    except Exception as e:
        st.error(f"Sayfa işlem hatası ({ws_name}): {e}")
        return None

def get_data(sheet_obj, worksheet_name):
    try:
        ws = ensure_worksheet(sheet_obj, worksheet_name)
        data = ws.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

def add_data(sheet_obj, worksheet_name, data_dict):
    try:
        ws = ensure_worksheet(sheet_obj, worksheet_name)
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
                    ws = ensure_worksheet(sheet, "users")
                    ws.append_row(["username", "password", "role"])
                    ws.append_row(["admin", make_hashes("noro2026"), "Yönetici"])
                    st.success("Admin kullanıcısı oluşturuldu. Lütfen tekrar deneyin.")
                except:
                    st.error("Kullanıcı veritabanı oluşturulamadı.")
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
    
    # Süpervizör ve Yönetim Sadece Yöneticide Çıkar
    if st.session_state['user_role'] == "Yönetici":
        menu.append("👨‍🏫 Süpervizör Paneli")
        menu.append("👥 Kullanıcı Yönetimi")
    
    menu.append("Çıkış")
    choice = st.sidebar.radio("Modül Seçiniz", menu)
    
    bugun = datetime.now().strftime("%d/%m/%Y")
    sheet = connect_gsheet()

    # Ortak Hasta Kimlik ve ÇOKLU LİNK Formu
    def hasta_kimlik_ui():
        c1, c2, c3 = st.columns(3)
        protokol = c1.text_input("Protokol No")
        ad = c2.text_input("Adı Soyadı")
        yatis = c3.date_input("Yatış Tarihi")
        
        c4, c5 = st.columns(2)
        yas = c4.number_input("Yaş", 0, 120, 50)
        cinsiyet = c5.selectbox("Cinsiyet", ["Erkek", "Kadın"])
        
        st.markdown("#### 🔗 Dosya ve Görüntü Bağlantıları (Google Drive / PACS vb.)")
        l1, l2, l3 = st.columns(3)
        link_dicom = l1.text_input("Görüntüleme (DICOM/MR) Linki")
        link_video = l2.text_input("Ameliyat Videosu Linki")
        link_ek = l3.text_input("Ek Dosya / Rapor Linki")
        
        st.divider()
        return protokol, ad, yas, cinsiyet, yatis.strftime("%d/%m/%Y"), link_dicom, link_video, link_ek

    # Ortak Kayıt Fonksiyonu (Süpervizör Onayı İçerir)
    def kaydet(worksheet, data):
        final_data = {
            "id": str(uuid.uuid4())[:8], 
            **data,
            "onay_durumu": "Bekliyor",
            "supervizor_notu": ""
        }
        if add_data(sheet, worksheet, final_data):
            st.success(f"✅ Kayıt başarıyla '{worksheet.upper()}' modülüne eklendi. Süpervizör onayı bekleniyor.")

    # --- MODÜLLER ---
    if choice == "Dashboard":
        st.title("📊 Nrs-Arsiv Paneli")
        try:
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Vasküler Vaka", len(get_data(sheet, "vaskuler")))
            col2.metric("Onkoloji Vaka", len(get_data(sheet, "onkoloji")))
            col3.metric("Spinal Vaka", len(get_data(sheet, "omurga")))
            col4.metric("Pediatrik Vaka", len(get_data(sheet, "pediatrik")))
        except: pass

    elif choice == "Vasküler":
        st.header("🩸 Serebrovasküler")
        with st.form("v_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            c1, c2, c3 = st.columns(3)
            gks = c1.slider("Geliş GKS", 3, 15, 15)
            fisher = c2.selectbox("Fisher Skoru (SAK)", ["Değerlendirilmedi", "Evre 1", "Evre 2", "Evre 3", "Evre 4"])
            hunt_hess = c3.selectbox("Hunt-Hess Evresi", ["Değerlendirilmedi", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"])
            
            c4, c5 = st.columns(2)
            ogilvy = c4.selectbox("Ogilvy-Carter Skoru", ["Değerlendirilmedi", "0", "1", "2", "3", "4", "5"])
            sahss = c5.selectbox("SAHSS (SAH Sekela Skalası)", ["Değerlendirilmedi", "İyi", "Orta", "Kötü"])
            
            tani = st.text_input("Klinik Tanı / Anevrizma-AVM Lokasyonu")
            notlar = st.text_area("Cerrahi Notlar / EVD Takibi")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "gks": gks, "fisher": fisher, "hunt_hess": hunt_hess, "ogilvy_carter": ogilvy, "sahss": sahss, "tani": tani, 
                        "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("vaskuler", veri)
        st.dataframe(get_data(sheet, "vaskuler").tail(5))

    elif choice == "Nöro-Onkoloji":
        st.header("🧬 Nöro-Onkoloji")
        with st.form("o_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            c1, c2, c3 = st.columns(3)
            tip = c1.selectbox("Tümör Tipi", ["Glial Tümör", "Menenjiyom", "Metastaz", "Schwannom", "Diğer"])
            kps = c2.slider("Karnofsky Skoru (KPS)", 0, 100, 80, step=10)
            ds_gpa = c3.text_input("DS-GPA Skoru (Metastaz İçin)")
            
            lokasyon = st.text_input("Anatomik Lokasyon")
            rezeksiyon = st.selectbox("Rezeksiyon Oranı", ["Gross Total Rezeksiyon (GTR)", "Subtotal Rezeksiyon (STR)", "Biyopsi"])
            notlar = st.text_area("Cerrahi Notlar / Patoloji Beklentisi")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "tip": tip, "kps": kps, "ds_gpa": ds_gpa, "lokasyon": lokasyon, "rezeksiyon": rezeksiyon, 
                        "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("onkoloji", veri)
        st.dataframe(get_data(sheet, "onkoloji").tail(5))

    elif choice == "Epilepsi":
        st.header("🧠 Epilepsi Cerrahisi")
        with st.form("e_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            c1, c2 = st.columns(2)
            cerrahi = c1.selectbox("Cerrahi Yöntem", ["VNS İmplantasyonu", "Amigdalohipokampektomi", "Lezyonektomi", "Korpus Kallozotomi", "Grid/Strip Yerleştirme", "Diğer"])
            engel = c2.selectbox("Engel Sınıflaması (Post-op Hedef/Durum)", ["Sınıf I", "Sınıf II", "Sınıf III", "Sınıf IV", "Değerlendirilmedi"])
            
            notlar = st.text_area("Klinik Notlar / Nöbet Sıklığı")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "cerrahi": cerrahi, "engel_skoru": engel, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("epilepsi", veri)
        st.dataframe(get_data(sheet, "epilepsi").tail(5))

    elif choice == "Omurga":
        st.header("🦴 Spinal Cerrahi")
        with st.form("s_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            c1, c2 = st.columns(2)
            patoloji = c1.selectbox("Patoloji", ["Lomber Disk Hernisi", "Servikal Disk Hernisi", "Spinal Stenoz", "Spondilolistezis", "Spinal Travma", "Spinal Tümör", "Diğer"])
            asia = c2.selectbox("ASIA Skoru (Mevcutsa)", ["Değerlendirilmedi", "A", "B", "C", "D", "E"])
            
            seviye = st.text_input("Spinal Seviye (Örn: L4-L5, C5-C6)")
            notlar = st.text_area("Cerrahi Notlar / Enstrümantasyon Detayları")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "patoloji": patoloji, "asia": asia, "seviye": seviye, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("omurga", veri)
        st.dataframe(get_data(sheet, "omurga").tail(5))

    elif choice == "Pediatrik":
        st.header("👶 Pediatrik Nöroşirürji")
        with st.form("p_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            kategori = st.selectbox("Patoloji Kategorisi", ["Hidrosefali", "Sendromik Kraniosinostoz", "Non-Sendromik Kraniosinostoz", "Meningomyelosel", "Tethered Cord", "Pediatrik Tümör", "Galen Veni Anevrizması / Vasküler", "Diğer"])
            tani = st.text_input("Spesifik Tanı / Sendrom Adı")
            notlar = st.text_area("Cerrahi Notlar / Şant Tipi / İlerleyici Plan")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "kategori": kategori, "tani": tani, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("pediatrik", veri)
        st.dataframe(get_data(sheet, "pediatrik").tail(5))

    elif choice == "Fonksiyonel":
        st.header("⚙️ Fonksiyonel Nöroşirürji")
        with st.form("f_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            tur = st.selectbox("Girişim Türü", ["Derin Beyin Stimülasyonu (DBS)", "Baklofen Pompası", "Ağrı Pili / Kordotomi", "Diğer"])
            hedef = st.text_input("Hedef Çekirdek (Örn: STN, GPi, VIM)")
            notlar = st.text_area("Klinik Notlar / Programlama Detayları")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "tur": tur, "hedef": hedef, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("fonksiyonel", veri)
        st.dataframe(get_data(sheet, "fonksiyonel").tail(5))

    elif choice == "Travma":
        st.header("🚑 Nörotravma")
        with st.form("t_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            c1, c2 = st.columns(2)
            gks = c1.slider("Geliş GKS", 3, 15, 15)
            marshall = c2.selectbox("Marshall Tomografi Skoru", ["Değerlendirilmedi", "Grade I", "Grade II", "Grade III", "Grade IV", "Grade V (Kitle)", "Grade VI"])
            
            tani = st.text_input("Tanı (EDH, SDH, Kontüzyon vb.)")
            notlar = st.text_area("Cerrahi Müdahale / ICP Takip Notları")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "gks": gks, "marshall": marshall, "tani": tani, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("travma", veri)
        st.dataframe(get_data(sheet, "travma").tail(5))

    elif choice == "👨‍🏫 Süpervizör Paneli":
        st.title("👨‍🏫 Süpervizör Onay Paneli")
        st.info("Bu modülde asistanların kaydettiği vakaları inceleyebilir, linklere doğrudan gidebilir ve onaylayabilirsiniz.")
        
        modul = st.selectbox("İncelenecek Veritabanı (Modül)", ["vaskuler", "onkoloji", "epilepsi", "omurga", "pediatrik", "fonksiyonel", "travma"])
        df = get_data(sheet, modul)
        
        if not df.empty and 'onay_durumu' in df.columns:
            bekleyenler = df[df['onay_durumu'] != "Onaylandı"]
            if not bekleyenler.empty:
                for index, row in bekleyenler.iterrows():
                    with st.expander(f"📌 {row.get('ad', 'İsimsiz Vaka')} | Protokol: {row.get('protokol','')} | Ekleyen: {row.get('kaydeden', '')}"):
                        
                        # Bağlantılar Ekranı
                        st.markdown("##### 📁 Yüklenen Dosya Bağlantıları")
                        if row.get('link_dicom'): st.markdown(f"- [Görüntüleme (DICOM/MR) Linkine Git]({row['link_dicom']})")
                        if row.get('link_video'): st.markdown(f"- [Ameliyat Videosu Linkine Git]({row['link_video']})")
                        if row.get('link_ek'): st.markdown(f"- [Ek Dosya / Rapor Linkine Git]({row['link_ek']})")
                        
                        st.markdown("##### 📝 Vaka Detayları")
                        gosterilecek = {k: v for k, v in row.items() if k not in ['id', 'onay_durumu', 'supervizor_notu', 'link_dicom', 'link_video', 'link_ek']}
                        st.write(gosterilecek)
                        
                        s_not = st.text_area("Süpervizör Onay Notu / Düzeltme İsteği", key=f"not_{row['id']}")
                        
                        if st.button("Vakayı Onayla", key=f"btn_{row['id']}"):
                            try:
                                ws = sheet.worksheet(modul)
                                cell = ws.find(str(row['id']))
                                col_onay = ws.find("onay_durumu").col
                                col_not = ws.find("supervizor_notu").col
                                
                                ws.update_cell(cell.row, col_onay, "Onaylandı")
                                ws.update_cell(cell.row, col_not, s_not)
                                st.success(f"{row.get('ad')} vakası onaylandı."); time.sleep(1); st.rerun()
                            except Exception as e:
                                st.error(f"Onaylama sırasında hata oluştu: {e}")
            else:
                st.success(f"✅ Harika! '{modul.upper()}' modülünde onay bekleyen vaka bulunmuyor.")
        else:
            st.warning("Bu modülde henüz hiç kayıt yok veya onay mekanizması kurulmadan önceki eski kayıtlar mevcut.")

    elif choice == "👥 Kullanıcı Yönetimi":
        st.title("👥 Kadro Yönetimi")
        with st.form("add_user"):
            u = st.text_input("Kullanıcı")
            p = st.text_input("Şifre", type='password')
            r = st.selectbox("Yetki Rolü", ["Asistan", "Yönetici"])
            if st.form_submit_button("Sisteme Ekle"):
                try:
                    ws = ensure_worksheet(sheet, "users")
                    if u in ws.col_values(1):
                        st.error("Bu kullanıcı zaten mevcut!")
                    else:
                        ws.append_row([u, make_hashes(p), r])
                        st.success("Kullanıcı başarıyla eklendi!")
                        time.sleep(1)
                        st.rerun()
                except Exception as e:
                    st.error(str(e))
        
        st.divider()
        users_df = get_data(sheet, "users")
        if not users_df.empty:
            silinecekler = users_df[users_df['username'] != 'admin']['username'].tolist()
            if silinecekler:
                sil = st.selectbox("Erişimi İptal Edilecek Kişi", silinecekler)
                if st.button("❌ Kullanıcıyı Sil"):
                    ws = sheet.worksheet("users")
                    cell = ws.find(sil)
                    ws.delete_rows(cell.row)
                    st.success("Kullanıcı silindi.")
                    time.sleep(1)
                    st.rerun()

    elif choice == "Çıkış":
        st.session_state.clear()
        st.rerun()
