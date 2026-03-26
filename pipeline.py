from utils.pdf_extractor import extract_text_from_pdf
from utils.claude_structurer import structure_ncs_data
from utils.claude_reporter import generate_clinical_report
from utils.prompts import (
    GPT_STRUCTURER_SYSTEM_PROMPT, 
    GPT_STRUCTURER_USER_PROMPT,
    CLAUDE_REPORTER_SYSTEM_PROMPT,
    CLAUDE_REPORTER_USER_PROMPT
)

USD_TO_INR = 84.0

def run_ncs_pipeline(pdf_file_path):
    """
    Orchestrates the NCS report generation pipeline.
    Yields (step_name, data, total_cost_usd) for progress tracking.
    """
    total_cost_usd = 0.0
    
    # Step 1: PDF Extract
    raw_text = extract_text_from_pdf(pdf_file_path)
    yield "Step 1: PDF Extracted", raw_text, total_cost_usd
    
    # Step 2: GPT Structure
    structured_json, gpt_cost = structure_ncs_data(
        raw_text, 
        GPT_STRUCTURER_SYSTEM_PROMPT, 
        GPT_STRUCTURER_USER_PROMPT
    )
    total_cost_usd += gpt_cost
    yield "Step 2: GPT Structured", structured_json, total_cost_usd
    
    # Step 3: Claude Report
    report_text, claude_cost = generate_clinical_report(
        structured_json, 
        CLAUDE_REPORTER_SYSTEM_PROMPT, 
        CLAUDE_REPORTER_USER_PROMPT
    )
    total_cost_usd += claude_cost
    yield "Step 3: Claude Report Written", report_text, total_cost_usd

def calculate_costs(total_cost_usd):
    cost_inr = total_cost_usd * USD_TO_INR
    return {
        "usd": round(total_cost_usd, 4),
        "inr": round(cost_inr, 2)
    }
