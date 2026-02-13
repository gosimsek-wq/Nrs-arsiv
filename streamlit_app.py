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

def ensure_worksheet(sheet_obj, ws_name):
    try:
        existing_sheets = [ws.title for ws in sheet_obj.worksheets()]
        if ws_name not in existing_sheets:
            ws = sheet_obj.add_worksheet(title=ws_name, rows="1", cols="40")
            return ws
        return sheet_obj.worksheet(ws_name)
    except Exception as e:
        st.error(f"Sayfa işlem hatası ({ws_name}): {e}")
        return None

# YENİ VE HATASIZ VERİ OKUMA MOTORU
def get_data(sheet_obj, worksheet_name):
    try:
        ws = ensure_worksheet(sheet_obj, worksheet_name)
        vals = ws.get_all_values()
        
        # Sadece gerçekten dolu olan satırları filtrele (Gizli boşlukları yoksay)
        cleaned_vals = [row for row in vals if any(str(cell).strip() for cell in row)]
        if len(cleaned_vals) < 2:
            return pd.DataFrame()
            
        headers = cleaned_vals[0]
        data = cleaned_vals[1:]
        
        # Pandas hatasını önlemek için satır uzunluklarını eşitle
        max_cols = len(headers)
        data = [row + [""] * (max_cols - len(row)) for row in data]
        
        return pd.DataFrame(data, columns=headers)
    except Exception as e:
        return pd.DataFrame()

