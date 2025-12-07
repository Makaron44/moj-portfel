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

    def dodaj_cykliczne(self):
        try:
            df_cykliczne = self.conn.read(worksheet="cykliczne", ttl=0)
            df_cykliczne = df_cykliczne.dropna(how="all")
            
            if df_cykliczne.empty: return False, "Zakładka 'cykliczne' jest pusta!"
            if "dzien" not in df_cykliczne.columns: return False, "Brak kolumny 'dzien'!"

            nowe_wiersze = []
            teraz = datetime.datetime.now()
            rok = teraz.year
            miesiac = teraz.month
            
            suma_dodana = 0
            licznik = 0
            
            for index, row in df_cykliczne.iterrows():
                kwota_baza = float(row['kwota'])
                kwota_final = kwota_baza if row['typ'] == "Wpływ" else -kwota_baza
                dzien_platnosci = int(row['dzien'])
                
                try:
                    data_transakcji = datetime.datetime(rok, miesiac, dzien_platnosci, 12, 0)
                except ValueError:
                    data_transakcji = teraz # Zabezpieczenie na koniec miesiąca

                nowe_wiersze.append({
                    "data": data_transakcji.strftime("%Y-%m-%d %H:%M"),
                    "typ": row['typ'],
                    "kategoria": row['kategoria'],
                    "kwota": kwota_final,
                    "opis": row['opis'] + " (Auto)"
                })
                suma_dodana += kwota_final
                licznik += 1
            
            df_main = self.wczytaj_dane()
            if not df_main.empty: df_main["data"] = df_main["data"].dt.strftime("%Y-%m-%d %H:%M")
            df_final = pd.concat([df_main, pd.DataFrame(nowe_wiersze)], ignore_index=True)
            self.conn.update(data=df_final)
            return True, f"Dodano {licznik} operacji na sumę {suma_dodana:.2f} PLN"
        except Exception as e:
            return False, f"Błąd automatu: {e}"

portfel = PortfelGoogle()

# --- PASEK BOCZNY ---
st.sidebar.title("Panel Sterowania")
st.sidebar.info(f"Zalogowano jako Administrator")

st.sidebar.markdown("---")
st.sidebar.write("⚡ **Szybkie akcje**")
if st.sidebar.button("🔄 Dodaj płatności cykliczne"):
    with st.spinner("Układam harmonogram opłat..."):
        sukces, msg = portfel.dodaj_cykliczne()
        if sukces:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
st.sidebar.markdown("---")
if st.sidebar.button("Wyloguj"):
    st.session_state["zalogowany"] = False
    st.rerun()

# --- GŁÓWNA CZĘŚĆ ---
st.title("💰 Twój Wirtualny Portfel")

# === NOWOŚĆ: LOGIKA TRZECH KWOT ===
# 1. Pobieramy wszystkie dane raz
df = portfel.wczytaj_dane()

saldo_realne = 0.0
saldo_oczekujace = 0.0
saldo_prognoza = 0.0

if not df.empty:
    teraz = datetime.datetime.now()
    
    # 2. Dzielimy na przeszłość (i dziś) oraz przyszłość
    # Realne = wszystko co ma datę <= teraz
    maska_realne = df["data"] <= teraz
    saldo_realne = df[maska_realne]["kwota"].sum()
    
    # Oczekujące = wszystko co ma datę > teraz
    maska_przyszle = df["data"] > teraz
    # Sumujemy tylko przyszłe WYDATKI (żeby wiedzieć ile rachunków wisi)
    # (Jeśli masz przyszłe wpływy, one też tu wpadną, co pomniejszy dług - to logiczne)
    saldo_oczekujace = df[maska_przyszle]["kwota"].sum()
    
    # Prognoza = Suma wszystkiego
    saldo_prognoza = df["kwota"].sum()

# === WYŚWIETLANIE 3 KOLUMN ===
k1, k2, k3 = st.columns(3)

with k1:
    st.metric(
        label="💵 Dostępne środki (Dziś)", 
        value=f"{saldo_realne:.2f} PLN",
        help="To pieniądze, które faktycznie powinieneś mieć teraz na koncie (transakcje do dziś włącznie)."
    )

with k2:
    # Kolorujemy na pomarańczowo/czerwono jeśli są wydatki
    st.metric(
        label="⏳ Oczekujące rachunki", 
        value=f"{saldo_oczekujace:.2f} PLN",
        delta="Do zapłaty" if saldo_oczekujace < 0 else "Wpływy",
        delta_color="inverse", # Czerwony jak ujemne
        help="To suma transakcji zaplanowanych na przyszłość (np. z automatu)."
    )

with k3:
    # Prognoza końcowa
    st.metric(
        label="🔮 Prognoza (Po opłatach)", 
        value=f"{saldo_prognoza:.2f} PLN",
        delta="Stan końcowy",
        help="Tyle Ci zostanie, gdy opłacisz wszystkie zaplanowane rachunki."
    )

