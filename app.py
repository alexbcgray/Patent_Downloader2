import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
import time
import zipfile
import io
import re

# --- App UI Configuration ---
st.set_page_config(page_title="Patent Downloader", page_icon="📄", layout="centered")

st.title("Automated Patent Downloader 📄")

# --- Create Tabs ---
tab1, tab2, tab3 = st.tabs(["🚀 Downloader", "📖 Instructions", "✂️ Text-to-Table Converter"])

# ==========================================
# TAB 1: THE DOWNLOADER TOOL
# ==========================================
with tab1:
    st.write("Drag and drop your Excel file containing a 'Publication number' column. The app will fetch the PDFs and package them into a single Zip file.")

    HEADERS = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    uploaded_file = st.file_uploader("Upload your Excel File (.xlsx)", type=["xlsx"], key="main_uploader")

    if uploaded_file is not None:
        try:
            df = pd.read_excel(uploaded_file)
            if 'Publication number' not in df.columns:
                st.error("⚠️ Error: The Excel file must contain a column named exactly 'Publication number'.")
                st.stop()
                
            patents_to_fetch = df['Publication number'].dropna().astype(str).tolist()
            st.success(f"Found {len(patents_to_fetch)} patents to process.")
            
        except Exception as e:
            st.error(f"Could not read the Excel file: {e}")
            st.stop()

        if st.button("Fetch Patents", type="primary"):
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_window = st.empty()
            zip_buffer = io.BytesIO()
            
            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                logs = []
                successful_downloads = 0
                failed_downloads = [] # <-- NEW: Our bucket for missing patents
                
                for i, pub_number in enumerate(patents_to_fetch):
                    pub_number = pub_number.strip()
                    status_text.markdown(f"**Currently processing:** `{pub_number}` ({i+1}/{len(patents_to_fetch)})")
                    patent_page_url = f"https://patents.google.com/patent/{pub_number}/en"
                    
                    try:
                        page_response = requests.get(patent_page_url, headers=HEADERS)
                        if page_response.status_code == 200:
                            soup = BeautifulSoup(page_response.text, 'html.parser')
                            meta_tag = soup.find('meta', attrs={'name': 'citation_pdf_url'})
                            
                            if meta_tag and meta_tag.get('content'):
                                real_pdf_url = meta_tag['content']
                                pdf_response = requests.get(real_pdf_url, headers=HEADERS)
                                
                                if pdf_response.status_code == 200:
                                    zip_file.writestr(f"{pub_number}.pdf", pdf_response.content)
                                    logs.append(f"✅ Success: {pub_number}")
                                    successful_downloads += 1
                                else:
                                    logs.append(f"❌ Failed to download PDF data: {pub_number}")
                                    failed_downloads.append(pub_number) # Added to fail list
                            else:
                                logs.append(f"⚠️ No PDF link found on page: {pub_number}")
                                failed_downloads.append(pub_number) # Added to fail list
                        else:
                            logs.append(f"❌ Could not load page: {pub_number}")
                            failed_downloads.append(pub_number) # Added to fail list
                            
                    except Exception as e:
                        logs.append(f"⚠️ Error on {pub_number}: {e}")
                        failed_downloads.append(pub_number) # Added to fail list
                    
                    progress_bar.progress((i + 1) / len(patents_to_fetch))
                    log_window.text("\n".join(logs[-5:]))
                    time.sleep(1.5) 

            # --- Processing Complete ---
            progress_bar.empty()
            
            if successful_downloads > 0:
                status_text.success(f"🎉 Complete! Successfully bundled {successful_downloads} out of {len(patents_to_fetch)} patents.")
                st.download_button(
                    label="⬇️ Download Successfully Fetched Patents (ZIP)",
                    data=zip_buffer.getvalue(),
                    file_name="Downloaded_Patents.zip",
                    mime="application/zip",
                    key="zip_download"
                )
            else:
                status_text.error("❌ No patents could be downloaded. Check your file or internet connection.")

            # --- Display Failed Patents ---
            if failed_downloads:
                st.warning(f"⚠️ **{len(failed_downloads)} patents could not be downloaded.** Google Patents likely does not have the PDF files for these. You will need to source them manually:")
                
                # Creates a nice, copy-pasteable text box with the failed numbers separated by commas
                failed_text = ", ".join(failed_downloads)
                st.text_area("Failed Patents (Copy & Paste):", failed_text, height=100)

# ==========================================
# TAB 2: INSTRUCTIONS & TEMPLATE
# ==========================================
with tab2:
    st.header("How to format your Excel file")
    st.write("For this tool to work, your Excel file must be formatted correctly. Don't worry, it's very simple!")
    st.markdown("""
    ### 📝 Checklist:
    1. Your file must be a standard Excel workbook (`.xlsx`).
    2. The very first row must be your headers.
    3. You **must** have a column titled exactly **`Publication number`** (case-sensitive).
    """)

    template_df = pd.DataFrame(columns=["Publication number", "Notes (Optional)"])
    output = io.BytesIO()
    with pd.ExcelWriter(output
