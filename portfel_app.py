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
    
    st.header("🔒 Logowanie")
    haslo_input = st.text_input("Podaj hasło dostępu:", type="password")
    if st.button("Zaloguj"):
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
            # Konwersja kolumny 'data' na format daty (żeby można było filtrować)
            if "data" in df.columns:
                df["data"] = pd.to_datetime(df["data"], errors='coerce')
            return df
        except Exception as e:
            st.error(f"Błąd połączenia z Arkuszem: {e}")
            return pd.DataFrame(columns=["data", "typ", "kategoria", "kwota", "opis"])

    def dodaj_transakcje(self, typ, kwota, kategoria, opis):
        if kwota <= 0:
            return False, "Kwota musi być dodatnia!"
        
        df = self.wczytaj_dane()
        # Przy dodawaniu, data jest zapisywana jako tekst (dla czytelności w Excelu)
        nowa_transakcja = pd.DataFrame([{
            "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 
            "typ": typ,
            "kategoria": kategoria,
            "kwota": kwota if typ == "Wpływ" else -kwota,
            "opis": opis
        }])
        
        # Konwersja starego DF z powrotem na string, żeby pasował do nowej transakcji przy łączeniu
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

# Pasek boczny - opcje
st.sidebar.title("Panel Sterowania")
if st.sidebar.button("Wyloguj"):
    st.session_state["zalogowany"] = False
    st.rerun()

st.title("💰 Twój Wirtualny Portfel")

# Saldo
saldo = portfel.oblicz_saldo()
# Kolorowanie salda: zielone jak dodatnie, czerwone jak ujemne
delta_color = "normal" if saldo >= 0 else "inverse"
st.metric(label="Aktualne Saldo", value=f"{saldo:.2f} PLN", delta=f"{saldo:.2f} PLN", delta_color=delta_color)

st.divider()

# ==========================================
# --- DODAWANIE (W ukrywanej sekcji) ---
# ==========================================
with st.expander("➕ Dodaj nową transakcję", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        typ_transakcji = st.radio("Rodzaj:", ["Wydatek", "Wpływ"], horizontal=True)
    with col2:
        kwota_input = st.number_input("Kwota (PLN):", min_value=0.0, format="%.2f", step=1.0)
    with col3:
        kategorie = ["Jedzenie", "Rachunki", "Transport", "Rozrywka", "Inne", "Wypłata"]
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

# ==========================================
# --- FILTROWANIE I ANALIZA ---
# ==========================================
st.subheader("🔍 Przegląd i Filtrowanie")

# Pobieramy dane
df = portfel.wczytaj_dane()

if not df.empty:
    # 1. FILTRY (Umieszczamy je w poziomie nad tabelą)
    f_col1, f_col2, f_col3 = st.columns(3)
    
    with f_col1:
        # Filtr Kategorii (Multiselect - można wybrać kilka)
        dostepne_kategorie = df["kategoria"].unique().tolist()
        wybrane_kategorie = st.multiselect("Wybierz kategorie:", dostepne_kategorie, default=dostepne_kategorie)
    
    with f_col2:
        # Filtr Daty (Od - Do)
        min_data = df["data"].min().date()
        max_data = df["data"].max().date()
        # Domyślnie pokazujemy cały zakres
        data_od, data_do = st.date_input("Zakres dat:", [min_data, max_data])

    # 2. LOGIKA FILTROWANIA
    # Filtrujemy po kategoriach
    maska_kategorii = df["kategoria"].isin(wybrane_kategorie)
    # Filtrujemy po dacie (musimy uważać na godziny, więc bierzemy samą datę .dt.date)
    maska_daty = (df["data"].dt.date >= data_od) & (df["data"].dt.date <= data_do)
    
    # Nakładamy oba filtry na dane
    df_przefiltrowane = df[maska_kategorii & maska_daty].copy()

    # Sortujemy: najnowsze na górze
    df_przefiltrowane = df_przefiltrowane.sort_values(by="data", ascending=False)

    # 3. PODLICZENIE (To o co prosiłeś - suma tego co widać)
    suma_filtrowana = df_przefiltrowane["kwota"].sum()
    
    # Wyświetlamy podsumowanie filtra na kolorowo
    with f_col3:
        st.markdown(f"**Podsumowanie wybranych:**")
        if suma_filtrowana > 0:
            st.markdown(f"<h2 style='color: green;'>+{suma_filtrowana:.2f} PLN</h2>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h2 style='color: red;'>{suma_filtrowana:.2f} PLN</h2>", unsafe_allow_html=True)

    # 4. TABELA Z KOLORAMI (Wpływ na zielono, Wydatek na czerwono)
    
    # Funkcja kolorująca kwoty
    def koloruj_kwoty(val):
        color = 'red' if val < 0 else 'green'
        return f'color: {color}; font-weight: bold;'

    # Przygotowanie tabeli do wyświetlenia (Formatowanie daty na ładniejszą)
    df_display = df_przefiltrowane.copy()
    df_display["data"] = df_display["data"].dt.strftime("%Y-%m-%d %H:%M")
    
    # Wyświetlenie tabeli z kolorowaniem kolumny "kwota"
    st.dataframe(
        df_display.style.map(koloruj_kwoty, subset=['kwota']).format({"kwota": "{:.2f} PLN"}),
        use_container_width=True,
        hide_index=True
    )

else:
    st.info("Brak danych w portfelu. Dodaj coś!")
