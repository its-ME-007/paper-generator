"""
Braille PDF rendering pipeline.
Converts structured question data to Braille PDFs.
"""

from fpdf import FPDF
import os
from datetime import datetime
from renderers.braille_text import text_to_braille, get_braille_status

def generate_braille_pdf(questions, paper_id, clean_text_fn):
    """
    Generate Braille version of question paper.
    
    This is the main pipeline entry point for Braille PDFs.
    
    Args:
        questions: List of question dicts
        paper_id: Unique paper identifier
        clean_text_fn: Function to clean Unicode characters
        
    Returns:
        str: Path to generated PDF file
    """
    # Check Braille system status
    status = get_braille_status()
    use_braille = status['liblouis_available']
    
    # Initialize PDF
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Try to load Unicode font for Braille symbols
    font_name = _setup_font(pdf)
    use_unicode = (font_name == 'DejaVu')
    
    # Render header
    _render_header(pdf, paper_id, font_name, use_braille, use_unicode, clean_text_fn)
    
    # Render questions
    _render_questions(pdf, questions, font_name, use_braille, use_unicode, clean_text_fn)
    
    # Save PDF
    filepath = _save_pdf(pdf, paper_id)
    
    return filepath

def _setup_font(pdf):
    """
    Set up PDF font with Unicode support if available.
    
    Args:
        pdf: FPDF instance
        
    Returns:
        str: Font name ('DejaVu' or 'Courier')
    """
    try:
        if os.path.exists('DejaVuSans.ttf'):
            pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            pdf.set_font('DejaVu', size=14)
            return 'DejaVu'
        else:
            pdf.set_font("Courier", size=14)
            return 'Courier'
    except:
        pdf.set_font("Courier", size=14)
        return 'Courier'

def _render_header(pdf, paper_id, font_name, use_braille, use_unicode, clean_text_fn):
    """Render PDF header with metadata."""
    pdf.set_font(font_name, size=16)
    header_text = "UPSC Practice Question Paper - Braille Version"
    
    if use_braille and use_unicode:
        try:
            header_braille = text_to_braille(header_text)
            pdf.cell(0, 10, header_braille, ln=True, align='C')
        except:
            pdf.cell(0, 10, header_text, ln=True, align='C')
    else:
        pdf.cell(0, 10, header_text, ln=True, align='C')
    
    pdf.set_font(font_name, size=10)
    pdf.ln(2)
    
    # Paper ID
    info_text = f"Paper ID: {paper_id}"
    _render_text_line(pdf, info_text, font_name, use_braille, use_unicode, align='C')
    
    # Date
    date_text = f"Generated: {datetime.now().strftime('%d-%m-%Y')}"
    _render_text_line(pdf, date_text, font_name, use_braille, use_unicode, align='C')
    
    # Status note
    if not use_braille or not use_unicode:
        pdf.set_font(font_name, size=8)
        note = "(Note: Braille conversion unavailable - showing regular text)"
        pdf.cell(0, 5, note, ln=True, align='C')
    
    pdf.ln(10)

def _render_text_line(pdf, text, font_name, use_braille, use_unicode, align='L'):
    """Render a single line of text with optional Braille conversion."""
    if use_braille and use_unicode:
        try:
            braille_text = text_to_braille(text)
            pdf.cell(0, 5, braille_text, ln=True, align=align)
        except:
            pdf.cell(0, 5, text, ln=True, align=align)
    else:
        pdf.cell(0, 5, text, ln=True, align=align)

def _render_questions(pdf, questions, font_name, use_braille, use_unicode, clean_text_fn):
    """Render all questions in Braille format."""
    pdf.set_font(font_name, size=12)
    
    for idx, question in enumerate(questions, start=1):
        # Render passage if present
        if question.get('passage'):
            _render_passage(pdf, question['passage'], font_name, use_braille, use_unicode, clean_text_fn)
        
        # Render question text
        _render_question_text(pdf, question, idx, font_name, use_braille, use_unicode, clean_text_fn)
        
        # Render statements if present
        if question.get('statements'):
            _render_statements(pdf, question['statements'], font_name, use_braille, use_unicode, clean_text_fn)
        
        # Render options
        _render_options(pdf, question.get('options', {}), font_name, use_braille, use_unicode, clean_text_fn)
        
        pdf.ln(6)

def _render_passage(pdf, passage, font_name, use_braille, use_unicode, clean_text_fn):
    """Render a passage with gray background."""
    pdf.set_font(font_name, size=10)
    pdf.set_fill_color(245, 245, 245)
    
    passage_clean = clean_text_fn(passage)
    passage_text = f"Passage: {passage_clean}"
    
    if use_braille and use_unicode:
        try:
            passage_braille = text_to_braille(passage_text)
            pdf.multi_cell(0, 6, passage_braille, fill=True)
        except:
            pdf.multi_cell(0, 6, passage_text, fill=True)
    else:
        pdf.multi_cell(0, 6, passage_text, fill=True)
    
    pdf.ln(4)

def _render_question_text(pdf, question, number, font_name, use_braille, use_unicode, clean_text_fn):
    """Render question text."""
    pdf.set_font(font_name, size=12)
    
    q_text = clean_text_fn(question.get('question_text', question.get('question', '')))
    q_full = f"Q{number}. {q_text}"
    
    if use_braille and use_unicode:
        try:
            q_braille = text_to_braille(q_full)
            pdf.multi_cell(0, 7, q_braille)
        except:
            pdf.multi_cell(0, 7, q_full)
    else:
        pdf.multi_cell(0, 7, q_full)
    
    pdf.ln(3)

def _render_statements(pdf, statements, font_name, use_braille, use_unicode, clean_text_fn):
    """Render statement list."""
    pdf.set_font(font_name, size=11)
    
    for i, stmt in enumerate(statements, 1):
        stmt_clean = clean_text_fn(stmt)
        stmt_full = f"  {i}. {stmt_clean}"
        
        if use_braille and use_unicode:
            try:
                stmt_braille = text_to_braille(stmt_full)
                pdf.multi_cell(0, 6, stmt_braille)
            except:
                pdf.multi_cell(0, 6, stmt_full)
        else:
            pdf.multi_cell(0, 6, stmt_full)
    
    pdf.ln(3)

def _render_options(pdf, options, font_name, use_braille, use_unicode, clean_text_fn):
    """Render answer options."""
    pdf.set_font(font_name, size=11)
    
    for key in ['A', 'B', 'C', 'D']:
        if key in options:
            opt_clean = clean_text_fn(options[key])
            opt_full = f"  ({key}) {opt_clean}"
            
            if use_braille and use_unicode:
                try:
                    opt_braille = text_to_braille(opt_full)
                    pdf.multi_cell(0, 6, opt_braille)
                except:
                    pdf.multi_cell(0, 6, opt_full)
            else:
                pdf.multi_cell(0, 6, opt_full)

def _save_pdf(pdf, paper_id):
    """Save PDF to file."""
    os.makedirs('generated_papers', exist_ok=True)
    filename = f"braille_paper_{paper_id}.pdf"
    filepath = os.path.join('generated_papers', filename)
    pdf.output(filepath)
    return filepath
