# Medical NCS Report Generator

This application generates structured medical reports from NCS (Nerve Conduction Study) machine PDFs using GPT and Claude.
## Setup Instructions

1.  **Install Python**: Ensure you have Python 3.8 or higher installed.
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment**:
    Open the `.env` file and ensure your `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` are correctly set.
    *Note: The current `.env` file already contains keys. Please verify they are valid and belong to you.*

## How to Run

You can run the application directly from the project root:

```bash
python -m streamlit run app.py
```

Or, on Windows, you can use the provided `run.bat` file.

## Project Structure

- `app.py`: The Streamlit frontend and main entry point.
- `pipeline.py`: Orchestrates the processing steps (Extract -> Structure -> Report).
- `prompts.py`: Contains the system and user prompts for the AI models.
- `utils/`: Helper modules for PDF extraction and AI API calls.
