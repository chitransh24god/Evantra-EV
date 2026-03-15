from flask import Flask, request, jsonify, render_template
from groq import Groq
import os
import base64
import json
import re
import mammoth
import tempfile

# Load .env file when running locally
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

app = Flask(__name__)

client = Groq(api_key=os.environ.get("GROQ_API_KEY", ""))
def extract_json(text):
    text = text.strip()
    text = re.sub(r"```json|```", "", text).strip()
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("No JSON found in response")

def extract_text_from_pdf(file_bytes):
    import fitz
    import os

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    text = ""
    for page in doc:
        text += page.get_text()
    doc.close()

    if len(text.strip()) > 10:
        return text

    # OCR fallback for scanned PDFs
    try:
        import pytesseract
        from pdf2image import convert_from_bytes

        # Windows path
        tesseract_win = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.path.exists(tesseract_win):
            pytesseract.pytesseract.tesseract_cmd = tesseract_win

        # Poppler path — Windows only, Linux has it built in
        poppler_win = r"C:\poppler\poppler-24.02.0\Library\bin"
        poppler_path = poppler_win if os.path.exists(poppler_win) else None

        images = convert_from_bytes(file_bytes, poppler_path=poppler_path)

        ocr_text = ""
        for img in images:
            ocr_text += pytesseract.image_to_string(img, lang="eng")

        if ocr_text.strip():
            return ocr_text

    except Exception:
        pass

    raise Exception("Could not extract text from this PDF. Please paste your resume text manually.")

def build_prompt(resume_text, job_desc=""):
    jd_section = f"\n\nJOB DESCRIPTION:\n{job_desc[:1500]}" if job_desc else ""
    return f"""You are a world-class ATS resume expert, career coach, and hiring manager with 20+ years of experience.
Analyse the resume below with extreme detail and honesty.{jd_section}

RESUME TEXT:
{resume_text[:5000]}

Be brutally honest. Identify EVERY issue dragging the score down. Return ONLY valid JSON (no markdown, no explanation):
{{
  "ats_score": <integer 0-100>,
  "score_breakdown": {{
    "formatting": <integer 0-100>,
    "keywords": <integer 0-100>,
    "experience": <integer 0-100>,
    "readability": <integer 0-100>,
    "impact": <integer 0-100>,
    "structure": <integer 0-100>
  }},
  "verdict": "<3-4 sentence brutally honest overall summary explaining exactly why the score is what it is>",
  "strengths": ["<5-7 specific strengths found in this exact resume>"],
  "critical_issues": [
    {{
      "issue": "<exact problem title>",
      "severity": "critical|high|medium|low",
      "explanation": "<2-3 sentences explaining exactly what is wrong and why it hurts the resume>",
      "fix": "<very specific actionable fix with example if possible>"
    }}
  ],
  "missing_keywords": ["<8-15 important keywords missing from this resume>"],
  "weak_lines": [
    {{
      "original": "<paste the actual weak line or bullet from the resume>",
      "problem": "<what is wrong with this line>",
      "improved": "<rewritten version of that exact line, stronger and ATS-optimised>"
    }}
  ],
  "skill_gaps": [
    {{
      "skill": "<missing skill name>",
      "priority": "high|medium|low",
      "reason": "<why this skill matters for this role or industry>"
    }}
  ],
  "section_feedback": {{
    "summary": "<detailed feedback on the summary/objective section, or note if missing>",
    "experience": "<detailed feedback on work experience section>",
    "education": "<detailed feedback on education section>",
    "skills": "<detailed feedback on skills section>",
    "formatting": "<specific formatting issues>"
  }},
  "quick_wins": [
    "<specific change that takes under 5 minutes and will immediately improve the score>"
  ],
  "rewrite_summary": "<write a fully rewritten professional summary for this person based on their resume>"
}}"""

def analyse_with_groq(prompt_text):
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt_text}],
        max_tokens=2000,
        temperature=0.3,
    )
    return response.choices[0].message.content

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/analyse", methods=["POST"])
def analyse():
    try:
        job_desc = request.form.get("job_desc", "")
        pasted   = request.form.get("pasted_text", "")
        file     = request.files.get("resume_file")
        resume_text = ""

        if not file or file.filename == "":
            if not pasted.strip():
                return jsonify({"error": "Please upload a file or paste resume text."}), 400
            resume_text = pasted
        else:
            filename = file.filename.lower()
            ext = filename.rsplit(".", 1)[-1] if "." in filename else ""

            if ext == "txt":
                resume_text = file.read().decode("utf-8", errors="ignore")

            elif ext in ("doc", "docx"):
                file_bytes = file.read()
                with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
                    tmp.write(file_bytes)
                    tmp_path = tmp.name
                with open(tmp_path, "rb") as f:
                    result_mammoth = mammoth.extract_raw_text(f)
                os.unlink(tmp_path)
                resume_text = result_mammoth.value
                if not resume_text.strip():
                    return jsonify({"error": "Could not extract text from this Word file."}), 400

            elif ext == "pdf":
                file_bytes = file.read()
                resume_text = extract_text_from_pdf(file_bytes)
                if not resume_text.strip():
                    return jsonify({"error": "Could not read this PDF. Please paste your resume text manually."}), 400

            elif ext in ("jpg", "jpeg", "png", "webp"):
                return jsonify({"error": "Please convert your image to PDF or DOCX, or paste the text manually."}), 400

            else:
                return jsonify({"error": "Unsupported file type: ." + ext}), 400

        prompt = build_prompt(resume_text, job_desc)
        raw    = analyse_with_groq(prompt)
        result = extract_json(raw)
        return jsonify(result)

    except json.JSONDecodeError as e:
        return jsonify({"error": "AI returned unexpected format. Please try again."}), 500
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(debug=True, port=5000)