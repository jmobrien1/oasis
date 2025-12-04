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

    Expected sheets:
      - "OASIS+Contract Information" (contract info)
      - Pool sheets: "8a", "Small Business", "Woman Owned SB",
                     "Service Disabled Veteran Owned ", "HUBZone", "Unrestricted"
    """
    xls = pd.ExcelFile(file)

    # Contract info sheet: first row is labels, so use header=1
    contracts = pd.read_excel(
        file,
        sheet_name="OASIS+Contract Information",
        header=1
    )

    # Standardize column names a bit
    contracts.columns = [c.strip() for c in contracts.columns]

    # Pool detail sheets
    pool_sheet_names = [
        "8a",
        "Small Business",
        "Woman Owned SB",
        "Service Disabled Veteran Owned ",
        "HUBZone",
        "Unrestricted",
    ]

    pool_frames = []
    for sheet in pool_sheet_names:
        if sheet in xls.sheet_names:
            df = pd.read_excel(file, sheet_name=sheet)
            df.columns = [c.strip() for c in df.columns]
            df["Pool"] = sheet.strip()
            pool_frames.append(df)

    if not pool_frames:
        raise ValueError("No pool sheets found in the workbook.")

    pools = pd.concat(pool_frames, ignore_index=True)

    # Clean up SIN/NAICS formatting
    if "NAICS" in pools.columns:
        pools["NAICS"] = (
            pools["NAICS"]
            .astype(str)
            .str.replace(".0$", "", regex=True)
            .str.strip()
        )

    if "SIN" in pools.columns:
        pools["SIN"] = (
            pools["SIN"]
            .astype(str)
            .str.replace(".0$", "", regex=True)
            .str.strip()
        )

    # Merge pool-level data with contract info
    left_key = "Contract #"
    right_key = "Contract Number"
    if left_key not in pools.columns or right_key not in contracts.columns:
        raise KeyError(
            f"Expected '{left_key}' in pool sheets "
            f"and '{right_key}' in contract info sheet."
        )

    merged = pools.merge(
        contracts,
        left_on=left_key,
        right_on=right_key,
        how="left",
        suffixes=("", "_contract")
    )

    # Vendor display convenience column
    vendor_cols = []
    if "Vendor" in merged.columns:
        vendor_cols.append("Vendor")
    if "Vendor Name" in merged.columns:
        vendor_cols.append("Vendor Name")

    if vendor_cols:
        merged["Vendor Display"] = (
            merged[vendor_cols]
            .bfill(axis=1)
            .iloc[:, 0]
        )
    else:
        merged["Vendor Display"] = ""

    # Ensure some commonly used columns exist (even if empty)
    for col in ["UEI", "Domain", "Pool", "NAICS", "SIN", "ZIP Code", "Vendor City"]:
        if col not in merged.columns:
            merged[col] = pd.NA

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
        mask = pd.Series(False, index=filtered.index)

        if "Vendor Display" in filtered.columns:
            mask |= filtered["Vendor Display"].astype(str).str.lower().str.contains(s, na=False)

        if "UEI" in filtered.columns:
            mask |= filtered["UEI"].astype(str).str.lower().str.contains(s, na=False)

        if "Contract Number" in filtered.columns:
            mask |= filtered["Contract Number"].astype(str).str.lower().str.contains(s, na=False)

        filtered = filtered[mask]

    # Pool filter
    if pools_selected:
        filtered = filtered[filtered["Pool"].isin(pools_selected)]

    # Domain filter
    if domains_selected:
        filtered = filtered[filtered["Domain"].isin(domains_selected)]

    # NAICS filter
    if naics_selected:
        filtered = filtered[filtered["NAICS"].isin(naics_selected)]

    # SIN filter
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
    "Upload your **OASIS+ Contractor List 12032025.xlsx** file",
    type=["xlsx"],
    help="Use the master file with the OASIS+Contract Information and pool sheets."
)

if not uploaded_file:
    st.info("Upload the Excel file to get started.")
    st.stop()

# Load data
try:
    data = load_oasis_excel(uploaded_file)
except Exception as e:
    st.error(f"Error loading workbook: {e}")
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
pools_selected = st.sidebar.multiselect(
    "Socioeconomic Pool",
    options=pool_options,
    default=[]
)

domain_options = sorted(data["Domain"].dropna().unique().tolist())
domains_selected = st.sidebar.multiselect(
    "Domain",
    options=domain_options,
    default=[]
)

naics_options = sorted(data["NAICS"].dropna().unique().tolist())
naics_selected = st.sidebar.multiselect(
    "NAICS",
    options=naics_options,
    default=[]
)

sin_options = sorted(data["SIN"].dropna().unique().tolist())
sin_selected = st.sidebar.multiselect(
    "SIN",
    options=sin_options,
    default=[]
)

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

with col1:
    st.metric(
        "Rows (after filters)",
        f"{len(filtered):,}"
    )

with col2:
    n_vendors = filtered["Vendor Display"].nunique()
    st.metric(
        "Unique Vendors (after filters)",
        f"{n_vendors:,}"
    )

with col3:
    n_naics = filtered["NAICS"].nunique()
    st.metric(
        "Unique NAICS (after filters)",
        f"{n_naics:,}"
    )

with col4:
    n_pools = filtered["Pool"].nunique()
    st.metric(
        "Pools represented (after filters)",
        f"{n_pools:,}"
    )

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

# Only keep columns that actually exist
show_cols = [c for c in show_cols if c in filtered.columns]

st.dataframe(
    filtered[show_cols].reset_index(drop=True),
    use_container_width=True,
    hide_index=True
)

# Download filtered data
csv_data = filtered.to_csv(index=False)
st.download_button(
    "Download filtered data as CSV",
    data=csv_data,
    file_name="oasis_filtered_export.csv",
    mime="text/csv"
)

st.markdown("---")

# -----------------------------
# Visualizations
# -----------------------------

st.subheader("Visualizations")

viz_tab1, viz_tab2, viz_tab3 = st.tabs([
    "Vendors per Pool",
    "Top NAICS by Vendor Count",
    "Domains Distribution"
])

with viz_tab1:
    if not filtered.empty:
        vendors_per_pool = (
            filtered.groupby("Pool")["Vendor Display"]
            .nunique()
            .sort_values(ascending=False)
        )
        st.bar_chart(vendors_per_pool)
    else:
        st.info("No data to display. Adjust your filters.")

with viz_tab2:
    if not filtered.empty:
        top_naics = (
            filtered.groupby("NAICS")["Vendor Display"]
            .nunique()
            .sort_values(ascending=False)
            .head(15)
        )
        st.bar_chart(top_naics)
    else:
        st.info("No data to display. Adjust your filters.")

with viz_tab3:
    if not filtered.empty:
        domains_counts = (
            filtered.groupby("Domain")["Vendor Display"]
            .nunique()
            .sort_values(ascending=False)
        )
        st.bar_chart(domains_counts)
    else:
        st.info("No data to display. Adjust your filters.")
