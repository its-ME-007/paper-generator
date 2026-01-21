from flask import Flask, render_template, request, jsonify, send_file
import json
import random
from fpdf import FPDF
import os
from datetime import datetime
import unicodedata
from collections import defaultdict
from groq import Groq
from dotenv import load_dotenv

# Import Braille pipeline
from renderers.braille_renderer import generate_braille_pdf as render_braille_pdf

load_dotenv()

app = Flask(__name__)

# Initialize Groq for grading
client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

TRACKING_FILE = 'question_usage_tracking.json'
SUBMISSIONS_DIR = 'submissions'
ANSWER_KEYS_DIR = 'answer_keys'

def load_tracking():
    """Load question usage tracking"""
    if os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'questions': {}}

def save_tracking(tracking_data):
    """Save question usage tracking"""
    with open(TRACKING_FILE, 'w', encoding='utf-8') as f:
        json.dump(tracking_data, f, indent=2)

def update_question_usage(question_ids):
    """Update usage count for selected questions"""
    tracking = load_tracking()
    for qid in question_ids:
        qid_str = str(qid)
        if qid_str not in tracking['questions']:
            tracking['questions'][qid_str] = {'count': 0, 'last_used': None}
        tracking['questions'][qid_str]['count'] += 1
        tracking['questions'][qid_str]['last_used'] = datetime.now().isoformat()
    save_tracking(tracking)

def clean_text(text):
    """Clean text to remove or replace problematic Unicode characters"""
    if not isinstance(text, str):
        return text
    
    # Replace common Unicode symbols with ASCII equivalents
    replacements = {
        '\u2295': '(+)',  # ⊕ circled plus
        '\u2296': '(-)',  # ⊖ circled minus
        '\u2297': '(x)',  # ⊗ circled times
        '\u2299': '(.)',  # ⊙ circled dot
        '\u2260': '!=',   # ≠ not equal
        '\u2264': '<=',   # ≤ less than or equal
        '\u2265': '>=',   # ≥ greater than or equal
        '\u2192': '->',   # → rightwards arrow
        '\u2190': '<-',   # ← leftwards arrow
        '\u00b0': 'deg',  # ° degree sign
        '\u03c0': 'pi',   # π pi
        '\u221a': 'sqrt', # √ square root
        '\u00d7': 'x',    # × multiplication
        '\u00f7': '/',    # ÷ division
        '\u2032': '',     # ′ prime (removed)
        '\u2033': '',     # ″ double prime (removed)
        '\u201c': '',     # " left double quotation mark (removed)
        '\u201d': '',     # " right double quotation mark (removed)
        '\u2018': '',     # ' left single quotation mark (removed)
        '\u2019': '',     # ' right single quotation mark (removed)
        '\u201a': '',     # ‚ single low-9 quotation mark (removed)
        '\u201b': '',     # ‛ single high-reversed-9 quotation mark (removed)
        '\u201e': '',     # „ double low-9 quotation mark (removed)
        '\u201f': '',     # ‟ double high-reversed-9 quotation mark (removed)
        '\u2013': '-',    # – en dash
        '\u2014': '-',    # — em dash
        '\u2026': '...',  # … ellipsis
    }
    
    for unicode_char, replacement in replacements.items():
        text = text.replace(unicode_char, replacement)
    
    # Remove any remaining problematic characters
    # Keep only Latin-1 compatible characters
    cleaned = ''
    for char in text:
        try:
            char.encode('latin-1')
            cleaned += char
        except UnicodeEncodeError:
            # Try to find ASCII equivalent or skip
            try:
                normalized = unicodedata.normalize('NFKD', char)
                ascii_char = normalized.encode('ASCII', 'ignore').decode('ASCII')
                cleaned += ascii_char if ascii_char else '?'
            except:
                cleaned += '?'
    
    return cleaned

# Load question databases
def load_questions():
    """Load all question types from JSON files"""
    with open('type-based-jsons/mcq_questions.json', 'r', encoding='utf-8') as f:
        mcq_questions = json.load(f)['questions']
    
    with open('type-based-jsons/statement_based_questions.json', 'r', encoding='utf-8') as f:
        statement_questions = json.load(f)['questions']
    
    with open('type-based-jsons/passage_based_questions.json', 'r', encoding='utf-8') as f:
        passage_questions = json.load(f)['questions']
    
    return {
        'mcq': mcq_questions,
        'statement': statement_questions,
        'passage': passage_questions
    }

