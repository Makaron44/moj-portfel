import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Mój Portfel", page_icon="💰")

# --- SILNIK (GOOGLE SHEETS) ---
class PortfelGoogle:
    def __init__(self):
        # Nawiązujemy połączenie z Google Sheets
        self.conn = st.connection("gsheets", type=GSheetsConnection)
        
    def wczytaj_dane(self):
        try:
            # Czytamy dane z arkusza. ttl=0 oznacza "zawsze pobieraj świeże"
            df = self.conn.read(ttl=0)
            # Jeśli arkusz jest pusty lub ma same nagłówki, zwróć pusty DataFrame z odpowiednimi kolumnami
            if df.empty:
                return pd.DataFrame(columns=["data", "typ", "kategoria", "kwota", "opis"])
            
            # Usuwamy puste wiersze (jeśli są)
            df = df.dropna(how="all")
            
            # Upewniamy się, że kolumny są w dobrym formacie
            return df
        except Exception as e:
            st.error(f"Błąd połączenia z Arkuszem: {e}")
            return pd.DataFrame(columns=["data", "typ", "kategoria", "kwota", "opis"])

    def dodaj_transakcje(self, typ, kwota, kategoria, opis):
        if kwota <= 0:
            return False, "Kwota musi być dodatnia!"
        
        # Pobieramy aktualne dane, żeby mieć do czego dopisać
        df = self.wczytaj_dane()
        
        # Obliczamy saldo
        aktualne_saldo = df["kwota"].sum() if not df.empty else 0.0
        
        if typ == "Wydatek" and kwota > aktualne_saldo:
            return False, "Niewystarczające środki!"

        # Tworzymy nowy wiersz
        nowa_transakcja = pd.DataFrame([{
            "data": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
            "typ": typ,
            "kategoria": kategoria,
            "kwota": kwota if typ == "Wpływ" else -kwota,
            "opis": opis
        }])

        # Dodajemy do istniejących danych
        nowy_df = pd.concat([df, nowa_transakcja], ignore_index=True)
        
        # Wysyłamy do Google Sheets
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

st.title("💰 Twój Wirtualny Portfel (Online)")

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
    with st.spinner("Zapisuję w Google Sheets..."):
        sukces, komunikat = portfel.dodaj_transakcje(typ_transakcji, kwota_input, kat_input, opis_input)
        if sukces:
            st.success(f"{komunikat}")
            st.rerun()
        else:
            st.error(komunikat)

# --- ŚRODEK (ZAKŁADKI) ---
st.divider()

tab1, tab2 = st.tabs(["📋 Historia", "📊 Wykresy"])

# Pobieramy dane raz, żeby użyć w obu zakładkach
df_aktualne = portfel.wczytaj_dane()

with tab1:
    if not df_aktualne.empty:
        # Sortujemy od najnowszych
        if "data" in df_aktualne.columns:
             # Sortowanie proste (tekstowe) wystarczy na początek
             df_wyswietl = df_aktualne.sort_index(ascending=False)
        else:
             df_wyswietl = df_aktualne

        st.dataframe(df_wyswietl, use_container_width=True, hide_index=True)
    else:
        st.info("Arkusz jest pusty. Dodaj pierwszą transakcję!")

with tab2:
    if not df_aktualne.empty:
        # Filtrujemy wydatki
        wydatki = df_aktualne[df_aktualne["kwota"] < 0].copy()
        if not wydatki.empty:
            wydatki["kwota"] = wydatki["kwota"].abs()
            wykres = wydatki.groupby("kategoria")["kwota"].sum()
            st.bar_chart(wykres)
        else:
            st.write("Brak wydatków.")
    else:
        st.write("Brak danych.")
