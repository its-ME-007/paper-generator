import json
from fpdf import FPDF

# Path to the JSON file
json_file_path = "mcq_responses.json"  # Replace with the actual file path

# Read JSON data from the file
with open(json_file_path, "r") as file:
    data = json.load(file)

# Create a PDF instance
pdf = FPDF()
pdf.set_auto_page_break(auto=True, margin=15)
pdf.add_page()
pdf.set_font("Arial", size=12)

# Add a title
pdf.set_font("Arial", style="B", size=16)
pdf.cell(200, 10, "UPSC Practice Question Paper", ln=True, align='C')
pdf.ln(10)

# Add questions
for idx, item in enumerate(data['questions'], start=1):
    pdf.set_font("Arial", size=12)
    pdf.multi_cell(0, 10, f"{idx}. {item['question']}")
    for opt_key, opt_val in item['options'].items():
        pdf.cell(0, 10, f"   {opt_key}. {opt_val}", ln=True)
    pdf.ln(5)

# Save PDF
pdf_output_path = "question_paper/question_paper.pdf"
pdf.output(pdf_output_path)
print(f"Question paper saved as {pdf_output_path}")
