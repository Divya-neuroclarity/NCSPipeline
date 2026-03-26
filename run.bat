@echo off
echo Starting Medical NCS Report Generator...
pip install -r requirements.txt
python -m streamlit run app.py
pause
