import streamlit as st
import pandas as pd


# -----------------------------
# Data loading & preparation
# -----------------------------

def load_oasis_excel(file) -> pd.DataFrame:
    """Load contract info + pool sheets and return a merged dataframe."""

    xls = pd.ExcelFile(file)

    # --- Contract Information sheet ---
    contracts = pd.read_excel(
        file,
        sheet_name="OASIS+Contract Information",
        header=1,  # row 2 in Excel is header
    )
    contracts.columns = [c.strip() for c in contracts.columns]

    if "Contract Number" not in contracts.columns:
        raise KeyError(
            f"'Contract Number' not found in contract sheet. Columns: {contracts.columns.tolist()}"
        )

    # --- Pool sheets ---
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
        raise ValueError("No pool sheets found in workbook.")

    pools = pd.concat(pool_frames, ignore_index=True)

    if "Contract #" not in pools.columns:
        raise KeyError(
            f"'Contract #' not found in pool sheets. Columns: {pools.columns.tolist()}"
        )

    # --- Normalize keys & common fields ---

    # Contract number fields
    pools["Contract #"] = (
        pools["Contract #"].astype(str).str.replace(".0", "", regex=False).str.strip()
    )
    contracts["Contract Number"] = (
        contracts["Contract Number"]
        .astype(str)
        .str.replace(".0", "", regex=False)
        .str.strip()
    )

    # NAICS / SIN as strings
    for col in ["NAICS", "SIN"]:
        if col in pools.columns:
            pools[col] = (
                pools[col].astype(str).str.replace(".0", "", regex=False).str.strip()
            )

    # Merge
    merged = pools.merge(
        contracts,
        left_on="Contract #",
        right_on="Contract Number",
        how="left",
        suffixes=("", "_contract"),
    )

    # Vendor Display
    vendor_cols = [c for c in ["Vendor", "Vendor Name"] if c in merged.columns]
    if vendor_cols:
        merged["Vendor Display"] = (
            merged[vendor_cols].bfill(axis=1).iloc[:, 0].fillna("")
        )
    else:
        merged["Vendor Display"] = ""

    # Ensure some columns exist & are strings for filtering
    for col in ["Pool", "Domain", "NAICS", "SIN", "UEI", "Vendor City", "ZIP Code"]:
        if col not in merged.columns:
            merged[col] = pd.NA
        merged[col] = merged[col].astype(str)

    return merged


def apply_filters(df: pd.DataFrame,
                  search_text: str,
                  pools_selected,
                  domains_selected,
                  naics_selected,
                  sin_selected) -> pd.DataFrame:
    """Apply text and facet filters to the merged dataframe."""
    filtered = df.copy()

    # Free-text search
    if search_text:
        s = search_text.lower()
        mask = False
        for col in ["Vendor Display", "UEI", "Contract Number", "Contract #"]:
            if col in filtered.columns:
                mask = mask | filtered[col].astype(str).str.lower().str.contains(s, na=False)
        filtered = filtered[mask]

    # Pool
    if pools_selected:
        filtered = filtered[filtered["Pool"].isin(pools_selected)]

    # Domain
    if domains_selected:
        filtered = filtered[filtered["Domain"].isin(domains_selected)]

    # NAICS
    if naics_selected:
        filtered = filtered[filtered["NAICS"].isin(naics_selected)]

    # SIN
    if sin_selected:
        filtered = filtered[filtered["SIN"].isin(sin_selected)]

    return filtered


# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(page_title="OASIS+ Contractor Explorer", layout="wide")

st.title("OASIS+ Contractor Explorer")
st.caption("Search, filter, and visualize OASIS+ contractor data.")

uploaded_file = st.file_uploader(
    "Upload your **OASIS+ Contractor List 12032025.xlsx** file",
    type=["xlsx"],
)

if uploaded_file is None:
    st.info("Upload the Excel file to get started.")
    st.stop()

# Load data with visible errors
try:
    data = load_oasis_excel(uploaded_file)
except Exception as e:
    st.error("❌ Error loading workbook:")
    st.exception(e)
    st.stop()

st.success("✅ Workbook loaded and merged successfully.")
st.write("Merged columns:", list(data.columns))

# -----------------------------
# Sidebar filters
# -----------------------------

try:
    st.sidebar.header("Filters")

    search_text = st.sidebar.text_input(
        "Search Vendor / UEI / Contract",
        placeholder="e.g. AEVEX, 47QRCA25D...",
    )

    pool_options = sorted(set(data["Pool"].dropna().astype(str).tolist()))
    pools_selected = st.sidebar.multiselect("Pool", pool_options)

    domain_options = sorted(set(data["Domain"].dropna().astype(str).tolist()))
    domains_selected = st.sidebar.multiselect("Domain", domain_options)

    naics_options = sorted(set(data["NAICS"].dropna().astype(str).tolist()))
    naics_selected = st.sidebar.multiselect("NAICS", naics_options)

    sin_options = sorted(set(data["SIN"].dropna().astype(str).tolist()))
    sin_selected = st.sidebar.multiselect("SIN", sin_options)

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

    col1.metric("Rows", f"{len(filtered):,}")
    col2.metric("Unique Vendors", f"{filtered['Vendor Display'].nunique():,}")
    col3.metric("Unique NAICS Codes", f"{filtered['NAICS'].nunique():,}")
    col4.metric("Pools", f"{filtered['Pool'].nunique():,}")

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
        hide_index=True,
    )

    st.download_button(
        "Download filtered data as CSV",
        data=filtered.to_csv(index=False),
        file_name="oasis_filtered_export.csv",
        mime="text/csv",
    )

    st.markdown("---")

    # -----------------------------
    # Visualizations
    # -----------------------------
    st.subheader("Visualizations")

    tab1, tab2, tab3 = st.tabs(["Vendors per Pool", "Top NAICS", "Domains"])

    with tab1:
        if not filtered.empty:
            by_pool = (
                filtered.groupby("Pool")["Vendor Display"]
                .nunique()
                .sort_values(ascending=False)
            )
            st.bar_chart(by_pool)
        else:
            st.info("No data for current filters.")

    with tab2:
        if not filtered.empty:
            by_naics = (
                filtered.groupby("NAICS")["Vendor Display"]
                .nunique()
                .sort_values(ascending=False)
                .head(20)
            )
            st.bar_chart(by_naics)
        else:
            st.info("No data for current filters.")

    with tab3:
        if not filtered.empty:
            by_domain = (
                filtered.groupby("Domain")["Vendor Display"]
                .nunique()
                .sort_values(ascending=False)
            )
            st.bar_chart(by_domain)
        else:
            st.info("No data for current filters.")

except Exception as e:
    st.error("❌ Error while building UI:")
    st.exception(e)
