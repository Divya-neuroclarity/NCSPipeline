import streamlit as st
import pypdfium2 as pdfium
from PIL import Image
import base64
import os
import time
from anthropic import Anthropic
from openai import OpenAI
from dotenv import load_dotenv
import io
from fpdf import FPDF
from utils.prompts import NCS_SYSTEM_PROMPT, NCS_USER_PROMPT

# Load environment variables
load_dotenv()

# Initialize API Clients
def get_openai_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def get_anthropic_client():
    return Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Model Mapping to actual IDs (Updated for 2026)
MODEL_MAPPING = {
    "gpt-5.3": "gpt-4o",  # Fallback to gpt-4o for testing
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "claude-sonnet-4.6": "claude-sonnet-4-20250514",  # Verified working
    "claude-opus-4.5": "claude-sonnet-4-20250514"    # Using Sonnet 4 as Opus fallback
}

# --- Core Logic Functions ---

def extract_pages_as_images(pdf_file, scale=3.0, quality=95):
    """
    Renders the first two pages of a PDF into base64-encoded JPEG strings.
    Vision APIs handle these much better for tabular data like NCS reports.
    Scale 3.0 is used to ensure high OCR accuracy for dense medical tables.
    """
    try:
        # Load PDF from bytes
        pdf_bytes = pdf_file.read()
        pdf = pdfium.PdfDocument(pdf_bytes)
        
        base64_images = []
        # NCS reports usually have the relevant table data on pages 1 and 2
        pages_to_extract = min(len(pdf), 2)
        
        for i in range(pages_to_extract):
            page = pdf.get_page(i)
            # Render page to a PIL image
            bitmap = page.render(scale=scale)
            pil_image = bitmap.to_pil()
            
            # Convert to RGB if necessary (e.g. if RGBA)
            if pil_image.mode != 'RGB':
                pil_image = pil_image.convert('RGB')
                
            # Buffer for JPEG
            buffered = io.BytesIO()
            pil_image.save(buffered, format="JPEG", quality=quality)
            img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
            base64_images.append(img_str)
            
        return base64_images
    except Exception as e:
        st.error(f"Error rendering PDF to images: {e}")
        return None

def call_openai(model_id, images, system_message):
    """Calls OpenAI API with vision (image_url) content blocks."""
    client = get_openai_client()
    start_time = time.time()
    
    # Build content list with images first, then text
    content = []
    for img_b64 in images:
        content.append({
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{img_b64}",
                "detail": "high"
            }
        })
    
    # Add vision-specific guidance to ensure model focuses on table accuracy
    vision_guidance = "VERY IMPORTANT: Analyze the provided images carefully. Map each nerve name (row) to its EXACT corresponding value (column) for Latency, Amplitude, and NCV. Do NOT skip rows or misalign columns."
    
    content.append({
        "type": "text",
        "text": f"{vision_guidance}\n\n{NCS_USER_PROMPT}"
    })
    
    response = client.chat.completions.create(
        model=model_id,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": content}
        ]
    )
    end_time = time.time()
    duration = end_time - start_time
    content_text = response.choices[0].message.content
    usage = {
        "input_tokens": response.usage.prompt_tokens,
        "output_tokens": response.usage.completion_tokens,
        "total_tokens": response.usage.total_tokens
    }
    return content_text, duration, usage

def call_claude(model_id, images, system_message):
    """Calls Anthropic API with vision (base64) content blocks."""
    client = get_anthropic_client()
    start_time = time.time()
    
    # Build message content with images, then text
    content = []
    for img_b64 in images:
        content.append({
            "type": "image",
            "source": {
                "type": "base64",
                "media_type": "image/jpeg",
                "data": img_b64
            }
        })
    
    # Add vision-specific guidance to ensure model focuses on table accuracy
    vision_guidance = "VERY IMPORTANT: Analyze the provided images carefully. Map each nerve name (row) to its EXACT corresponding value (column) for Latency, Amplitude, and NCV. Do NOT skip rows or misalign columns."
    
    content.append({
        "type": "text",
        "text": f"{vision_guidance}\n\n{NCS_USER_PROMPT}"
    })
    
    response = client.messages.create(
        model=model_id,
        max_tokens=4096,
        system=system_message,
        messages=[
            {"role": "user", "content": content}
        ]
    )
    end_time = time.time()
    duration = end_time - start_time
    content_text = response.content[0].text
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "total_tokens": response.usage.input_tokens + response.usage.output_tokens
    }
    return content_text, duration, usage