# YENİ VE HATASIZ VERİ YAZMA MOTORU
def add_data(sheet_obj, worksheet_name, data_dict):
    try:
        ws = ensure_worksheet(sheet_obj, worksheet_name)
        vals = ws.get_all_values()
        cleaned_vals = [row for row in vals if any(str(cell).strip() for cell in row)]
        
        # Eğer tabloda hiç gerçek veri yoksa ÖNCE başlıkları ekle
        if not cleaned_vals:
            ws.append_row(list(data_dict.keys()))
            
        # Sonra veriyi ekle
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
    
    if st.session_state['user_role'] == "Yönetici":
        menu.append("👨‍🏫 Süpervizör Paneli")
        menu.append("📈 İstatistik ve Analiz")
        menu.append("👥 Kullanıcı Yönetimi")
    
    menu.append("Çıkış")
    choice = st.sidebar.radio("Modül Seçiniz", menu)
    
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
        
        st.markdown("#### 🔗 Dosya ve Görüntü Bağlantıları")
        l1, l2, l3 = st.columns(3)
        link_dicom = l1.text_input("Görüntüleme (DICOM/MR) Linki")
        link_video = l2.text_input("Ameliyat Videosu Linki")
        link_ek = l3.text_input("Ek Dosya / Rapor Linki")
        
        st.divider()
        return protokol, ad, yas, cinsiyet, yatis.strftime("%d/%m/%Y"), link_dicom, link_video, link_ek

    def kaydet(worksheet, data):
        final_data = {
            "id": str(uuid.uuid4())[:8], 
            **data,
            "onay_durumu": "Bekliyor",
            "supervizor_notu": ""
        }
        if add_data(sheet, worksheet, final_data):
            st.success(f"✅ Kayıt başarıyla eklendi. Süpervizör onayı bekleniyor.")

    # --- MODÜLLER ---
    if choice == "Dashboard":
        st.title("📊 Klinik Genel Görünüm")
        try:
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🩸 Vasküler Vaka", len(get_data(sheet, "vaskuler")))
            c2.metric("🧬 Onkoloji Vaka", len(get_data(sheet, "onkoloji")))
            c3.metric("🦴 Spinal Vaka", len(get_data(sheet, "omurga")))
            c4.metric("🚑 Travma Vaka", len(get_data(sheet, "travma")))
            
            c5, c6, c7, c8 = st.columns(4)
            c5.metric("👶 Pediatrik Vaka", len(get_data(sheet, "pediatrik")))
            c6.metric("🧠 Epilepsi Vaka", len(get_data(sheet, "epilepsi")))
            c7.metric("⚙️ Fonksiyonel Vaka", len(get_data(sheet, "fonksiyonel")))
            c8.metric("👨‍⚕️ Toplam Kullanıcı", len(get_data(sheet, "users")))
            
            st.info("💡 Detaylı analizler ve grafikler için sol menüden 'İstatistik ve Analiz' sekmesine gidebilirsiniz.")
        except: pass

    elif choice == "Vasküler":
        st.header("🩸 Serebrovasküler")
        with st.form("v_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            st.markdown("**Klinik ve Radyolojik Skorlamalar**")
            c1, c2, c3 = st.columns(3)
            gks = c1.slider("Geliş GKS", 3, 15, 15)
            mrs = c2.selectbox("Modifiye Rankin Skoru (mRS)", ["Değerlendirilmedi", "0", "1", "2", "3", "4", "5", "6 (Eksitus)"])
            fisher = c3.selectbox("Fisher Skoru (SAK)", ["Değerlendirilmedi", "Evre 1", "Evre 2", "Evre 3", "Evre 4"])
            
            c4, c5, c6 = st.columns(3)
            hunt_hess = c4.selectbox("Hunt-Hess (SAK)", ["Değerlendirilmedi", "Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5"])
            ich_skoru = c5.selectbox("ICH Skoru (İntraserebral Kanama)", ["Değerlendirilmedi", "0", "1", "2", "3", "4", "5", "6"])
            spetzler = c6.selectbox("Spetzler-Martin (AVM)", ["Değerlendirilmedi", "Grade I", "Grade II", "Grade III", "Grade IV", "Grade V"])
            
            c7, c8 = st.columns(2)
            ogilvy = c7.selectbox("Ogilvy-Carter Skoru", ["Değerlendirilmedi", "0", "1", "2", "3", "4", "5"])
            sahss = c8.selectbox("SAHSS (SAH Sekela Skalası)", ["Değerlendirilmedi", "İyi", "Orta", "Kötü"])
            
            st.markdown("**Tanı ve Lokasyon Bilgileri**")
            t_col1, t_col2 = st.columns(2)
            tani = t_col1.selectbox("Klinik Tanı", ["Anevrizma", "Arteriovenöz Malformasyon (AVM)", "Kavernom", "Dural AVF / Spinal AVF", "İntraserebral Kanama (Primer)", "Moyamoya", "İskemik İnme / Karotis Stenozu", "Galen Veni Anevrizması", "Diğer"])
            lokasyon = t_col2.selectbox("Anatomik Lokasyon", ["ACA / ACoA", "MCA", "ICA / PCoA", "Baziler / PCA / Vertebral", "Lober (Kortikal/Subkortikal)", "Bazal Ganglion / Talamus", "Spinal", "Diğer"])
            
            notlar = st.text_area("Cerrahi Notlar / Komplikasyonlar / Ek Bilgiler")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "gks": gks, "mrs": mrs, "fisher": fisher, "hunt_hess": hunt_hess, "ich_skoru": ich_skoru, "spetzler": spetzler, "ogilvy_carter": ogilvy, "sahss": sahss, "tani": tani, "lokasyon": lokasyon, 
                        "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("vaskuler", veri)

    elif choice == "Nöro-Onkoloji":
        st.header("🧬 Nöro-Onkoloji")
        with st.form("o_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            st.markdown("**Tümör Özellikleri ve Skorlamalar**")
            c1, c2, c3 = st.columns(3)
            tip = c1.selectbox("Tümör Tipi", ["Glial Tümör (Yüksek Dereceli)", "Glial Tümör (Düşük Dereceli)", "Menenjiyom", "Metastaz", "Schwannom", "Kafa Tabanı Tümörü", "SSS Lenfoması", "Diğer"])
            who_grade = c2.selectbox("WHO Derecesi", ["Değerlendirilmedi", "Grade 1", "Grade 2", "Grade 3", "Grade 4"])
            idh_durumu = c3.selectbox("IDH Mutasyon Durumu", ["Bilinmiyor", "Mutant", "Wild-type"])

            c4, c5, c6 = st.columns(3)
            kps = c4.slider("Karnofsky Skoru (KPS)", 0, 100, 80, step=10)
            ds_gpa = c5.selectbox("DS-GPA Skoru (Metastaz İçin)", ["Değerlendirilmedi", "0.0 - 1.0", "1.5 - 2.5", "3.0 - 4.0"])
            rezeksiyon = c6.selectbox("Rezeksiyon Oranı", ["Gross Total (GTR)", "Subtotal (STR)", "Parsiyel", "Biyopsi"])
            
            st.markdown("**Lokasyon Bilgisi**")
            lokasyon = st.selectbox("Anatomik Lokasyon", ["Frontal", "Temporal", "Parietal", "Oksipital", "Serebellar / Posterior Fossa", "Kafa Tabanı", "Beyin Sapı / Mezensefalon", "Ventriküliçi", "Spinal İntramedüller", "Spinal Ekstramedüller", "Diğer"])
            
            notlar = st.text_area("Cerrahi Notlar / Patoloji Detayları / Ek Bilgiler")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "tip": tip, "who_grade": who_grade, "idh_durumu": idh_durumu, "kps": kps, "ds_gpa": ds_gpa, "lokasyon": lokasyon, "rezeksiyon": rezeksiyon, 
                        "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("onkoloji", veri)

    elif choice == "Epilepsi":
        st.header("🧠 Epilepsi Cerrahisi")
        with st.form("e_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            c1, c2 = st.columns(2)
            cerrahi = c1.selectbox("Cerrahi Yöntem", ["VNS İmplantasyonu", "Amigdalohipokampektomi", "Lezyonektomi", "Korpus Kallozotomi", "Grid / Strip Yerleştirilmesi", "Diğer"])
            engel = c2.selectbox("Engel Sınıflaması (Post-op Hedef/Sonuç)", ["Değerlendirilmedi", "Sınıf I", "Sınıf II", "Sınıf III", "Sınıf IV"])
            
            notlar = st.text_area("Klinik Notlar / Nöbet Paterni / Ek Bilgiler")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "cerrahi": cerrahi, "engel_skoru": engel, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("epilepsi", veri)

    elif choice == "Omurga":
        st.header("🦴 Spinal Cerrahi")
        with st.form("s_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            st.markdown("**Spinal Skorlamalar**")
            c1, c2, c3, c4 = st.columns(4)
            patoloji = c1.selectbox("Patoloji", ["Lomber Disk Hernisi", "Servikal Disk Hernisi", "Spinal Stenoz", "Spondilolistezis", "Spinal Travma", "Spinal Kist Hidatik", "Tarlov Kisti", "Spinal Tümör", "Diğer"])
            asia = c2.selectbox("ASIA Skoru", ["Değerlendirilmedi", "A", "B", "C", "D", "E"])
            vas = c3.slider("VAS Ağrı Skoru (0-10)", 0, 10, 5)
            odi_ndi = c4.number_input("ODI / NDI (%)", 0, 100, 0)
            
            st.markdown("**Lokasyon Bilgisi**")
            seviye = st.selectbox("Spinal Seviye / Bölge", ["Servikal", "Torakal", "Lomber", "Lumbosakral", "Kraniyoservikal Bileşke", "Skolyoz / Deformite (Tüm Omurga)", "Diğer"])
            
            notlar = st.text_area("Enstrümantasyon Detayları / Tam Seviye (Örn: L4-L5) / Notlar")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "patoloji": patoloji, "asia": asia, "vas_skoru": vas, "odi_ndi": odi_ndi, "seviye": seviye, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("omurga", veri)

    elif choice == "Pediatrik":
        st.header("👶 Pediatrik Nöroşirürji")
        with st.form("p_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            c1, c2 = st.columns(2)
            kategori = c1.selectbox("Patoloji Kategorisi", ["Kraniosinostoz", "Hidrosefali", "Meningomyelosel / Spinal Disrafizm", "Tethered Cord", "Pediatrik Tümör", "Vasküler (Galen Veni vb.)", "KİBA (Kitle Olmadan)", "Diğer"])
            
            tani = c2.selectbox("Spesifik Tanı / Patoloji", [
                "Belirtilmemiş", 
                "İzole Sagittal Sinostoz (Skafosefali)", 
                "Tek Taraflı Koronal Sinostoz (Plagiosefali)", 
                "Bilateral Koronal Sinostoz (Brakisefali)", 
                "Metopik Sinostoz (Trigonosefali)", 
                "Lambdoid Sinostoz", 
                "Sendromik (Apert / Crouzon / Pfeiffer vb.)", 
                "Dandy-Walker Varyantı / Malformasyonu", 
                "Araknoid Kist", 
                "Medulloblastom", 
                "Talamik Gliom", 
                "Ependimom", 
                "Diğer"
            ])
            
            notlar = st.text_area("Cerrahi Notlar / EVD-Şant Takibi / Ek Bilgiler")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "kategori": kategori, "tani": tani, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("pediatrik", veri)

    elif choice == "Fonksiyonel":
        st.header("⚙️ Fonksiyonel Nöroşirürji")
        with st.form("f_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            c1, c2 = st.columns(2)
            tur = c1.selectbox("Girişim Türü", ["Derin Beyin Stimülasyonu (DBS)", "Baklofen Pompası", "Ağrı Pili / Spinal Kord Stimülatörü", "Lezyon Cerrahisi", "Diğer"])
            hedef = c2.selectbox("Hedef Çekirdek / Bölge", ["Uygulanamaz / Diğer", "STN (Subtalamik Nükleus)", "GPi (Globus Pallidus İnternus)", "VIM (Ventralis İntermedius)", "Ant. Nükleus (Talamus)", "Spinal Kord", "Periferik Sinir"])
            
            notlar = st.text_area("Programlama Parametreleri / Notlar")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "tur": tur, "hedef": hedef, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("fonksiyonel", veri)

    elif choice == "Travma":
        st.header("🚑 Nörotravma")
        with st.form("t_form"):
            protokol, ad, yas, cinsiyet, yatis, link_dicom, link_video, link_ek = hasta_kimlik_ui()
            
            st.markdown("**Travma Skorlamaları**")
            c1, c2, c3, c4 = st.columns(4)
            gks = c1.slider("Geliş GKS", 3, 15, 15)
            marshall = c2.selectbox("Marshall Skoru", ["Değerlendirilmedi", "Grade I", "Grade II", "Grade III", "Grade IV", "Grade V (Kitle)", "Grade VI"])
            rotterdam = c3.selectbox("Rotterdam Skoru", ["Değerlendirilmedi", "1", "2", "3", "4", "5", "6"])
            gose = c4.selectbox("GOSE (Sonuç Skoru)", ["Değerlendirilmedi", "1 (Ölüm)", "2 (Vejetatif)", "3 (Ağır Engelli-Alt)", "4 (Ağır Engelli-Üst)", "5 (Orta Engelli)", "6 (İyi İyileşme)"])
            
            tani = st.selectbox("Primer Tanı", ["Akut Subdural Hematom (ASDH)", "Epidural Hematom (EDH)", "Kronik Subdural Hematom (KSDH)", "Serebral Kontüzyon / İntraparankimal", "Travmatik Subaraknoid Kanama (tSAK)", "Kafatası Çökme Kırığı", "Yaygın Aksonal Yaralanma (YAY)", "Spinal Kord Yaralanması", "Diğer"])
            notlar = st.text_area("İntrakraniyal Basınç (ICP) Takibi / Müdahale Detayları")
            
            if st.form_submit_button("Kaydet"):
                veri = {"tarih": bugun, "protokol": protokol, "ad": ad, "yas": yas, "cinsiyet": cinsiyet, "yatis": yatis, 
                        "gks": gks, "marshall": marshall, "rotterdam": rotterdam, "gose": gose, "tani": tani, "link_dicom": link_dicom, "link_video": link_video, "link_ek": link_ek, "kaydeden": st.session_state['username'], "notlar": notlar}
                kaydet("travma", veri)

    elif choice == "👨‍🏫 Süpervizör Paneli":
        st.title("👨‍🏫 Süpervizör Onay Paneli")
        modul = st.selectbox("İncelenecek Veritabanı", ["vaskuler", "onkoloji", "epilepsi", "omurga", "pediatrik", "fonksiyonel", "travma"])
        df = get_data(sheet, modul)
        
        if not df.empty and 'onay_durumu' in df.columns:
            bekleyenler = df[df['onay_durumu'] != "Onaylandı"]
            if not bekleyenler.empty:
                for index, row in bekleyenler.iterrows():
                    with st.expander(f"📌 {row.get('ad', 'İsimsiz')} | {row.get('tarih','')} | Ekleyen: {row.get('kaydeden', '')}"):
                        if row.get('link_dicom'): st.markdown(f"- [DICOM/MR Linki]({row['link_dicom']})")
                        if row.get('link_video'): st.markdown(f"- [Video Linki]({row['link_video']})")
                        if row.get('link_ek'): st.markdown(f"- [Ek Dosya Linki]({row['link_ek']})")
                        
                        gosterilecek = {k: v for k, v in row.items() if k not in ['id', 'onay_durumu', 'supervizor_notu', 'link_dicom', 'link_video', 'link_ek']}
                        st.write(gosterilecek)
                        
                        s_not = st.text_area("Süpervizör Notu", key=f"not_{row['id']}")
                        if st.button("Onayla", key=f"btn_{row['id']}"):
                            try:
                                ws = sheet.worksheet(modul)
                                cell = ws.find(str(row['id']))
                                ws.update_cell(cell.row, ws.find("onay_durumu").col, "Onaylandı")
                                ws.update_cell(cell.row, ws.find("supervizor_notu").col, s_not)
                                st.success("Onaylandı."); time.sleep(1); st.rerun()
                            except Exception as e: st.error(f"Hata: {e}")
            else: st.success("Onay bekleyen vaka bulunmuyor.")
        else: st.warning("Kayıt yok.")

    elif choice == "📈 İstatistik ve Analiz":
        st.title("📈 İstatistik ve Veri Analizi")
        st.info("İstatistiksel analiz için modül seçin. Tüm verileri tablonun sağ üstündeki indirme butonundan (CSV formatında) alıp SPSS vb. programlara aktarabilirsiniz.")
        
        analiz_modul = st.selectbox("Analiz Edilecek Klinik", ["vaskuler", "onkoloji", "epilepsi", "omurga", "pediatrik", "fonksiyonel", "travma"])
        df = get_data(sheet, analiz_modul)
        
        if not df.empty:
            c1, c2 = st.columns(2)
            c1.metric("Toplam Vaka", len(df))
            try:
                df['yas'] = pd.to_numeric(df['yas'], errors='coerce')
                c2.metric("Yaş Ortalaması", f"{df['yas'].mean():.1f}")
            except: pass
            
            st.divider()
            col3, col4 = st.columns(2)
            with col3:
                st.markdown("**Cinsiyet Dağılımı**")
                if 'cinsiyet' in df.columns: st.bar_chart(df['cinsiyet'].value_counts())
            
            with col4:
                if analiz_modul == "onkoloji" and 'tip' in df.columns:
                    st.markdown("**Tümör Tipi Dağılımı**")
                    st.bar_chart(df['tip'].value_counts())
                elif analiz_modul == "omurga" and 'patoloji' in df.columns:
                    st.markdown("**Patoloji Dağılımı**")
                    st.bar_chart(df['patoloji'].value_counts())
                elif analiz_modul == "vaskuler" and 'tani' in df.columns:
                    st.markdown("**Klinik Tanı Dağılımı**")
                    st.bar_chart(df['tani'].value_counts())
                elif analiz_modul == "travma" and 'tani' in df.columns:
                    st.markdown("**Travma Tanı Dağılımı**")
                    st.bar_chart(df['tani'].value_counts())
                elif analiz_modul == "pediatrik" and 'tani' in df.columns:
                    st.markdown("**Spesifik Tanı Dağılımı**")
                    st.bar_chart(df['tani'].value_counts())
                else:
                    st.markdown("**Son Eklenen Vakalar**")
                    st.write(df[['tarih', 'ad', 'yas', 'cinsiyet']].tail(5))
            
            st.divider()
            st.markdown("### 📥 Tüm Veritabanı")
            st.dataframe(df)
        else:
            st.warning("Veri bulunamadı.")

    elif choice == "👥 Kullanıcı Yönetimi":
        st.title("👥 Kadro Yönetimi")
        with st.form("add_user"):
            u = st.text_input("Kullanıcı Adı")
            p = st.text_input("Şifre", type='password')
            r = st.selectbox("Rol", ["Asistan", "Yönetici"])
            if st.form_submit_button("Ekle"):
                try:
                    ws = ensure_worksheet(sheet, "users")
                    if u in ws.col_values(1): st.error("Kullanıcı mevcut!")
                    else: ws.append_row([u, make_hashes(p), r]); st.success("Eklendi!"); time.sleep(1); st.rerun()
                except: pass
        
        st.divider()
        users_df = get_data(sheet, "users")
        if not users_df.empty:
            silinecekler = users_df[users_df['username'] != 'admin']['username'].tolist()
            if silinecekler:
                sil = st.selectbox("Kullanıcıyı Sil", silinecekler)
                if st.button("❌ Sil"):
                    ws = sheet.worksheet("users"); cell = ws.find(sil); ws.delete_rows(cell.row); st.success("Silindi."); time.sleep(1); st.rerun()

    elif choice == "Çıkış":
        st.session_state.clear()
        st.rerun()