# Presets configuration
PRESETS = {
    'balanced': {'mcq': 30, 'statement': 30, 'passage': 20},
    'mcq_heavy': {'mcq': 50, 'statement': 20, 'passage': 10},
    'statement_heavy': {'mcq': 20, 'statement': 40, 'passage': 20},
    'passage_heavy': {'mcq': 20, 'statement': 20, 'passage': 40},
    'equal': {'mcq': 27, 'statement': 27, 'passage': 26}
}

@app.route('/')
def index():
    """Render the main page"""
    questions_db = load_questions()
    counts = {
        'mcq': len(questions_db['mcq']),
        'statement': len(questions_db['statement']),
        'passage': len(questions_db['passage'])
    }
    return render_template('paper_generator.html', presets=PRESETS, counts=counts)

@app.route('/generate', methods=['POST'])
def generate_paper():
    """Generate question paper based on user preferences"""
    try:
        data = request.json
        mcq_count = int(data.get('mcq', 0))
        statement_count = int(data.get('statement', 0))
        passage_count = int(data.get('passage', 0))
        
        # Validate total
        total = mcq_count + statement_count + passage_count
        if total != 80:
            return jsonify({'error': f'Total questions must be 80, got {total}'}), 400
        
        # Load questions
        questions_db = load_questions()
        tracking = load_tracking()
        
        # Validate available questions
        if mcq_count > len(questions_db['mcq']):
            return jsonify({'error': f'Not enough MCQ questions. Available: {len(questions_db["mcq"])}'}), 400
        if statement_count > len(questions_db['statement']):
            return jsonify({'error': f'Not enough statement questions. Available: {len(questions_db["statement"])}'}), 400
        if passage_count > len(questions_db['passage']):
            return jsonify({'error': f'Not enough passage questions. Available: {len(questions_db["passage"])}'}), 400
        
        # Smart sampling: prefer less-used questions
        def smart_sample(question_list, count):
            # Sort by usage count (least used first)
            sorted_questions = sorted(question_list, 
                key=lambda q: tracking['questions'].get(str(q.get('question_id', id(q))), {}).get('count', 0))
            return sorted_questions[:count]
        
        selected_mcq = smart_sample(questions_db['mcq'], mcq_count)
        selected_statement = smart_sample(questions_db['statement'], statement_count)
        selected_passage = smart_sample(questions_db['passage'], passage_count)
        
        # Combine and shuffle all questions
        all_questions = selected_mcq + selected_statement + selected_passage
        random.shuffle(all_questions)
        
        # Track question usage
        question_ids = [q.get('question_id', id(q)) for q in all_questions]
        update_question_usage(question_ids)
        
        # Generate paper ID
        paper_id = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Generate PDF and answer key
        pdf_path = generate_pdf(all_questions, paper_id)
        answer_key_path = generate_answer_key(all_questions, paper_id)
        
        # Generate Braille version using new pipeline
        braille_path = render_braille_pdf(all_questions, paper_id, clean_text)
        
        return jsonify({
            'success': True,
            'message': 'Question paper generated successfully!',
            'paper_id': paper_id,
            'pdf_url': f'/download/{os.path.basename(pdf_path)}',
            'answer_key_url': f'/download/{os.path.basename(answer_key_path)}',
            'braille_url': f'/download/{os.path.basename(braille_path)}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_pdf(questions, paper_id):
    """Generate unified PDF with shuffled questions"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Add header
    pdf.set_font("Arial", style="B", size=18)
    pdf.cell(0, 10, "UPSC Practice Question Paper", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, f"Paper ID: {paper_id}", ln=True, align='C')
    pdf.cell(0, 5, f"Generated on: {datetime.now().strftime('%d-%m-%Y %H:%M')}", ln=True, align='C')
    pdf.cell(0, 5, f"Total Questions: {len(questions)} | Time: 2 hours | Total Marks: 160", ln=True, align='C')
    pdf.ln(10)
    
    # Instructions
    pdf.set_font("Arial", style="B", size=11)
    pdf.cell(0, 6, "Instructions:", ln=True)
    pdf.set_font("Arial", size=10)
    pdf.multi_cell(0, 5, "1. Each question carries 2 marks.\n2. There is negative marking of 0.66 marks for wrong answers.\n3. Fill in your answers carefully in the submission form.")
    pdf.ln(8)
    
    # Add all questions (unified, already shuffled)
    for idx, question in enumerate(questions, start=1):
        add_question_to_pdf(pdf, question, idx)
    
    # Save PDF
    os.makedirs('generated_papers', exist_ok=True)
    filename = f"question_paper_{paper_id}.pdf"
    filepath = os.path.join('generated_papers', filename)
    pdf.output(filepath)
    
    # Save question mapping for grading
    save_paper_mapping(paper_id, questions)
    
    return filepath

def add_question_to_pdf(pdf, question, number):
    """Add any type of question to PDF"""
    # Add passage if present (for passage-based questions)
    passage = question.get('passage', '')
    if passage:
        pdf.set_font("Arial", style="I", size=9)
        pdf.set_fill_color(240, 240, 240)
        pdf.multi_cell(0, 5, f"Passage: {clean_text(passage)}", fill=True)
        pdf.ln(2)
    
    # Add question text
    pdf.set_font("Arial", style="B", size=11)
    question_text = clean_text(question.get('question_text', question.get('question', 'N/A')))
    pdf.multi_cell(0, 6, f"Q{number}. {question_text}")
    pdf.set_font("Arial", size=10)
    
    # Add statements if present (for statement-based questions)
    statements = question.get('statements', [])
    if statements:
        for i, stmt in enumerate(statements, 1):
            stmt_text = clean_text(stmt)
            pdf.multi_cell(0, 5, f"    {i}. {stmt_text}")
        pdf.ln(2)
    
    # Add options
    options = question.get('options', {})
    for key in ['A', 'B', 'C', 'D']:
        if key in options:
            option_text = clean_text(options[key])
            pdf.multi_cell(0, 5, f"    ({key}) {option_text}")
    
    pdf.ln(6)

def save_paper_mapping(paper_id, questions):
    """Save paper questions and answers for grading"""
    os.makedirs(SUBMISSIONS_DIR, exist_ok=True)
    mapping = {
        'paper_id': paper_id,
        'generated_at': datetime.now().isoformat(),
        'questions': []
    }
    
    for idx, q in enumerate(questions, start=1):
        mapping['questions'].append({
            'number': idx,
            'question_id': q.get('question_id', ''),
            'question_text': q.get('question_text', q.get('question', '')),
            'correct_answer': q.get('answer', ''),
            'question_type': q.get('question_type', ''),
            'subject': q.get('subject', '')
        })
    
    filepath = os.path.join(SUBMISSIONS_DIR, f'paper_{paper_id}.json')
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, indent=2)
    
    # Also save raw questions for translation
    questions_filepath = os.path.join(SUBMISSIONS_DIR, f'questions_{paper_id}.json')
    with open(questions_filepath, 'w', encoding='utf-8') as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)

def generate_answer_key(questions, paper_id):
    """Generate answer key PDF"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    
    # Header
    pdf.set_font("Arial", style="B", size=18)
    pdf.cell(0, 10, "Answer Key", ln=True, align='C')
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 5, f"Paper ID: {paper_id}", ln=True, align='C')
    pdf.ln(10)
    
    # Answer grid
    pdf.set_font("Arial", style="B", size=11)
    pdf.cell(30, 8, "Q. No.", 1, 0, 'C')
    pdf.cell(30, 8, "Answer", 1, 1, 'C')
    
    pdf.set_font("Arial", size=10)
    for idx, q in enumerate(questions, start=1):
        pdf.cell(30, 7, str(idx), 1, 0, 'C')
        pdf.cell(30, 7, q.get('answer', 'N/A'), 1, 1, 'C')
    
    # Save
    os.makedirs(ANSWER_KEYS_DIR, exist_ok=True)
    filename = f"answer_key_{paper_id}.pdf"
    filepath = os.path.join(ANSWER_KEYS_DIR, filename)
    pdf.output(filepath)
    
    return filepath

# Old generate_braille_pdf removed - now using renderers.braille_renderer pipeline

@app.route('/translate/<paper_id>/<language>', methods=['POST'])
def translate_paper(paper_id, language):
    """Translate question paper to different language using AI"""
    try:
        # Load questions
        questions_path = os.path.join(SUBMISSIONS_DIR, f'questions_{paper_id}.json')
        if not os.path.exists(questions_path):
            return jsonify({'error': 'Paper not found'}), 404
        
        with open(questions_path, 'r', encoding='utf-8') as f:
            questions = json.load(f)
        
        # Language mapping
        languages = {
            'hindi': 'Hindi (हिंदी)',
            'tamil': 'Tamil (தமிழ்)',
            'telugu': 'Telugu (తెలుగు)',
            'bengali': 'Bengali (বাংলা)',
            'marathi': 'Marathi (मराठी)',
            'gujarati': 'Gujarati (ગુજરાતી)',
            'kannada': 'Kannada (ಕನ್ನಡ)',
            'malayalam': 'Malayalam (മലയാളം)',
            'punjabi': 'Punjabi (ਪੰਜਾਬੀ)',
            'urdu': 'Urdu (اردو)'
        }
        
        if language not in languages:
            return jsonify({'error': 'Unsupported language'}), 400
        
        target_lang = languages[language]
        translated_questions = []
        
        # Preprocess questions to ensure clean JSON
        clean_questions = []
        for q in questions:
            clean_q = q.copy()
            # Ensure all text fields are properly encoded
            if 'question_text' in clean_q:
                clean_q['question_text'] = str(clean_q['question_text'])
            if 'question' in clean_q:
                clean_q['question'] = str(clean_q['question'])
            if 'statements' in clean_q and isinstance(clean_q['statements'], list):
                clean_q['statements'] = [str(s) for s in clean_q['statements']]
            if 'options' in clean_q and isinstance(clean_q['options'], dict):
                clean_q['options'] = {k: str(v) for k, v in clean_q['options'].items()}
            # Handle passage field (for passage-based questions)
            if 'passage' in clean_q and clean_q['passage']:
                clean_q['passage'] = str(clean_q['passage'])
            clean_questions.append(clean_q)
        
        # Translate in batches of 5 questions
        batch_size = 5
        for i in range(0, len(clean_questions), batch_size):
            batch = clean_questions[i:i+batch_size]
            batch_json = json.dumps(batch, ensure_ascii=False, indent=2)
            
            prompt = f"""Translate the following UPSC question paper questions to {target_lang}.

CRITICAL RULES:
1. Translate these fields: question_text (or question), statements, options (A, B, C, D), AND passage
2. The "passage" field contains reading comprehension text - translate it completely
3. Keep the EXACT same JSON structure - preserve all punctuation, quotes, and special characters
4. Do NOT translate: question_id, question_type, answer, subject
5. Maintain all field names in English
6. Keep all punctuation marks EXACTLY as they appear in the original
7. Return ONLY valid JSON array, no markdown, no extra text, no explanations

IMPORTANT: The output must be a valid JSON array that can be parsed by json.loads()

Questions to translate:
{batch_json}"""
            
            response = client.chat.completions.create(
                model='llama-3.3-70b-versatile',
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a professional translator. You MUST respond with ONLY a valid JSON array. No explanations, no markdown, no extra text - just the JSON array."
                    },
                    {
                        "role": "user", 
                        "content": prompt
                    }
                ],
                temperature=0.1,  # Lower temperature for more consistent JSON
                response_format={"type": "json_object"}  # Force JSON response
            )
            # Parse response
            ai_response = response.choices[0].message.content.strip()
            
            # Remove markdown code blocks
            if ai_response.startswith('```json'):
                ai_response = ai_response.split('```json', 1)[1].split('```', 1)[0].strip()
            elif ai_response.startswith('```'):
                ai_response = ai_response.split('```', 1)[1].split('```', 1)[0].strip()
            
            # If response is a JSON object with an array inside, extract it
            # (Some models wrap arrays in {"data": [...]} or {"result": [...]})
            if ai_response.startswith('{'):
                try:
                    temp_obj = json.loads(ai_response)
                    # Look for array in common keys
                    for key in ['data', 'result', 'questions', 'translated', 'items']:
                        if key in temp_obj and isinstance(temp_obj[key], list):
                            ai_response = json.dumps(temp_obj[key])
                            break
                except:
                    pass
            
            # Remove any leading/trailing text that's not part of JSON
            # Find the first [ and last ]
            start_idx = ai_response.find('[')
            end_idx = ai_response.rfind(']')
            
            if start_idx != -1 and end_idx != -1:
                ai_response = ai_response[start_idx:end_idx+1]
            
            # Fix common JSON issues
            ai_response = ai_response.replace('\n', ' ')  # Remove newlines
            ai_response = ai_response.replace('\r', '')   # Remove carriage returns
            
            try:
                batch_translated = json.loads(ai_response)
                if isinstance(batch_translated, list):
                    translated_questions.extend(batch_translated)
                else:
                    # If single object returned, wrap in list
                    translated_questions.append(batch_translated)
            except json.JSONDecodeError as e:
                # Log the problematic response for debugging
                print(f"JSON Parse Error at batch {i//batch_size + 1}: {e}")
                print(f"Problematic response: {ai_response[:1000]}")
                
                # Try to salvage partial data - skip this batch and continue
                print(f"Skipping batch {i//batch_size + 1}, continuing with next batch...")
                # Use original questions for this batch as fallback
                translated_questions.extend(batch)
        
        # Generate PDF with translated content
        pdf_path = generate_translated_pdf(translated_questions, paper_id, target_lang)
        
        return jsonify({
            'success': True,
            'message': f'Paper translated to {target_lang}',
            'pdf_url': f'/download/{os.path.basename(pdf_path)}'
        })
        
    except ValueError as ve:
        # Specific error for translation/parsing issues
        return jsonify({'error': f'Translation error: {str(ve)}'}), 500
    except json.JSONDecodeError as je:
        # JSON parsing error
        return jsonify({'error': f'JSON parsing error: {str(je)}. Please try again.'}), 500
    except Exception as e:
        # General error
        return jsonify({'error': f'Unexpected error: {str(e)}'}), 500

