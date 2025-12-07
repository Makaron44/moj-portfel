import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Mój Portfel", page_icon="💰")

# ==========================================
# --- BRAMKARZ (LOGOWANIE) ---
# ==========================================
def sprawdz_haslo():
    """Zwraca True jeśli użytkownik jest zalogowany, inaczej False"""
    if "zalogowany" not in st.session_state:
        st.session_state["zalogowany"] = False

    if st.session_state["zalogowany"]:
        return True

    st.header("🔒 Logowanie")
    haslo_input = st.text_input("Podaj hasło dostępu:", type="password")
    
    if st.button("Zaloguj"):
        # Sprawdzamy czy hasło pasuje do tego w Secrets
        if haslo_input == st.secrets["password"]:
            st.session_state["zalogowany"] = True
            st.rerun()  # Odświeżamy stronę, żeby wpuścić użytkownika
        else:
            st.error("Nieprawidłowe hasło!")
            
    return False

# JEŚLI HASŁO NIEPOPRAWNE -> ZATRZYMAJ PROGRAM TU
if not sprawdz_haslo():
    st.stop()

# ==========================================
# --- WŁAŚCIWA APLIKACJA (Dostępna po zalogowaniu) ---
# ==========================================

# --- SILNIK (GOOGLE SHEETS) ---
class PortfelGoogle:
    def __init__(self):
        self.conn = st.connection("gsheets", type=GSheetsConnection)
        
    def wczytaj_dane(self):
        try:
            df = self.conn.read(ttl=0)
            if df.empty:
                return pd.DataFrame(columns=["data", "typ", "kategoria", "kwota", "opis"])
            df = df.dropna(how="all")
            return df
        except Exception as e:
            st.error(f"Błąd połączenia z Arkuszem: {e}")
            return pd.DataFrame(columns=["data", "typ", "kategoria", "kwota", "opis"])

    def dodaj_transakcje(self, typ, kwota, kategoria, opis):
        if kwota <= 0:
            return False, "Kwota musi być dodatnia!"
        
        df = self.wczytaj_dane()
        aktualne_saldo = df["kwota"].sum() if not df.empty else 0.0
        
        if typ == "Wydatek" and kwota > aktualne_saldo:
            return False, "Niewystarczające środki!"

        nowa_transakcja = pd.DataFrame([{
            "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "typ": typ,
            "kategoria": kategoria,
            "kwota": kwota if typ == "Wpływ" else -kwota,
            "opis": opis
        }])

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

# Inicjalizacja
portfel = PortfelGoogle()

# Przycisk wylogowania na pasku bocznym
if st.sidebar.button("Wyloguj"):
    st.session_state["zalogowany"] = False
    st.rerun()

st.title("💰 Twój Wirtualny Portfel")

# --- WYŚWIETLANIE SALDA ---
saldo = portfel.oblicz_saldo()
st.metric(label="Aktualne Saldo", value=f"{saldo:.2f} PLN")

# --- LEWY PANEL (DODAWANIE) ---
st.sidebar.header("Dodaj nową transakcję")
typ_transakcji = st.sidebar.radio("Rodzaj:", ["Wydatek", "Wpływ"])

kwota_input = st.sidebar.number_input("Kwota (PLN):", min_value=0.0, format="%.2f", step=1.0)
opis_input = st.sidebar.text_input("Opis (np. Zakupy):")

kategorie = ["Jedzenie", "Rachunki", "Transport", "Rozrywka", "Inne", "Wypłata"]
if typ_transakcji == "Wpływ":
    kat_input = "Wpływ"
else:
    kat_input = st.sidebar.selectbox("Kategoria:", kategorie)

if st.sidebar.button("Dodaj transakcję"):
    with st.spinner("Zapisuję..."):
        sukces, komunikat = portfel.dodaj_transakcje(typ_transakcji, kwota_input, kat_input, opis_input)
        if sukces:
            st.success(f"{komunikat}")
            st.rerun()
        else:
            st.error(komunikat)

# --- ŚRODEK (ZAKŁADKI) ---
st.divider()

tab1, tab2 = st.tabs(["📋 Historia", "📊 Wykresy"])
df_aktualne = portfel.wczytaj_dane()

with tab1:
    if not df_aktualne.empty:
        if "data" in df_aktualne.columns:
             df_wyswietl = df_aktualne.sort_index(ascending=False)
        else:
             df_wyswietl = df_aktualne
        st.dataframe(df_wyswietl, use_container_width=True, hide_index=True)
    else:
        st.info("Arkusz jest pusty.")

with tab2:
    if not df_aktualne.empty:
        wydatki = df_aktualne[df_aktualne["kwota"] < 0].copy()
        if not wydatki.empty:
            wydatki["kwota"] = wydatki["kwota"].abs()
            wykres = wydatki.groupby("kategoria")["kwota"].sum()
            st.bar_chart(wykres)
        else:
            st.write("Brak wydatków.")
    else:
        st.write("Brak danych.")
