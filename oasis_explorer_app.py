import streamlit as st
import pandas as pd

# -----------------------------
# Data loading & preparation
# -----------------------------

@st.cache_data
def load_oasis_excel(file) -> pd.DataFrame:
    """
    Load the OASIS+ Excel file and build a single merged dataset.
    This DEBUG version prints the real pool sheet column names.
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

    # Show contract sheet columns for verification
    st.write("📄 Contract sheet columns detected:", contracts.columns.tolist())

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
        raise ValueError("DEBUG ERROR: No pool sheets found in the workbook.")

    pools = pd.concat(pool_frames, ignore_index=True)

    # DEBUG: Print pool sheet column names so we know what merge key actually exists
    st.write("📄 Pool sheet columns detected:", pools.columns.tolist())

    # ---------------------------
    # TEMPORARY: DO NOT MERGE YET
    # ---------------------------
    # Instead, return the pools dataframe so the app doesn't crash.
    # Once we know the correct column names, we will restore merging.
    return pools


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

    # Free-text search attempt on possible fields
    search_cols = [c for c in ["Vendor", "Vendor Name", "UEI", "Contract Number", "Contract #"] if c in df.columns]

    if search_text:
        s = search_text.lower()
        mask = pd.Series(False, index=df.index)
        for col in search_cols:
            mask |= df[col].astype(str).str.lower().str.contains(s, na=False)
        filtered = df[mask]

    # Pool
    if pools_selected and "Pool" in df.columns:
        filtered = filtered[filtered["Pool"].isin(pools_selected)]

    # Domain
    if domains_selected and "Domain" in df.columns:
        filtered = filtered[filtered["Domain"].isin(domains_selected)]

    # NAICS
    if naics_selected and "NAICS" in df.columns:
        filtered = filtered[filtered["NAICS"].isin(naics_selected)]

    # SIN
    if sin_selected and "SIN" in df.columns:
        filtered = filtered[filtered["SIN"].isin(sin_selected)]

    return filtered


# -----------------------------
# Streamlit UI
# -----------------------------

st.set_page_config(
    page_title="OASIS+ Contractor Explorer (DEBUG MODE)",
    layout="wide",
)

st.title("🛠️ OASIS+ Contractor Explorer — DEBUG VERSION")
st.caption("Upload the Excel file. This version prints sheet column names so we can fix the merge logic.")

uploaded_file = st.file_uploader(
    "Upload your **OASIS+ Contractor List Excel file**",
    type=["xlsx"],
    help="Upload the master spreadsheet containing Contract Information + Pools."
)

if not uploaded_file:
    st.info("Upload the Excel file to continue.")
    st.stop()

# Load data with visible error output
try:
    data = load_oasis_excel(uploaded_file)
except Exception as e:
    st.error(f"❌ Error loading workbook:\n\n**{e}**")
    st.stop()

st.success("Workbook loaded successfully in DEBUG mode.")

# -----------------------------
# Sidebar filters
# -----------------------------
st.sidebar.header("Filters (limited in debug mode)")

search_text = st.sidebar.text_input("Search text")

pool_options = sorted(data["Pool"].dropna().unique().tolist()) if "Pool" in data.columns else []
pools_selected = st.sidebar.multiselect("Socioeconomic Pool", pool_options)

domain_options = sorted(data["Domain"].dropna().unique().tolist()) if "Domain" in data.columns else []
domains_selected = st.sidebar.multiselect("Domain", domain_options)

naics_options = sorted(data["NAICS"].dropna().unique().tolist()) if "NAICS" in data.columns else []
naics_selected = st.sidebar.multiselect("NAICS", naics_options)

sin_options = sorted(data["SIN"].dropna().unique().tolist()) if "SIN" in data.columns else []
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
# Display Data
# -----------------------------
st.subheader("DEBUG: Raw / Filtered Data Preview")
st.dataframe(filtered, use_container_width=True)

st.info("Scroll up to see the printed column names. Send them to me so I can finalize merge logic.")
