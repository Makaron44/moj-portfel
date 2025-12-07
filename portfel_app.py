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
            # Wczytujemy główny arkusz (Arkusz1 - domyślny)
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
            # Wczytujemy zakładkę 'limity'
            df_limity = self.conn.read(worksheet="limity", ttl=0)
            df_limity = df_limity.dropna(how="all")
            return df_limity
        except Exception:
            # Jeśli nie ma zakładki limity, zwracamy pusty, żeby program nie padł
            return pd.DataFrame(columns=["kategoria", "limit"])

    def dodaj_transakcje(self, typ, kwota, kategoria, opis):
        if kwota <= 0:
            return False, "Kwota musi być dodatnia!"
        
        df = self.wczytaj_dane()
        nowa_transakcja = pd.DataFrame([{
            "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 
            "typ": typ,
            "kategoria": kategoria,
            "kwota": kwota if typ == "Wpływ" else -kwota,
            "opis": opis
        }])
        
        if not df.empty:
             df["data"] = df["data"].dt.strftime("%Y-%m-%d %H:%M")

        nowy_df = pd.concat([df, nowa_transakcja], ignore_index=True)
        try:
            self.conn.update(data=nowy_df)
            return True, "Dodano pomyślnie!"
        except Exception as e:
            return False, f"Błąd zapisu: {e}"

    def oblicz_saldo(self):
        df = self.wczytaj_dane()
        if df.empty:
            return 0.0
        return df["kwota"].sum()

portfel = PortfelGoogle()

# --- PASEK BOCZNY ---
st.sidebar.title("Panel Sterowania")
st.sidebar.info(f"Zalogowano jako Administrator")
if st.sidebar.button("Wyloguj"):
    st.session_state["zalogowany"] = False
    st.rerun()

# --- NAGŁÓWEK ---
st.title("💰 Twój Wirtualny Portfel")

saldo = portfel.oblicz_saldo()
delta_color = "normal" if saldo >= 0 else "inverse"
st.metric(label="Aktualne Saldo", value=f"{saldo:.2f} PLN", delta=f"Stan konta", delta_color=delta_color)

st.divider()