def generate_translated_pdf(questions, paper_id, language):
    """Generate PDF with translated questions"""
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    
    # Try to add Unicode font support
    try:
        if os.path.exists('DejaVuSans.ttf'):
            pdf.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
            pdf.set_font('DejaVu', size=12)
            use_unicode = True
        else:
            # Fallback to Arial with cleaned text
            pdf.set_font('Arial', size=12)
            use_unicode = False
    except Exception:
        pdf.set_font('Arial', size=12)
        use_unicode = False
    
    # Header
    font_name = 'DejaVu' if use_unicode else 'Arial'
    pdf.set_font(font_name, size=18)
    header_text = f"UPSC Practice Paper ({language})" if use_unicode else "UPSC Practice Paper (Translated)"
    pdf.cell(0, 10, header_text, ln=True, align='C')
    pdf.set_font(font_name, size=10)
    pdf.cell(0, 5, f"Paper ID: {paper_id}", ln=True, align='C')
    pdf.cell(0, 5, f"Generated: {datetime.now().strftime('%d-%m-%Y %H:%M')}", ln=True, align='C')
    
    if not use_unicode:
        pdf.set_font(font_name, size=9)
        pdf.cell(0, 5, "Note: Unicode font not available. Some characters may not display correctly.", ln=True, align='C')
    
    pdf.ln(10)
    
    # Questions
    for idx, question in enumerate(questions, start=1):
        # Passage if present (for passage-based questions)
        passage = question.get('passage', '')
        if passage:
            pdf.set_font(font_name, size=10)
            passage_text = clean_text(passage)  # Always clean text
            pdf.set_fill_color(240, 240, 240)
            pdf.multi_cell(0, 6, f"Passage: {passage_text}", fill=True)
            pdf.ln(3)
        
        # Question text
        pdf.set_font(font_name, size=11)
        q_text = question.get('question_text', question.get('question', 'N/A'))
        q_text = clean_text(q_text)  # Always clean text
        pdf.multi_cell(0, 7, f"Q{idx}. {q_text}")
        pdf.set_font(font_name, size=10)
        
        # Statements
        statements = question.get('statements', [])
        if statements:
            for i, stmt in enumerate(statements, 1):
                stmt_text = clean_text(stmt)  # Always clean text
                pdf.multi_cell(0, 6, f"    {i}. {stmt_text}")
            pdf.ln(2)
        
        # Options
        options = question.get('options', {})
        for key in ['A', 'B', 'C', 'D']:
            if key in options:
                opt_text = clean_text(options[key])  # Always clean text
                pdf.multi_cell(0, 6, f"    ({key}) {opt_text}")
        
        pdf.ln(6)
    
    # Save
    os.makedirs('generated_papers/translated', exist_ok=True)
    safe_lang = language.split('(')[0].strip().replace(' ', '_')
    filename = f"paper_{paper_id}_{safe_lang}.pdf"
    filepath = os.path.join('generated_papers/translated', filename)
    pdf.output(filepath)
    
    return filepath

