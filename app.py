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
                failed_downloads = [] # Tracks patents that couldn't be fetched
                
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
                                    failed_downloads.append(pub_number)
                            else:
                                logs.append(f"⚠️ No PDF link found on page: {pub_number}")
                                failed_downloads.append(pub_number)
                        else:
                            logs.append(f"❌ Could not load page: {pub_number}")
                            failed_downloads.append(pub_number)
                            
                    except Exception as e:
                        logs.append(f"⚠️ Error on {pub_number}: {e}")
                        failed_downloads.append(pub_number)
                    
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
    
    # Intact parenthesis fix is applied here:
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        template_df.to_excel(writer, index=False, sheet_name='Patents')
        
    processed_data = output.getvalue()
    
    st.download_button(
        label="⬇️ Download Blank Template",
        data=processed_data,
        file_name="Patent_Template.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        key="template_download"
    )

# ==========================================
# TAB 3: TEXT-TO-TABLE CONVERTER
# ==========================================
with tab3:
    st.header("Messy Text Converter")
    st.write("Did you copy a 'Cited By' table from Google Patents and it turned into a giant block of unformatted text? Paste it below to instantly extract the Publication Numbers into a clean Excel file.")

    raw_text = st.text_area("Paste your messy block text here:", height=200, placeholder="e.g., WO1995029451A11994-04-251995-11-02...")

    if raw_text:
        # Remove header row if accidentally copied
        clean_text = raw_text.replace("Publication numberPriority datePublication dateAssigneeTitle", "")

        # Regex: Looks for (Patent Number) then ignores spaces/asterisks then finds Date 1 and Date 2
        pattern = r'([A-Z]{2}[A-Z0-9]*?)[\s\*]*(\d{4}-\d{2}-\d{2})\s*(\d{4}-\d{2}-\d{2})'
        matches = re.finditer(pattern, clean_text)

        extracted_data = []
        for match in matches:
            pub_num = match.group(1).strip()
            extracted_data.append({
                "Publication number": pub_num,
                "Priority Date": match.group(2),
                "Publication Date": match.group(3)
            })

        if extracted_data:
            df_converted = pd.DataFrame(extracted_data)
            st.success(f"✅ Successfully extracted {len(df_converted)} patents!")
            st.dataframe(df_converted)

            # Generate Downloadable Excel
            convert_output = io.BytesIO()
            with pd.ExcelWriter(convert_output, engine='xlsxwriter') as writer:
                df_converted.to_excel(writer, index=False, sheet_name='Converted Patents')
            converted_data = convert_output.getvalue()

            st.download_button(
                label="⬇️ Download Clean Excel File",
                data=converted_data,
                file_name="Converted_Patents.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="tab3_excel_download"
            )
        else:
            st.error("❌ Could not find any valid patent numbers or dates in that text. Please check the formatting.")
