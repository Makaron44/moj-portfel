import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Mój Portfel", page_icon="💰", layout="wide")

# ==========================================
# --- BRAMKARZ (LOGOWANIE) ---
# ==========================================
def sprawdz_haslo():
    if "zalogowany" not in st.session_state:
        st.session_state["zalogowany"] = False
    if st.session_state["zalogowany"]:
        return True
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.header("🔒 Logowanie")
        haslo_input = st.text_input("Podaj hasło dostępu:", type="password")
        if st.button("Zaloguj", use_container_width=True):
            if haslo_input == st.secrets["password"]:
                st.session_state["zalogowany"] = True
                st.rerun()
            else:
                st.error("Nieprawidłowe hasło!")
    return False

if not sprawdz_haslo():
    st.stop()

# ==========================================
# --- SILNIK (GOOGLE SHEETS) ---
# ==========================================
class PortfelGoogle:
    def __init__(self):
        self.conn = st.connection("gsheets", type=GSheetsConnection)
        
    def wczytaj_dane(self):
        try:
            df = self.conn.read(ttl=0)
            if df.empty:
                return pd.DataFrame(columns=["data", "typ", "kategoria", "kwota", "opis"])
            df = df.dropna(how="all")
            if "data" in df.columns:
                df["data"] = pd.to_datetime(df["data"], errors='coerce')
            return df
        except Exception as e:
            st.error(f"Błąd połączenia z Arkuszem: {e}")
            return pd.DataFrame(columns=["data", "typ", "kategoria", "kwota", "opis"])

    def wczytaj_limity(self):
        try:
            df_limity = self.conn.read(worksheet="limity", ttl=0)
            df_limity = df_limity.dropna(how="all")
            return df_limity
        except Exception:
            return pd.DataFrame(columns=["kategoria", "limit"])

    def dodaj_transakcje(self, typ, kwota, kategoria, opis):
        if kwota <= 0: return False, "Kwota musi być dodatnia!"
        
        df = self.wczytaj_dane()
        nowa_transakcja = pd.DataFrame([{
            "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 
            "typ": typ,
            "kategoria": kategoria,
            "kwota": kwota if typ == "Wpływ" else -kwota,
            "opis": opis
        }])
        
        if not df.empty: df["data"] = df["data"].dt.strftime("%Y-%m-%d %H:%M")
        nowy_df = pd.concat([df, nowa_transakcja], ignore_index=True)
        
        try:
            self.conn.update(data=nowy_df)
            return True, "Dodano pomyślnie!"
        except Exception as e:
            return False, f"Błąd zapisu: {e}"

    # --- NOWA FUNKCJA: AUTOMAT ---
    def dodaj_cykliczne(self):
        try:
            # 1. Wczytaj definicje z zakładki 'cykliczne'
            df_cykliczne = self.conn.read(worksheet="cykliczne", ttl=0)
            df_cykliczne = df_cykliczne.dropna(how="all")
            
            if df_cykliczne.empty:
                return False, "Zakładka 'cykliczne' jest pusta!"
            
            # 2. Przygotuj dane do dodania
            nowe_wiersze = []
            teraz = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            suma_dodana = 0
            licznik = 0
            
            for index, row in df_cykliczne.iterrows():
                kwota_baza = float(row['kwota'])
                kwota_final = kwota_baza if row['typ'] == "Wpływ" else -kwota_baza
                
                nowe_wiersze.append({
                    "data": teraz,
                    "typ": row['typ'],
                    "kategoria": row['kategoria'],
                    "kwota": kwota_final,
                    "opis": row['opis'] + " (Auto)" # Dodajemy dopisek Auto
                })
                suma_dodana += kwota_final
                licznik += 1
            
            # 3. Dodaj do głównej bazy
            df_main = self.wczytaj_dane()
            if not df_main.empty: df_main["data"] = df_main["data"].dt.strftime("%Y-%m-%d %H:%M")
            
            df_nowe = pd.DataFrame(nowe_wiersze)
            df_final = pd.concat([df_main, df_nowe], ignore_index=True)
            
            self.conn.update(data=df_final)
            return True, f"Dodano {licznik} operacji na sumę {suma_dodana:.2f} PLN"
            
        except Exception as e:
            return False, f"Błąd automatu: {e} (Sprawdź czy masz zakładkę 'cykliczne')"

    def oblicz_saldo(self):
        df = self.wczytaj_dane()
        if df.empty: return 0.0
        return df["kwota"].sum()

portfel = PortfelGoogle()

# --- PASEK BOCZNY ---
st.sidebar.title("Panel Sterowania")
st.sidebar.info(f"Zalogowano jako Administrator")

# === NOWOŚĆ: Przycisk Cykliczne ===
st.sidebar.markdown("---")
st.sidebar.write("⚡ **Szybkie akcje**")
if st.sidebar.button("🔄 Dodaj płatności cykliczne"):
    with st.spinner("Przetwarzam stałe opłaty..."):
        sukces, msg = portfel.dodaj_cykliczne()
        if sukces:
            st.toast(msg, icon="✅") # Nowoczesne powiadomienie dymek
            st.rerun()
        else:
            st.error(msg)
