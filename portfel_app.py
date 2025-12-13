import streamlit as st
import pandas as pd
import datetime
from streamlit_gsheets import GSheetsConnection

# --- KONFIGURACJA STRONY ---
st.set_page_config(page_title="Mój Portfel Pro", page_icon="💰", layout="wide")

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
                    data_transakcji = teraz 

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

# --- WCZYTANIE DANYCH DO OBLICZEŃ ---
df = portfel.wczytaj_dane()

# ==========================================
# --- PASEK BOCZNY (SIDEBAR) ---
# ==========================================
st.sidebar.title("Panel Sterowania")
st.sidebar.info(f"Witaj! Dzisiaj jest: {datetime.date.today()}")

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

# --- NOWOŚĆ 1: CEL MARZEŃ (OSZCZĘDNOŚCI) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Cel: Oszczędzanie")
cel_kwota = st.sidebar.number_input("Twój Cel (PLN):", value=10000.0, step=500.0)

uzbierane = 0.0
if not df.empty:
    # Szukamy wydatków w kategorii 'Oszczędności 💰'
    maska_oszczednosci = df["kategoria"] == "Oszczędności 💰"
    uzbierane = df[maska_oszczednosci]["kwota"].abs().sum()

procent = min(uzbierane / cel_kwota, 1.0) if cel_kwota > 0 else 0
st.sidebar.progress(procent)
st.sidebar.write(f"Uzbierano: **{uzbierane:.2f} PLN**")
st.sidebar.caption(f"({procent*100:.1f}% celu)")
if uzbierane >= cel_kwota:
    st.sidebar.success("🎉 CEL OSIĄGNIĘTY!")

# --- NOWOŚĆ 2: KALKULATOR ŻYCIA ---
st.sidebar.markdown("---")
st.sidebar.subheader("⏳ Kalkulator Życia")
st.sidebar.caption("Przelicz cenę na godziny swojej pracy")
twoja_stawka = st.sidebar.number_input("Stawka netto/h:", value=30.0, step=1.0)
koszt_rzeczy = st.sidebar.number_input("Cena zakupu:", value=0.0, step=10.0)

if koszt_rzeczy > 0:
    godziny = koszt_rzeczy / twoja_stawka
    st.sidebar.write(f"Kosztuje to: **{godziny:.1f} godz.** pracy")
    if godziny > 8:
        dniowki = godziny / 8
        st.sidebar.error(f"To ponad {dniowki:.1f} dniówki!")
    else:
        st.sidebar.success("Kupuj, to tylko chwila pracy!")

st.sidebar.markdown("---")
if st.sidebar.button("Wyloguj"):
    st.session_state["zalogowany"] = False
    st.rerun()

# ==========================================
# --- GŁÓWNA CZĘŚĆ (MAIN) ---
# ==========================================
st.title("💰 Twój Asystent Finansowy")

# LOGIKA TRZECH KWOT
saldo_realne = 0.0
saldo_oczekujace = 0.0
saldo_prognoza = 0.0

if not df.empty:
    teraz = datetime.datetime.now()
    # Realne = data <= teraz
    maska_realne = df["data"] <= teraz
    saldo_realne = df[maska_realne]["kwota"].sum()
    
    # Oczekujące = data > teraz
    maska_przyszle = df["data"] > teraz
    saldo_oczekujace = df[maska_przyszle]["kwota"].sum()
    
    # Prognoza = Suma wszystkiego
    saldo_prognoza = df["kwota"].sum()

# --- NOWOŚĆ 3: FINANSOWE SUMIENIE ---
# Komentarz zależny od prognozy
if saldo_prognoza > 5000:
    st.success("🚀 Jest świetnie! Saldo wygląda imponująco. Może mała inwestycja?")
elif saldo_prognoza > 2000:
    st.info("👌 Sytuacja stabilna. Masz bezpieczny zapas gotówki.")
elif saldo_prognoza > 500:
    st.warning("⚠️ Uważaj. Zbliżasz się do granicy bezpieczeństwa.")
elif saldo_prognoza > 0:
    st.error("🚨 Alarm! Balansujesz na krawędzi. Żadnych zbędnych wydatków!")
else:
    st.error("💀 Jesteś pod kreską. Włącz tryb oszczędzania TOTALNEGO.")

# METRYKI
k1, k2, k3 = st.columns(3)
with k1:
    st.metric(label="💵 Dostępne środki (Dziś)", value=f"{saldo_realne:.2f} PLN")
with k2:
    st.metric(label="⏳ Oczekujące rachunki", value=f"{saldo_oczekujace:.2f} PLN", 
              delta="Wpływy" if saldo_oczekujace > 0 else "Opłaty", delta_color="inverse")
with k3:
    st.metric(label="🔮 Prognoza (Po opłatach)", value=f"{saldo_prognoza:.2f} PLN", delta="Stan końcowy")

