import streamlit as st
import datetime
import json
import os
import pandas as pd # Biblioteka do ładnych tabelek i wykresów

PLIK_DANYCH = "moj_portfel.json"

# --- LOGIKA (SILNIK) ---
class WirtualnyPortfel:
    def __init__(self):
        self.saldo = 0.0
        self.historia = []
        self.wczytaj_dane()

    def wczytaj_dane(self):
        if os.path.exists(PLIK_DANYCH):
            try:
                with open(PLIK_DANYCH, "r", encoding='utf-8') as plik:
                    dane = json.load(plik)
                    self.saldo = dane.get("saldo", 0.0)
                    self.historia = dane.get("historia", [])
            except Exception as e:
                st.error(f"Błąd wczytywania danych: {e}")

    def zapisz_dane(self):
        dane_do_zapisu = {"saldo": self.saldo, "historia": self.historia}
        with open(PLIK_DANYCH, "w", encoding='utf-8') as plik:
            json.dump(dane_do_zapisu, plik, indent=4, ensure_ascii=False)

    def dodaj_transakcje(self, typ, kwota, kategoria, opis):
        if kwota > 0:
            if typ == "Wydatek" and kwota > self.saldo:
                return False, "Niewystarczające środki!"
            
            # Aktualizacja salda
            if typ == "Wpływ":
                self.saldo += kwota
            else:
                self.saldo -= kwota
            
            # Zapis do historii
            data = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
            transakcja = {
                "typ": typ,
                "kwota": kwota if typ == "Wpływ" else -kwota,
                "kategoria": kategoria,
                "opis": opis,
                "data": data
            }
            self.historia.append(transakcja)
            self.zapisz_dane()
            return True, "Dodano pomyślnie!"
        return False, "Kwota musi być dodatnia!"

# --- INTERFEJS (WYGLĄD) ---

# Ustawienia strony
st.set_page_config(page_title="Mój Portfel", page_icon="💰")

# Inicjalizacja portfela
portfel = WirtualnyPortfel()

st.title("💰 Twój Wirtualny Portfel")

# Wyświetlanie salda na górze (Duży licznik)
st.metric(label="Aktualne Saldo", value=f"{portfel.saldo:.2f} PLN")

# --- LEWY PANEL (DODAWANIE) ---
st.sidebar.header("Dodaj nową transakcję")
typ_transakcji = st.sidebar.radio("Rodzaj:", ["Wydatek", "Wpływ"])

kwota_input = st.sidebar.number_input("Kwota (PLN):", min_value=0.0, format="%.2f", step=1.0)
opis_input = st.sidebar.text_input("Opis (np. Zakupy):")

# Kategorie
kategorie = ["Jedzenie", "Rachunki", "Transport", "Rozrywka", "Inne", "Wypłata"]
if typ_transakcji == "Wpływ":
    kat_input = "Wpływ" # Automatycznie
else:
    kat_input = st.sidebar.selectbox("Kategoria:", kategorie)

if st.sidebar.button("Dodaj transakcję"):
    sukces, komunikat = portfel.dodaj_transakcje(typ_transakcji, kwota_input, kat_input, opis_input)
    if sukces:
        st.success(f"{komunikat} ({kwota_input} PLN)")
        # Odśwież stronę, żeby zaktualizować saldo
        st.rerun()
    else:
        st.error(komunikat)

# --- ŚRODEK (HISTORIA I WYKRESY) ---

# --- ŚRODEK (HISTORIA I WYKRESY - WERSJA Z ZAKŁADKAMI) ---

st.divider() # Linia oddzielająca

# Tworzymy dwie zakładki zamiast kolumn
tab1, tab2 = st.tabs(["📋 Historia Transakcji", "📊 Analiza Wydatków"])

with tab1:
    st.subheader("Ostatnie operacje")
    if portfel.historia:
        # Tworzymy tabelkę
        df = pd.DataFrame(portfel.historia)
        
        # SZYBKA NAPRAWA DANYCH:
        # Jeśli stare dane nie mają kategorii (są "None"), zamień je na "Inne"
        if "kategoria" not in df.columns:
            df["kategoria"] = "Inne"
        else:
            df["kategoria"] = df["kategoria"].fillna("Inne")

        # Wyświetlamy tabelę na całą szerokość
        st.dataframe(
            df[["data", "typ", "kategoria", "kwota", "opis"]].iloc[::-1], 
            use_container_width=True, # Rozciągnij na maxa
            hide_index=True
        )
    else:
        st.info("Brak historii transakcji.")

with tab2:
    st.subheader("Wydatki wg kategorii")
    if portfel.historia:
        # Filtrujemy tylko wydatki
        wydatki = [t for t in portfel.historia if t['typ'] == 'Wydatek']
        if wydatki:
            df_wydatki = pd.DataFrame(wydatki)
            
            # Zabezpieczenie przed brakiem kategorii w starych danych
            if "kategoria" not in df_wydatki.columns:
                df_wydatki["kategoria"] = "Inne"
            else:
                df_wydatki["kategoria"] = df_wydatki["kategoria"].fillna("Inne")

            df_wydatki['kwota'] = df_wydatki['kwota'].abs()
            
            # Grupujemy i sumujemy
            wykres_dane = df_wydatki.groupby("kategoria")["kwota"].sum()
            
            # Wyświetlamy wykres
            st.bar_chart(wykres_dane)
        else:
            st.write("Brak wydatków do pokazania na wykresie.")