st.sidebar.markdown("---")

if st.sidebar.button("Wyloguj"):
    st.session_state["zalogowany"] = False
    st.rerun()

# --- GŁÓWNA CZĘŚĆ ---
st.title("💰 Twój Wirtualny Portfel")

saldo = portfel.oblicz_saldo()
delta_color = "normal" if saldo >= 0 else "inverse"
st.metric(label="Aktualne Saldo", value=f"{saldo:.2f} PLN", delta=f"Stan konta", delta_color=delta_color)

st.divider()

# --- DODAWANIE ---
with st.expander("➕ Dodaj pojedynczą transakcję", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        typ_transakcji = st.radio("Rodzaj:", ["Wydatek", "Wpływ"], horizontal=True)
    with col2:
        kwota_input = st.number_input("Kwota (PLN):", min_value=0.0, format="%.2f", step=1.0)
    with col3:
        kategorie = ["Jedzenie", "Rachunki", "Transport", "Rozrywka", "Inne", "Wypłata", "Paliwo", "Dom", "Zdrowie"]
        if typ_transakcji == "Wpływ":
            kat_input = "Wpływ"
        else:
            kat_input = st.selectbox("Kategoria:", kategorie)
    with col4:
        opis_input = st.text_input("Opis:")
        if st.button("Zapisz transakcję", use_container_width=True):
            with st.spinner("Zapisuję..."):
                sukces, komunikat = portfel.dodaj_transakcje(typ_transakcji, kwota_input, kat_input, opis_input)
                if sukces:
                    st.success(f"{komunikat}")
                    st.rerun()
                else:
                    st.error(komunikat)

# --- ZAKŁADKI ---
tab1, tab2, tab3 = st.tabs(["📊 Budżet (Limity)", "📋 Historia i Filtry", "📈 Analiza Wykresowa"])

df = portfel.wczytaj_dane()

# === TAB 1: BUDŻET ===
with tab1:
    st.subheader("Twój miesięczny budżet")
    df_limity = portfel.wczytaj_limity()
    if df_limity.empty:
        st.warning("⚠️ Brak zakładki 'limity' w arkuszu.")
    elif df.empty:
        st.info("Brak wydatków.")
    else:
        obecny_miesiac = datetime.datetime.now().month
        obecny_rok = datetime.datetime.now().year
        df_ten_miesiac = df[(df["data"].dt.month == obecny_miesiac) & (df["data"].dt.year == obecny_rok) & (df["typ"] == "Wydatek")].copy()
        df_ten_miesiac["kwota"] = df_ten_miesiac["kwota"].abs()
        wydatki_suma = df_ten_miesiac.groupby("kategoria")["kwota"].sum()

        for index, row in df_limity.iterrows():
            kat = row['kategoria']
            limit = float(row['limit'])
            wydano = wydatki_suma.get(kat, 0.0)
            procent = min(wydano / limit, 1.0)
            
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{kat}**")
                st.progress(procent)
            with c2:
                st.write(f"{wydano:.2f} / {limit:.2f} PLN")
                if wydano > limit: st.caption(f"🚨 +{wydano - limit:.2f} zł")

# === TAB 2: HISTORIA ===
with tab2:
    if not df.empty:
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            dostepne_kategorie = df["kategoria"].unique().tolist()
            wybrane_kategorie = st.multiselect("Filtruj:", dostepne_kategorie, default=dostepne_kategorie)
        with f_col2:
            min_d = df["data"].min().date()
            max_d = df["data"].max().date()
            d_od, d_do = st.date_input("Zakres:", [min_d, max_d])
        
        maska = df["kategoria"].isin(wybrane_kategorie) & (df["data"].dt.date >= d_od) & (df["data"].dt.date <= d_do)
        df_f = df[maska].copy().sort_values(by="data", ascending=False)
        
        suma = df_f["kwota"].sum()
        with f_col3:
            kolor = "green" if suma >= 0 else "red"
            st.markdown(f"Suma: <span style='color:{kolor}; font-size: 1.5em; font-weight:bold'>{suma:.2f} PLN</span>", unsafe_allow_html=True)

        def koloruj(val): return f'color: {"red" if val < 0 else "green"}; font-weight: bold;'
        df_disp = df_f.copy()
        df_disp["data"] = df_disp["data"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(df_disp.style.map(koloruj, subset=['kwota']).format({"kwota": "{:.2f} PLN"}), use_container_width=True, hide_index=True)
    else:
        st.info("Brak danych.")

# === TAB 3: WYKRESY ===
with tab3:
    if not df.empty:
        wyd = df[df["kwota"] < 0].copy()
        if not wyd.empty:
            wyd["kwota"] = wyd["kwota"].abs()
            c1, c2 = st.columns(2)
            with c1: st.bar_chart(wyd.groupby("kategoria")["kwota"].sum())
            with c2:
                st.write("**Top 5 wydatków:**")
                for i, r in wyd.sort_values("kwota", ascending=False).head(5).iterrows():
                    st.write(f"💸 {r['kwota']:.2f} zł - {r['opis']}")
        else: st.write("Brak wydatków.")