@app.route('/download/<filename>')
@app.route('/download/<folder>/<filename>')
def download(filename, folder=None):
    """Download generated PDF"""
    # Check multiple directories
    if folder:
        filepath = os.path.join('generated_papers', folder, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
    
    for directory in ['generated_papers', ANSWER_KEYS_DIR, 'generated_papers/translated']:
        filepath = os.path.join(directory, filename)
        if os.path.exists(filepath):
            return send_file(filepath, as_attachment=True, download_name=filename)
    return jsonify({'error': 'File not found'}), 404

@app.route('/submit', methods=['GET'])
def submit_page():
    """Render submission page"""
    # Get list of available papers
    papers = []
    if os.path.exists(SUBMISSIONS_DIR):
        for file in os.listdir(SUBMISSIONS_DIR):
            if file.startswith('paper_') and file.endswith('.json'):
                paper_id = file.replace('paper_', '').replace('.json', '')
                papers.append(paper_id)
    papers.sort(reverse=True)
    return render_template('submit_answers.html', papers=papers)

@app.route('/get_paper/<paper_id>')
def get_paper(paper_id):
    """Get paper details for submission form"""
    filepath = os.path.join(SUBMISSIONS_DIR, f'paper_{paper_id}.json')
    if os.path.exists(filepath):
        with open(filepath, 'r', encoding='utf-8') as f:
            return jsonify(json.load(f))
    return jsonify({'error': 'Paper not found'}), 404

@app.route('/submit_answers', methods=['POST'])
def submit_answers():
    """Submit student answers via image upload"""
    try:
        # Get form data
        paper_id = request.form.get('paper_id')
        student_name = request.form.get('student_name', 'Anonymous')
        
        # Get uploaded image
        if 'answer_sheet' not in request.files:
            return jsonify({'error': 'No image uploaded'}), 400
        
        image_file = request.files['answer_sheet']
        if image_file.filename == '':
            return jsonify({'error': 'No image selected'}), 400
        
        # Save uploaded image
        os.makedirs('submissions/images', exist_ok=True)
        image_filename = f"{paper_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{image_file.filename}"
        image_path = os.path.join('submissions/images', image_filename)
        image_file.save(image_path)
        
        # Load paper mapping
        paper_path = os.path.join(SUBMISSIONS_DIR, f'paper_{paper_id}.json')
        if not os.path.exists(paper_path):
            return jsonify({'error': 'Paper not found'}), 404
        
        with open(paper_path, 'r', encoding='utf-8') as f:
            paper_data = json.load(f)
        
        # Extract answers from image using Gemini Vision
        total_questions = len(paper_data['questions'])
        prompt = f"""You are analyzing an answer sheet image for a UPSC practice test.

The answer sheet contains answers for questions 1 to {total_questions}.
Each question has options: A, B, C, or D.

Please extract ALL answers from the image and provide them in this EXACT JSON format:
{{
  "1": "A",
  "2": "B",
  "3": "C",
  ...
}}

Rules:
- Use question numbers as keys (as strings)
- Use uppercase letters (A, B, C, or D) as values
- If a question is not answered or unclear, use empty string ""
- Include ALL {total_questions} questions in the response
- Return ONLY the JSON object, no other text"""

        # Call Groq Vision API with llama-3.2-90b-vision-preview
        import base64
        with open(image_path, 'rb') as img_file:
            image_data = img_file.read()
            image_base64 = base64.b64encode(image_data).decode('utf-8')
        
        response = client.chat.completions.create(
            model='llama-3.2-90b-vision-preview',
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_base64}"
                            }
                        }
                    ]
                }
            ],
            temperature=0.1
        )
        
        # Parse extracted answers
        ai_response = response.choices[0].message.content.strip()
        # Remove markdown code blocks if present
        if ai_response.startswith('```json'):
            ai_response = ai_response.split('```json')[1].split('```')[0].strip()
        elif ai_response.startswith('```'):
            ai_response = ai_response.split('```')[1].split('```')[0].strip()
        
        try:
            answers = json.loads(ai_response)
        except json.JSONDecodeError:
            return jsonify({'error': 'Failed to parse answers from image. Please ensure the image is clear.'}), 400
        
        # Grade the answers
        results = []
        correct = 0
        incorrect = 0
        unanswered = 0
        
        for q in paper_data['questions']:
            q_num = str(q['number'])
            student_answer = answers.get(q_num, '').strip().upper()
            correct_answer = q['correct_answer'].strip().upper()
            
            is_correct = student_answer == correct_answer
            if not student_answer:
                status = 'unanswered'
                unanswered += 1
            elif is_correct:
                status = 'correct'
                correct += 1
            else:
                status = 'incorrect'
                incorrect += 1
            
            results.append({
                'question_number': q['number'],
                'student_answer': student_answer or 'Not Answered',
                'correct_answer': correct_answer,
                'status': status
            })
        
        # Calculate score
        score = (correct * 2) - (incorrect * 0.66)
        percentage = (score / 160) * 100
        
        # Save submission
        submission_id = f"{paper_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        submission_data = {
            'submission_id': submission_id,
            'paper_id': paper_id,
            'student_name': student_name,
            'submitted_at': datetime.now().isoformat(),
            'image_path': image_path,
            'extracted_answers': answers,
            'results': results,
            'statistics': {
                'correct': correct,
                'incorrect': incorrect,
                'unanswered': unanswered,
                'score': round(score, 2),
                'percentage': round(percentage, 2)
            }
        }
        
        os.makedirs('submissions/completed', exist_ok=True)
        submission_path = os.path.join('submissions/completed', f'{submission_id}.json')
        with open(submission_path, 'w', encoding='utf-8') as f:
            json.dump(submission_data, f, indent=2)
        
        # Generate AI feedback immediately
        ai_feedback = generate_ai_feedback(submission_data)
        submission_data['ai_feedback'] = ai_feedback
        submission_data['ai_graded_at'] = datetime.now().isoformat()
        
        with open(submission_path, 'w', encoding='utf-8') as f:
            json.dump(submission_data, f, indent=2)
        
        return jsonify({
            'success': True,
            'submission_id': submission_id,
            'statistics': submission_data['statistics'],
            'results': results,
            'ai_feedback': ai_feedback
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def generate_ai_feedback(submission):
    """Generate AI feedback for a submission"""
    prompt = f"""You are an expert UPSC examiner. Review this student's performance and provide detailed feedback.

Student: {submission['student_name']}
Score: {submission['statistics']['score']}/160 ({submission['statistics']['percentage']}%)
Correct: {submission['statistics']['correct']}
Incorrect: {submission['statistics']['incorrect']}
Unanswered: {submission['statistics']['unanswered']}

Provide:
1. Overall performance assessment (2-3 sentences)
2. Strengths identified
3. Areas needing improvement
4. Specific recommendations for study
5. Motivational closing remark

Keep it professional, constructive, and encouraging."""
    
    response = client.chat.completions.create(
        model='llama-3.3-70b-versatile',
        messages=[
            {"role": "system", "content": "You are an expert UPSC examiner providing constructive, professional feedback."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

@app.route('/grade_ai/<submission_id>', methods=['POST'])
def grade_with_ai(submission_id):
    """Retrieve AI feedback (already generated during submission)"""
    try:
        # Load submission
        submission_path = os.path.join('submissions/completed', f'{submission_id}.json')
        if not os.path.exists(submission_path):
            return jsonify({'error': 'Submission not found'}), 404
        
        with open(submission_path, 'r', encoding='utf-8') as f:
            submission = json.load(f)
        
        # Return existing AI feedback
        if 'ai_feedback' in submission:
            return jsonify({
                'success': True,
                'ai_feedback': submission['ai_feedback']
            })
        else:
            return jsonify({'error': 'AI feedback not available'}), 404
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/results/<submission_id>')
def view_results(submission_id):
    """View detailed results"""
    submission_path = os.path.join('submissions/completed', f'{submission_id}.json')
    if not os.path.exists(submission_path):
        return "Submission not found", 404
    
    with open(submission_path, 'r', encoding='utf-8') as f:
        submission = json.load(f)
    
    return render_template('results.html', submission=submission)

@app.route('/presets')
def get_presets():
    """Return available presets"""
    return jsonify(PRESETS)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