st.divider()

# --- DODAWANIE ---
with st.expander("➕ Dodaj transakcję", expanded=False):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        typ_transakcji = st.radio("Rodzaj:", ["Wydatek", "Wpływ"], horizontal=True)
    with col2:
        kwota_input = st.number_input("Kwota (PLN):", min_value=0.0, format="%.2f", step=1.0)
    with col3:
        if typ_transakcji == "Wpływ":
            kategorie = ["Pensja", "Premia", "Zwrot podatku", "Sprzedaż", "Inne", "Bilans otwarcia"]
            kat_input = st.selectbox("Kategoria:", kategorie, index=0)
        else:
            # Tu dodaliśmy "Oszczędności" do listy
            kategorie = [
                "Jedzenie", "Rachunki", "Transport", "Rozrywka", 
                "Inne", "Paliwo", "Dom", "Zdrowie", 
                "Bankomat (Gotówka)", "Oszczędności 💰"
            ]
            kat_input = st.selectbox("Kategoria:", kategorie)
    with col4:
        opis_input = st.text_input("Opis:")
        if st.button("Zapisz", use_container_width=True):
            with st.spinner("Zapisuję..."):
                sukces, komunikat = portfel.dodaj_transakcje(typ_transakcji, kwota_input, kat_input, opis_input)
                if sukces:
                    st.success(f"{komunikat}")
                    st.rerun()
                else:
                    st.error(komunikat)

# --- ZAKŁADKI ---
tab1, tab2, tab3 = st.tabs(["📊 Budżet", "📋 Historia i Szukaj", "📈 Wykresy"])

# === TAB 1: BUDŻET ===
with tab1:
    st.subheader("Realizacja budżetu")
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

# === TAB 2: HISTORIA I WYSZUKIWARKA ===
with tab2:
    if not df.empty:
        df_hist = df.copy()
        df_hist["Status"] = df_hist["data"].apply(lambda x: "🕒 Oczekujące" if x > datetime.datetime.now() else "✅ Zaksięgowane")
        
        st.caption("Filtrowanie i przeszukiwanie bazy")
        szukana_fraza = st.text_input("🔍 Szukaj w opisach (np. 'Biedronka', 'Prezent'):", placeholder="Wpisz szukane słowo...")

        f_col1, f_col2 = st.columns(2)
        with f_col1:
            dostepne_kategorie = df["kategoria"].unique().tolist()
            wybrane_kategorie = st.multiselect("Filtruj kategorie:", dostepne_kategorie, default=dostepne_kategorie)
        with f_col2:
            min_d = df["data"].min().date()
            max_d = df["data"].max().date()
            d_od, d_do = st.date_input("Zakres dat:", [min_d, max_d])
        
        maska = df["kategoria"].isin(wybrane_kategorie) & (df["data"].dt.date >= d_od) & (df["data"].dt.date <= d_do)
        if szukana_fraza:
            maska = maska & (df["opis"].str.contains(szukana_fraza, case=False, na=False))

        df_f = df_hist[maska].copy().sort_values(by="data", ascending=False)
        
        st.divider()
        col_res1, col_res2 = st.columns([1, 3])
        suma = df_f["kwota"].sum()
        with col_res1:
            st.markdown("Wynik wyszukiwania:")
            kolor = "green" if suma >= 0 else "red"
            st.markdown(f"<span style='color:{kolor}; font-size: 1.8em; font-weight:bold'>{suma:.2f} PLN</span>", unsafe_allow_html=True)
            st.caption(f"Znaleziono: {len(df_f)} operacji")

        def koloruj(val): return f'color: {"red" if val < 0 else "green"}; font-weight: bold;'
        
        cols_to_show = ["data", "Status", "typ", "kategoria", "kwota", "opis"]
        df_disp = df_f[cols_to_show].copy()
        df_disp["data"] = df_disp["data"].dt.strftime("%Y-%m-%d %H:%M")
        
        with col_res2:
            st.dataframe(df_disp.style.map(koloruj, subset=['kwota']).format({"kwota": "{:.2f} PLN"}), use_container_width=True, hide_index=True)
    else:
        st.info("Brak danych w bazie.")

# === TAB 3: WYKRESY ===
with tab3:
    if not df.empty:
        wyd = df[df["kwota"] < 0].copy()
        if not wyd.empty:
            wyd["kwota"] = wyd["kwota"].abs()
            c1, c2 = st.columns(2)
            with c1: 
                st.subheader("Struktura wydatków")
                st.bar_chart(wyd.groupby("kategoria")["kwota"].sum())
            with c2:
                st.subheader("Top 5 Wydatków")
                for i, r in wyd.sort_values("kwota", ascending=False).head(5).iterrows():
                    st.write(f"💸 **{r['kwota']:.2f} zł** - {r['opis']} ({r['kategoria']})")
        else: st.write("Brak wydatków.")