def generate_pdf_report(report_text):
    """Generates a PDF from the report text with NEUROCLARITY DIAGNOSTICS letterhead formatting."""
    try:
        pdf = FPDF()
        pdf.set_margins(20, 20, 20)
        pdf.add_page()
        page_w = pdf.epw  # effective page width

        # ── Letterhead ──────────────────────────────────────────────────────
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(page_w, 10, "NEUROCLARITY DIAGNOSTICS", ln=True, align="C")
        pdf.set_font("Helvetica", "I", 10)
        pdf.cell(page_w, 6, "Innovating Neuro Care. Inspiring Hope", ln=True, align="C")
        pdf.ln(3)
        pdf.set_draw_color(60, 60, 180)
        pdf.set_line_width(0.8)
        pdf.line(pdf.l_margin, pdf.get_y(), pdf.l_margin + page_w, pdf.get_y())
        pdf.ln(4)

        # ── Report Title ─────────────────────────────────────────────────────
        pdf.set_draw_color(0, 0, 0)
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(page_w, 8, "Nerve Conduction Study Report", ln=True, align="C")
        pdf.ln(4)

        # Clean text for latin-1 compatibility
        clean_report = report_text.encode("latin-1", "replace").decode("latin-1")

        # Section headers to detect
        SECTION_HEADERS = {
            "interpretation:",
            "motor nerve conduction studies:",
            "f waves studies:",
            "sensory nerve conduction studies:",
            "conclusions:",
        }
        # Lines that are structural decorators — skip them
        SKIP_LINES = {"---", "neuroclarity diagnostics", "innovating neuro care. inspiring hope",
                      "nerve conduction study report"}
        # Signature line detection
        SIGNATURE_ANCHOR = "neurotechnologist"

        lines = clean_report.splitlines()

        for line in lines:
            stripped = line.strip()
            lower = stripped.lower()

            if not stripped:
                pdf.ln(3)
                continue

            # Skip decorator/header lines already rendered above
            if lower in SKIP_LINES or lower == "---":
                continue

            # Signature footer
            if SIGNATURE_ANCHOR in lower:
                pdf.ln(8)
                pdf.set_line_width(0.4)
                col_w = page_w / 2
                # Draw two signature lines
                y = pdf.get_y()
                pdf.line(pdf.l_margin, y, pdf.l_margin + col_w * 0.55, y)
                pdf.line(pdf.l_margin + col_w * 0.75, y, pdf.l_margin + page_w * 0.97, y)
                pdf.ln(2)
                pdf.set_font("Helvetica", size=9)
                pdf.cell(col_w, 6, "Neurotechnologist", align="L")
                pdf.cell(col_w, 6, "Consultant Neurologist", align="R", ln=True)
                continue

            # Patient info line (Name: / Age: / Date: / UHID:)
            if lower.startswith("name:") or lower.startswith("date:"):
                pdf.set_font("Helvetica", size=10)
                pdf.cell(page_w, 6, stripped, ln=True)
                continue

            # Section headers
            clean_stripped = stripped.replace("**", "").strip()
            if clean_stripped.lower() in SECTION_HEADERS:
                pdf.ln(3)
                pdf.set_font("Helvetica", "B", 11)
                pdf.set_fill_color(235, 238, 255)
                pdf.cell(page_w, 7, clean_stripped, ln=True, fill=True)
                pdf.set_font("Helvetica", size=10)
                pdf.ln(1)
                continue

            # Body text — render with markdown for **bold** support
            pdf.set_font("Helvetica", size=10)
            pdf.multi_cell(w=page_w, h=6, txt=stripped, markdown=True)

        pdf_output = pdf.output()
        return bytes(pdf_output)

    except Exception as e:
        print(f"PDF Gen Error: {e}")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Helvetica", size=11)
        pdf.multi_cell(0, 8, f"Error generating PDF: {str(e)}\n\n{report_text[:1500]}")
        return bytes(pdf.output())

# --- Streamlit UI ---

st.set_page_config(page_title="NCS Report Comparison", page_icon="🧬", layout="wide")

st.title("🧬 Multi-Model NCS Report Generator")
st.markdown("Compare clinical report outputs from different models using the same standard prompt.")

# Sidebar - Settings
with st.sidebar:
    st.header("Settings")
    selected_model = st.selectbox(
        "Select AI Model",
        ["gpt-5.3", "gpt-4o", "gpt-4o-mini", "claude-sonnet-4.6", "claude-opus-4.5"]
    )
    
    st.divider()
    st.caption("API Keys are loaded from .env automatically.")
    if not os.getenv("OPENAI_API_KEY") or not os.getenv("ANTHROPIC_API_KEY"):
        st.error("Missing API Keys in .env!")

# File Uploader
uploaded_file = st.file_uploader("Upload NCS Machine PDF", type="pdf")

if uploaded_file:
    st.info(f"File uploaded: {uploaded_file.name}")
    
    if st.button("Generate Report", type="primary"):
        with st.spinner(f"Rendering PDF to images and calling {selected_model} (Vision)..."):
            # 1. Render pages to images (Pages 1-2 only)
            images = extract_pages_as_images(uploaded_file)
            
            if images:
                try:
                    # 2. Get Persona (System Prompt)
                    system_prompt = NCS_SYSTEM_PROMPT
                    
                    # 3. Call Model with images
                    model_id = MODEL_MAPPING[selected_model]
                    
                    if selected_model.startswith("gpt"):
                        report, duration, usage = call_openai(model_id, images, system_prompt)
                    else:
                        report, duration, usage = call_claude(model_id, images, system_prompt)
                    
                    # 4. Display Results
                    st.success(f"Report generated in {duration:.2f} seconds.")
                    
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.subheader("Generated Report")
                        st.text_area("Report Content", value=report, height=600)
                        
                        st.download_button(
                            label="Download Report as TXT",
                            data=report,
                            file_name=f"NCS_Report_{selected_model}.txt",
                            mime="text/plain"
                        )
                        
                        # Generate and add PDF button
                        pdf_data = generate_pdf_report(report)
                        st.download_button(
                            label="Download Report as PDF",
                            data=pdf_data,
                            file_name=f"NCS_Report_{selected_model}.pdf",
                            mime="application/pdf"
                        )
                        
                    with col2:
                        st.subheader("Execution Stats")
                        st.metric("Response Time", f"{duration:.2f}s")
                        st.write("**Token Usage:**")
                        st.write(f"- Input: {usage['input_tokens']}")
                        st.write(f"- Output: {usage['output_tokens']}")
                        st.write(f"- Total: {usage['total_tokens']}")
                        
                        st.divider()
                        st.caption(f"Actual model ID used: `{model_id}`")
                        
                except Exception as e:
                    st.error(f"Failed to generate report: {e}")
            else:
                st.error("Could not extract any text from the PDF.")

st.sidebar.divider()
st.sidebar.info("This tool is for comparative evaluation of AI models in neurodiagnostic reporting.")
