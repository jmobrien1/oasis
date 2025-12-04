import streamlit as st
import pandas as pd

# -----------------------------
# Data loading & preparation
# -----------------------------

@st.cache_data
def load_oasis_excel(file) -> pd.DataFrame:
    """
    Load the OASIS+ Excel file and build a single merged dataset:
    Pool sheets + contract info.
    """
    xls = pd.ExcelFile(file)

    # Load Contract Information (header row is row 2 → header=1)
    contracts = pd.read_excel(
        file,
        sheet_name="OASIS+Contract Information",
        header=1
    )

    # Clean column names
    contracts.columns = [c.strip() for c in contracts.columns]

    # Load pool sheets (some names have trailing spaces)
    pool_sheet_names = [
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
        if sheet.strip() in [name.strip() for name in pool_sheet_names]:
            df = pd.read_excel(file, sheet_name=sheet)
            df.columns = [c.strip() for c in df.columns]
            df["Pool"] = sheet.strip()
            pool_frames.append(df)

    if not pool_frames:
        raise ValueError("ERROR: No pool sheets found in the workbook.")

    pools = pd.concat(pool_frames, ignore_index=True)

    # Normalize Contract Number across datasets
    if "Contract Number" not in pools.columns:
        raise KeyError(
            "ERROR: Expected 'Contract Number' column in pool sheets, but it was not found."
        )

    pools["Contract Number"] = pools["Contract Number"].astype(str).str.replace(".0", "", regex=False).str.strip()

    if "Contract Number" in contracts.columns:
        contracts["Contract Number"] = contracts["Contract Number"].astype(str).str.strip()
    else:
        raise KeyError(
            "ERROR: Expected 'Contract Number' in OASIS+Contract Information sheet."
        )

    # Merge pool-level data with contract info
    merged = pools.merge(
        contracts,
        left_on="Contract Number",
        right_on="Contract Number",
        how="left",
        suffixes=("", "_contract")
    )

    # Create a Vendor display column
    vendor_cols = []
    for col in ["Vendor", "Vendor Name", "Vendor_Name", "vendor"]:
        if col in merged.columns:
            vendor_cols.append(col)

    if vendor_cols:
        merged["Vendor Display"] = merged[vendor_cols].bfill(axis=1).iloc[:, 0]
    else:
        merged["Vendor Display"] = ""

    # Ensure useful columns exist (even if missing)
    for col in ["UEI", "Domain", "Pool", "NAICS", "SIN", "ZIP Code", "Vendor City"]:
        if col not in merged.columns:
            merged[col] = pd.NA

    # Clean NAICS + SIN formatting
    if "NAICS" in merged.columns:
        merged["NAICS"] = merged["NAICS"].astype(str).str.replace(".0", "", regex=False).str.strip()

    if "SIN" in merged.columns:
        merged["SIN"] = merged["SIN"].astype(str).str.replace(".0", "", regex=False).str.strip()

    return merged


# -----------------------------
# Filtering logic
# -----------------------------

def apply_filters(df: pd.DataFrame,
                  search_text: str,
                  pools_selected,
                  domains_selected,
                  naics_selected,
                  sin_selected):
    filtered = df.copy()

    # Free-text search across Vendor, UEI, Contract Number
    if search_text:
        s = search_text.lower()
        mask = (
            df["Vendor Display"].astype(str).str.lower().str.contains(s, na=False)
            | df["UEI"].astype(str).str.lower().str.contains(s, na=False)
            | df["Contract Number"].astype(str).str.lower().str.contains(s, na=False)
        )
        filtered = df[mask]

    # Specific filters
    if pools_selected:
        filtered = filtered[filtered["Pool"].isin(pools_selected)]

    if domains_selected:
        filtered = filtered[filtered["Domain"].isin(domains_selected)]

    if naics_selected:
        filtered = filtered[filtered["NAICS"].isin(naics_selected)]

    if sin_selected:
        filtered = filtered[filtered["SIN"].isin(sin_selected)]

    return filtered


# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(
    page_title="OASIS+ Contractor Explorer",
    layout="wide",
)

st.title("OASIS+ Contractor Explorer")
st.caption("Search, filter, and visualize OASIS+ contractor data interactively.")

uploaded_file = st.file_uploader(
    "Upload your **OASIS+ Contractor List Excel file**",
    type=["xlsx"],
    help="Upload the master spreadsheet containing Contract Information + Pools."
)

if not uploaded_file:
    st.info("Upload the Excel file to get started.")
    st.stop()

# Load data with visible error output
try:
    data = load_oasis_excel(uploaded_file)
except Exception as e:
    st.error(f"❌ Error loading workbook:\n\n**{e}**")
    st.stop()


# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.header("Filters")

search_text = st.sidebar.text_input(
    "Search Vendor / UEI / Contract #",
    placeholder="e.g. ESSNOVA, 47QRCA25D..."
)

pool_options = sorted(data["Pool"].dropna().unique().tolist())
pools_selected = st.sidebar.multiselect("Socioeconomic Pool", pool_options)

domain_options = sorted(data["Domain"].dropna().unique().tolist())
domains_selected = st.sidebar.multiselect("Domain", domain_options)

naics_options = sorted(data["NAICS"].dropna().unique().tolist())
naics_selected = st.sidebar.multiselect("NAICS Codes", naics_options)

sin_options = sorted(data["SIN"].dropna().unique().tolist())
sin_selected = st.sidebar.multiselect("SIN Codes", sin_options)

# Apply filters
filtered = apply_filters(
    data,
    search_text=search_text,
    pools_selected=pools_selected,
    domains_selected=domains_selected,
    naics_selected=naics_selected,
    sin_selected=sin_selected,
)


# -----------------------------
# Summary metrics
# -----------------------------
col1, col2, col3, col4 = st.columns(4)

col1.metric("Rows (after filters)", f"{len(filtered):,}")
col2.metric("Unique Vendors", f"{filtered['Vendor Display'].nunique():,}")
col3.metric("Unique NAICS Codes", f"{filtered['NAICS'].nunique():,}")
col4.metric("Pools Represented", f"{filtered['Pool'].nunique():,}")

st.markdown("---")


# -----------------------------
# Data table
# -----------------------------

st.subheader("Filtered Data")

show_cols = [
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

show_cols = [c for c in show_cols if c in filtered.columns]

st.dataframe(
    filtered[show_cols].reset_index(drop=True),
    use_container_width=True,
    hide_index=True
)

st.download_button(
    "Download filtered data as CSV",
    data=filtered.to_csv(index=False),
    file_name="oasis_filtered_export.csv",
    mime="text/csv"
)

st.markdown("---")


# -----------------------------
# Visualizations
# -----------------------------
st.subheader("Visualizations")

tab1, tab2, tab3 = st.tabs([
    "Vendors per Pool",
    "Top NAICS Codes",
    "Domain Distribution"
])

with tab1:
    if not filtered.empty:
        chart = filtered.groupby("Pool")["Vendor Display"].nunique().sort_values(ascending=False)
        st.bar_chart(chart)
    else:
        st.info("No data to display.")

with tab2:
    if not filtered.empty:
        chart = filtered.groupby("NAICS")["Vendor Display"].nunique().sort_values(ascending=False).head(20)
        st.bar_chart(chart)
    else:
        st.info("No data to display.")

with tab3:
    if not filtered.empty:
        chart = filtered.groupby("Domain")["Vendor Display"].nunique().sort_values(ascending=False)
        st.bar_chart(chart)
    else:
        st.info("No data to display.")
