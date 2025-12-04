import streamlit as st
import pandas as pd

# -----------------------------
# Load and normalize workbook
# -----------------------------

@st.cache_data
def load_oasis_excel(file):
    xls = pd.ExcelFile(file)

    # Load Contract Information (header row is row 2 → header=1)
    contracts = pd.read_excel(
        file,
        sheet_name="OASIS+Contract Information",
        header=1
    )

    contracts.columns = [c.strip() for c in contracts.columns]

    # Normalize Contract Number
    contracts["Contract Number"] = (
        contracts["Contract Number"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # Identify pool sheets
    pool_names = [
        "8a",
        "Small Business",
        "Woman Owned SB",
        "Service Disabled Veteran Owned",
        "Service Disabled Veteran Owned ",
        "HUBZone",
        "Unrestricted",
    ]

    pool_frames = []

    for sheet in xls.sheet_names:
        if sheet.strip() in [p.strip() for p in pool_names]:
            df = pd.read_excel(file, sheet_name=sheet)
            df.columns = [c.strip() for c in df.columns]
            df["Pool"] = sheet.strip()
            pool_frames.append(df)

    if not pool_frames:
        raise ValueError("No pool sheets found in uploaded file.")

    pools = pd.concat(pool_frames, ignore_index=True)

    # Normalize pool Contract #
    pools["Contract #"] = (
        pools["Contract #"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # Normalize NAICS & SIN
    for col in ["NAICS", "SIN"]:
        if col in pools.columns:
            pools[col] = (
                pools[col]
                .astype(str)
                .str.replace(".0", "", regex=False)
                .str.strip()
            )

    # Merge pool-level sheets with contract info sheet
    merged = pools.merge(
        contracts,
        left_on="Contract #",
        right_on="Contract Number",
        how="left",
        suffixes=("", "_contract")
    )

    # Vendor Display
    merged["Vendor Display"] = (
        merged.get("Vendor")
        .fillna(merged.get("Vendor Name"))
        .fillna("")
    )

    # Ensure expected columns exist
    for c in ["Domain", "NAICS", "SIN", "Pool"]:
        if c not in merged.columns:
            merged[c] = pd.NA

    return merged


# -----------------------------
# Filtering logic
# -----------------------------

def apply_filters(df, search, pools, domains, naics, sin):
    filt = df.copy()

    if search:
        s = search.lower()
        cols = ["Vendor Display", "UEI", "Contract Number", "Contract #"]
        mask = False

        for col in cols:
            if col in filt.columns:
                mask = mask | filt[col].astype(str).str.lower().str.contains(s, na=False)

        filt = filt[mask]

    if pools:
        filt = filt[filt["Pool"].isin(pools)]

    if domains:
        filt = filt[filt["Domain"].isin(domains)]

    if naics:
        filt = filt[filt["NAICS"].isin(naics)]

    if sin:
        filt = filt[filt["SIN"].isin(sin)]

    return filt


# -----------------------------
# UI
# -----------------------------

st.set_page_config(page_title="OASIS+ Contractor Explorer", layout="wide")

st.title("OASIS+ Contractor Explorer")
st.caption("Search, filter, and visualize OASIS+ contractor data.")

uploaded_file = st.file_uploader(
    "Upload OASIS+ Excel file",
    type=["xlsx"]
)

if not uploaded_file:
    st.stop()

try:
    data = load_oasis_excel(uploaded_file)
except Exception as e:
    st.error(f"Error loading file:\n\n{e}")
    st.stop()


# -----------------------------
# Sidebar Filters
# -----------------------------

st.sidebar.header("Filters")

search = st.sidebar.text_input("Search Vendor / UEI / Contract")

pool_opts = sorted(data["Pool"].dropna().unique().tolist())
pools = st.sidebar.multiselect("Pool", pool_opts)

domain_opts = sorted(data["Domain"].dropna().unique().tolist())
domains = st.sidebar.multiselect("Domain", domain_opts)

naics_opts = sorted(data["NAICS"].dropna().unique().tolist())
naics = st.sidebar.multiselect("NAICS", naics_opts)

sin_opts = sorted(data["SIN"].dropna().unique().tolist())
sins = st.sidebar.multiselect("SIN", sin_opts)

filtered = apply_filters(data, search, pools, domains, naics, sins)

# -----------------------------
# Summary Metrics
# -----------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Rows", f"{len(filtered):,}")
col2.metric("Unique Vendors", f"{filtered['Vendor Display'].nunique():,}")
col3.metric("Unique NAICS Codes", f"{filtered['NAICS'].nunique():,}")
col4.metric("Pools", f"{filtered['Pool'].nunique():,}")

st.divider()

# -----------------------------
# Data Table
# -----------------------------

st.subheader("Filtered Results")

cols = [
    "Vendor Display",
    "Pool",
    "Domain",
    "SIN",
    "NAICS",
    "Contract Number",
    "UEI",
    "Vendor City",
    "ZIP Code",
]

cols = [c for c in cols if c in filtered.columns]

st.dataframe(filtered[cols], use_container_width=True, hide_index=True)

st.download_button(
    "Download CSV",
    filtered.to_csv(index=False),
    "oasis_filtered_export.csv",
    "text/csv"
)

# -----------------------------
# Visualizations
# -----------------------------

st.subheader("Visualizations")

tab1, tab2, tab3 = st.tabs(["Vendors per Pool", "Top NAICS", "Domains"])

with tab1:
    chart = filtered.groupby("Pool")["Vendor Display"].nunique().sort_values(ascending=False)
    st.bar_chart(chart)

with tab2:
    top = filtered.groupby("NAICS")["Vendor Display"].nunique().sort_values(ascending=False).head(20)
    st.bar_chart(top)

with tab3:
    dom = filtered.groupby("Domain")["Vendor Display"].nunique().sort_values(ascending=False)
    st.bar_chart(dom)
