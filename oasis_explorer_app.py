import streamlit as st
import pandas as pd

# -----------------------------
# Load and normalize workbook
# -----------------------------

@st.cache_data
def load_oasis_excel(file):
    xls = pd.ExcelFile(file)

    # --- Contract Information sheet ---
    contracts = pd.read_excel(
        file,
        sheet_name="OASIS+Contract Information",
        header=1
    )
    contracts.columns = [c.strip() for c in contracts.columns]

    if "Contract Number" not in contracts.columns:
        raise KeyError("Expected 'Contract Number' in OASIS+Contract Information sheet.")

    # Normalize Contract Number
    contracts["Contract Number"] = (
        contracts["Contract Number"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # --- Pool sheets ---
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

    if "Contract #" not in pools.columns:
        raise KeyError("Expected 'Contract #' column in pool sheets.")

    # Normalize Contract # in pools
    pools["Contract #"] = (
        pools["Contract #"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # Normalize NAICS & SIN in pools if present
    for col in ["NAICS", "SIN"]:
        if col in pools.columns:
            pools[col] = (
                pools[col]
                .astype(str)
                .str.replace(".0", "", regex=False)
                .str.strip()
            )

    # Merge pools with contract info
    merged = pools.merge(
        contracts,
        left_on="Contract #",
        right_on="Contract Number",
        how="left",
        suffixes=("", "_contract")
    )

    # Build Vendor Display
    vendor_cols = [c for c in ["Vendor", "Vendor Name"] if c in merged.columns]
    if vendor_cols:
        merged["Vendor Display"] = (
            merged[vendor_cols]
            .bfill(axis=1)
            .iloc[:, 0]
            .fillna("")
        )
    else:
        merged["Vendor Display"] = ""

    # Ensure expected columns exist
    for c in ["Domain", "NAICS", "SIN", "Pool", "UEI", "Vendor City", "ZIP Code"]:
        if c not in merged.columns:
            merged[c] = pd.NA

    return merged


# -----------------------------
# Filtering logic
# -----------------------------

def apply_filters(df, search, pools, domains, naics, sins):
    filtered = df.copy()

    # Text search across common fields
    if search:
        s = search.lower()
        mask = False
        for col in ["Vendor Display", "UEI", "Contract Number", "Contract #"]:
            if col in filtered.columns:
                mask = mask | filtered[col].astype(str).str.lower().str.contains(s, na=False)
        filtered = filtered[mask]

    # Pool filter
    if pools:
        filtered = filtered[filtered["Pool"].astype(str).isin(pools)]

    # Domain filter
    if domains:
        filtered = filtered[filtered["Domain"].astype(str).isin(domains)]

    # NAICS filter
    if naics:
        filtered = filtered[filtered["NAICS"].astype(str).isin(naics)]

    # SIN filter
    if sins:
        filtered = filtered[filtered["SIN"].astype(str).isin(sins)]

    return filtered


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
    st.info("Upload your OASIS+ Contractor List Excel file to begin.")
    st.stop()

# Load data
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

# Pool options
if "Pool" in data.columns:
    pool_opts = sorted(set(map(str, data["Pool"].dropna().tolist())))
else:
    pool_opts = []
pools = st.sidebar.multiselect("Pool", pool_opts)

# Domain options
if "Domain" in data.columns:
    domain_opts = sorted(set(map(str, data["Domain"].dropna().tolist())))
else:
    domain_opts = []
domains = st.sidebar.multiselect("Domain", domain_opts)

# NAICS options
if "NAICS" in data.columns:
    naics_opts = sorted(set(map(str, data["NAICS"].dropna().tolist())))
else:
    naics_opts = []
naics = st.sidebar.multiselect("NAICS", naics_opts)

# SIN options
if "SIN" in data.columns:
    sin_opts = sorted(set(map(str, data["SIN"].dropna().tolist())))
else:
    sin_opts = []
sins = st.sidebar.multiselect("SIN", sin_opts)

# Apply filters
filtered = apply_filters(data, search, pools, domains, naics, sins)


# -----------------------------
# Summary Metrics
# -----------------------------

col1, col2, col3, col4 = st.columns(4)

col1.metric("Rows", f"{len(filtered):,}")
col2.metric("Unique Vendors", f"{filtered['Vendor Display'].nunique():,}")
col3.metric("Unique NAICS Codes", f"{filtered['NAICS'].astype(str).nunique():,}")
col4.metric("Pools", f"{filtered['Pool'].astype(str).nunique():,}")

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
    if not filtered.empty:
        chart = (
            filtered.groupby("Pool")["Vendor Display"]
            .nunique()
            .sort_values(ascending=False)
        )
        st.bar_chart(chart)
    else:
        st.info("No data to display for current filters.")

with tab2:
    if not filtered.empty:
        chart = (
            filtered.groupby("NAICS")["Vendor Display"]
            .nunique()
            .sort_values(ascending=False)
            .head(20)
        )
        st.bar_chart(chart)
    else:
        st.info("No data to display for current filters.")

with tab3:
    if not filtered.empty:
        chart = (
            filtered.groupby("Domain")["Vendor Display"]
            .nunique()
            .sort_values(ascending=False)
        )
        st.bar_chart(chart)
    else:
        st.info("No data to display for current filters.")