# --- DODAWANIE ---
with st.expander("➕ Dodaj nową transakcję", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        typ_transakcji = st.radio("Rodzaj:", ["Wydatek", "Wpływ"], horizontal=True)
    with col2:
        kwota_input = st.number_input("Kwota (PLN):", min_value=0.0, format="%.2f", step=1.0)
    with col3:
        kategorie = ["Jedzenie", "Rachunki", "Transport", "Rozrywka", "Inne", "Wypłata", "Paliwo"]
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

# --- ZAKŁADKI GŁÓWNE ---
tab1, tab2, tab3 = st.tabs(["📊 Budżet (Limity)", "📋 Historia i Filtry", "📈 Analiza Wykresowa"])

# Pobieramy dane raz
df = portfel.wczytaj_dane()

# === ZAKŁADKA 1: STRAŻNIK BUDŻETU ===
with tab1:
    st.subheader("Twój miesięczny budżet")
    
    # 1. Pobieramy limity z Excela
    df_limity = portfel.wczytaj_limity()
    
    if df_limity.empty:
        st.warning("⚠️ Nie zdefiniowano limitów w arkuszu! Utwórz zakładkę 'limity' w Google Sheets.")
        st.info("Kolumny: kategoria | limit")
    elif df.empty:
        st.info("Brak wydatków do analizy.")
    else:
        # 2. Obliczamy wydatki w TYM miesiącu (żeby budżet był miesięczny)
        obecny_miesiac = datetime.datetime.now().month
        obecny_rok = datetime.datetime.now().year
        
        # Filtrujemy tylko ten miesiąc
        df_ten_miesiac = df[
            (df["data"].dt.month == obecny_miesiac) & 
            (df["data"].dt.year == obecny_rok) &
            (df["typ"] == "Wydatek")
        ].copy()
        
        # Sumujemy wydatki per kategoria (zamieniamy na liczbę dodatnią)
        df_ten_miesiac["kwota"] = df_ten_miesiac["kwota"].abs()
        wydatki_suma = df_ten_miesiac.groupby("kategoria")["kwota"].sum()

        # 3. Rysujemy paski dla każdego limitu
        for index, row in df_limity.iterrows():
            kat = row['kategoria']
            limit = float(row['limit'])
            
            # Ile wydaliśmy w tej kategorii? (Jeśli nic, to 0)
            wydano = wydatki_suma.get(kat, 0.0)
            
            # Obliczamy procent
            procent = min(wydano / limit, 1.0) # max 100% dla paska
            
            # Kolumny do ładnego wyświetlania
            c1, c2 = st.columns([3, 1])
            with c1:
                st.write(f"**{kat}**")
                # Kolor paska zależy od zużycia
                bar_color = "green"
                if procent > 0.75: bar_color = "orange" 
                if procent >= 1.0: bar_color = "red"
                
                st.progress(procent)
            with c2:
                st.write(f"{wydano:.2f} / {limit:.2f} PLN")
                if wydano > limit:
                    st.caption(f"🚨 Przekroczono o {wydano - limit:.2f} zł!")

# === ZAKŁADKA 2: HISTORIA I FILTRY ===
with tab2:
    if not df.empty:
        f_col1, f_col2, f_col3 = st.columns(3)
        with f_col1:
            dostepne_kategorie = df["kategoria"].unique().tolist()
            wybrane_kategorie = st.multiselect("Filtruj kategorie:", dostepne_kategorie, default=dostepne_kategorie)
        with f_col2:
            min_data = df["data"].min().date()
            max_data = df["data"].max().date()
            data_od, data_do = st.date_input("Zakres dat:", [min_data, max_data])
        
        maska_kategorii = df["kategoria"].isin(wybrane_kategorie)
        maska_daty = (df["data"].dt.date >= data_od) & (df["data"].dt.date <= data_do)
        df_przefiltrowane = df[maska_kategorii & maska_daty].copy().sort_values(by="data", ascending=False)
        
        suma_filtrowana = df_przefiltrowane["kwota"].sum()
        with f_col3:
            st.markdown("**Suma wybranych:**")
            kolor = "green" if suma_filtrowana >= 0 else "red"
            st.markdown(f"<h3 style='color: {kolor};'>{suma_filtrowana:.2f} PLN</h3>", unsafe_allow_html=True)

        def koloruj_kwoty(val):
            color = 'red' if val < 0 else 'green'
            return f'color: {color}; font-weight: bold;'

        df_display = df_przefiltrowane.copy()
        df_display["data"] = df_display["data"].dt.strftime("%Y-%m-%d %H:%M")
        
        st.dataframe(
            df_display.style.map(koloruj_kwoty, subset=['kwota']).format({"kwota": "{:.2f} PLN"}),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("Brak danych.")

# === ZAKŁADKA 3: WYKRESY ===
with tab3:
    if not df.empty:
        wydatki = df[df["kwota"] < 0].copy()
        if not wydatki.empty:
            wydatki["kwota"] = wydatki["kwota"].abs()
            
            c1, c2 = st.columns(2)
            with c1:
                st.subheader("Struktura wydatków")
                wykres = wydatki.groupby("kategoria")["kwota"].sum()
                st.bar_chart(wykres)
            with c2:
                st.subheader("Top wydatki")
                # Pokazujemy 5 najdroższych transakcji
                top5 = wydatki.sort_values(by="kwota", ascending=False).head(5)
                for i, row in top5.iterrows():
                    st.write(f"💸 **{row['kwota']:.2f} zł** - {row['opis']} ({row['data'].strftime('%Y-%m-%d')})")
        else:
            st.write("Brak wydatków.")