st.divider()

# --- DODAWANIE ---
with st.expander("➕ Dodaj pojedynczą transakcję", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        typ_transakcji = st.radio("Rodzaj:", ["Wydatek", "Wpływ"], horizontal=True)
    with col2:
        kwota_input = st.number_input("Kwota (PLN):", min_value=0.0, format="%.2f", step=1.0)
    with col3:
        # LOGIKA: Różne kategorie dla Wpływów i Wydatków
        if typ_transakcji == "Wpływ":
            # Lista tylko dla wpływów
            kategorie = ["Pensja", "Premia", "Zwrot podatku", "Sprzedaż", "Inne", "Bilans otwarcia"]
            # Domyślnie zaznaczamy "Pensja" (index 0) lub "Bilans" (ostatni)
            kat_input = st.selectbox("Kategoria:", kategorie, index=0)
        else:
            # Lista tylko dla wydatków
            kategorie = [
                "Jedzenie", "Rachunki", "Transport", "Rozrywka", 
                "Inne", "Paliwo", "Dom", "Zdrowie", 
                "Bankomat (Gotówka)"  # <-- Jasna nazwa dla wypłaty z bankomatu
            ]
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
tab1, tab2, tab3 = st.tabs(["📊 Budżet", "📋 Historia i Filtry", "📈 Wykresy"])

# === TAB 1: BUDŻET ===
with tab1:
    st.subheader("Twój miesięczny budżet")
    df_limity = portfel.wczytaj_limity()
    if df_limity.empty:
        st.warning("⚠️ Brak zakładki 'limity'.")
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
        # Dodajemy informację o statusie
        df_hist = df.copy()
        df_hist["Status"] = df_hist["data"].apply(lambda x: "🕒 Oczekujące" if x > datetime.datetime.now() else "✅ Zaksięgowane")
        
        # --- SEKCJA FILTRÓW (TERAZ Z WYSZUKIWARKĄ) ---
        st.caption("Filtrowanie i przeszukiwanie bazy")
        
        # Rząd 1: Wyszukiwarka tekstowa (To jest nowość!)
        szukana_fraza = st.text_input("🔍 Szukaj w opisach (np. 'Biedronka', 'Prezent'):", placeholder="Wpisz szukane słowo...")

        # Rząd 2: Filtry standardowe
        f_col1, f_col2 = st.columns(2)
        with f_col1:
            dostepne_kategorie = df["kategoria"].unique().tolist()
            wybrane_kategorie = st.multiselect("Filtruj kategorie:", dostepne_kategorie, default=dostepne_kategorie)
        with f_col2:
            min_d = df["data"].min().date()
            max_d = df["data"].max().date()
            d_od, d_do = st.date_input("Zakres dat:", [min_d, max_d])
        
        # --- LOGIKA FILTROWANIA ---
        # 1. Filtrujemy po kategoriach i dacie
        maska = df["kategoria"].isin(wybrane_kategorie) & (df["data"].dt.date >= d_od) & (df["data"].dt.date <= d_do)
        
        # 2. Jeśli ktoś coś wpisał w wyszukiwarkę -> dodajemy ten warunek
        if szukana_fraza:
            # case=False oznacza, że wielkość liter nie ma znaczenia (Auto = auto)
            # na=False oznacza, że ignorujemy puste opisy
            maska = maska & (df["opis"].str.contains(szukana_fraza, case=False, na=False))

        # Aplikujemy filtry
        df_f = df_hist[maska].copy().sort_values(by="data", ascending=False)
        
        # --- PODSUMOWANIE WYNIKÓW ---
        st.divider()
        col_res1, col_res2 = st.columns([1, 3])
        
        suma = df_f["kwota"].sum()
        with col_res1:
            st.markdown("Wynik wyszukiwania:")
            kolor = "green" if suma >= 0 else "red"
            st.markdown(f"<span style='color:{kolor}; font-size: 1.8em; font-weight:bold'>{suma:.2f} PLN</span>", unsafe_allow_html=True)
            st.caption(f"Znaleziono: {len(df_f)} operacji")

        # --- TABELA ---
        def koloruj(val): return f'color: {"red" if val < 0 else "green"}; font-weight: bold;'
        
        cols_to_show = ["data", "Status", "typ", "kategoria", "kwota", "opis"]
        df_disp = df_f[cols_to_show].copy()
        df_disp["data"] = df_disp["data"].dt.strftime("%Y-%m-%d %H:%M")
        
        with col_res2:
            st.dataframe(
                df_disp.style.map(koloruj, subset=['kwota']).format({"kwota": "{:.2f} PLN"}), 
                use_container_width=True, 
                hide_index=True
            )
    else:
        st.info("Brak danych w bazie.")

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


