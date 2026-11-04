import os, re, sqlite3, uuid, json, shutil
from pathlib import Path
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import fitz
import pytesseract
from PIL import Image
from docx import Document

BASE = Path(__file__).resolve().parent.parent
UPLOADS = BASE / 'backend' / 'uploads'
UPLOADS.mkdir(parents=True, exist_ok=True)
DB = BASE / 'backend' / 'portfoliomatch.db'
FRONTEND = BASE / 'frontend'
ALLOWED = {'.pdf', '.docx', '.txt', '.csv', '.png', '.jpg', '.jpeg'}

app = Flask(__name__, static_folder=str(FRONTEND), static_url_path='')
app.config['MAX_CONTENT_LENGTH'] = 10 * 1024 * 1024

SKILLS = [
    'HTML', 'HTML5', 'CSS', 'CSS3', 'JavaScript', 'TypeScript', 'React', 'React.js',
    'Angular', 'Vue', 'Node.js', 'Express', 'Express.js', 'Python', 'Java', 'C', 'C++',
    'C#', 'SQL', 'MySQL', 'PostgreSQL', 'MongoDB', 'Mongoose', 'REST API', 'REST APIs',
    'Git', 'GitHub', 'Docker', 'AWS', 'Azure', 'Figma', 'Machine Learning',
    'Data Science', 'Pandas', 'NumPy', 'TensorFlow', 'Flask', 'Django', 'Spring Boot',
    'Data Structures', 'Algorithms', 'OOP', 'Object-Oriented Programming', 'Postman',
    'Bootstrap', 'Tailwind CSS', 'Next.js', 'Firebase', 'Redis', 'Linux', 'Power BI',
    'Excel', 'Tableau', 'Scikit-learn', 'PyTorch', 'Kubernetes', 'Jenkins', 'PHP',
    'Laravel', 'Dart', 'Flutter', 'Kotlin', 'Swift', 'Android', 'iOS', 'GraphQL',
    'Selenium', 'Jest', 'Jupyter', 'Pillow', 'PyMuPDF', 'Tesseract OCR'
]
SKILL_ALIASES = {
    'html5':'HTML', 'css3':'CSS', 'react.js':'React', 'reactjs':'React',
    'nodejs':'Node.js', 'express.js':'Express', 'expressjs':'Express',
    'rest apis':'REST API', 'restful api':'REST API', 'restful apis':'REST API',
    'object-oriented programming':'OOP', 'object oriented programming':'OOP',
    'data structures and algorithms':'Data Structures', 'scikit learn':'Scikit-learn',
    'sklearn':'Scikit-learn', 'nextjs':'Next.js', 'tailwind':'Tailwind CSS'
}
def canonical_skill(skill):
    key = normalize(skill).lower()
    if key in SKILL_ALIASES:
        return SKILL_ALIASES[key]
    for item in SKILLS:
        if item.lower() == key:
            return item
    return skill


SAMPLE_JOBS = [
    ('Amazon', 'Software Development Engineer – 2026', 'India', 'Java, Python, C++, Data Structures, Algorithms, OOP, SQL, Git'),
    ('Microsoft', 'Software Engineer', 'India', 'C++, C#, Java, Python, SQL, Git, Azure, Data Structures'),
    ('Infosys', 'Frontend Developer', 'India', 'HTML, CSS, JavaScript, React, Git, REST API'),
    ('TCS', 'Full Stack Developer', 'India', 'JavaScript, React, Node.js, Express, MongoDB, SQL, Git'),
    ('Zoho', 'Software Developer', 'India', 'Java, SQL, JavaScript, HTML, CSS, Git'),
    ('Freshworks', 'Backend Developer', 'India', 'Node.js, Express, REST API, MongoDB, SQL, Git')
]

def db():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    return con

def ensure_legacy_job(con, company_name, title, description='', location='', job_type='', salary='', experience=''):
    """Map a displayed job to the existing ER-diagram company/job tables."""
    company = con.execute('SELECT company_id FROM company WHERE company_name=?', (company_name,)).fetchone()
    if company:
        company_id = company['company_id']
    else:
        cur = con.execute('INSERT INTO company(company_name) VALUES(?)', (company_name,))
        company_id = cur.lastrowid
    job = con.execute('SELECT job_id FROM job WHERE company_id=? AND job_title=?', (company_id, title)).fetchone()
    if job:
        return job['job_id']
    cur = con.execute(
        'INSERT INTO job(job_title,description,location,job_type,salary,experience_required,company_id) VALUES(?,?,?,?,?,?,?)',
        (title, description, location, job_type, salary, experience, company_id))
    return cur.lastrowid

def init_db():
    con = db()
    con.executescript("""
    PRAGMA foreign_keys = ON;
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        role TEXT NOT NULL DEFAULT 'jobseeker',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS company_profiles (
        user_id INTEGER PRIMARY KEY,
        company_name TEXT NOT NULL,
        industry TEXT,
        location TEXT,
        website TEXT,
        description TEXT,
        contact_person TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS company_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT,
        location TEXT,
        job_type TEXT,
        salary TEXT,
        experience_required TEXT,
        required_skills TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(company_user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS portfolios (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        filename TEXT NOT NULL,
        extracted_text TEXT,
        extracted_json TEXT,
        ocr_used INTEGER DEFAULT 0,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        company TEXT NOT NULL,
        title TEXT NOT NULL,
        location TEXT,
        required_skills TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS match_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        portfolio_id INTEGER,
        job_id INTEGER NOT NULL,
        compatibility INTEGER NOT NULL,
        skill_score INTEGER NOT NULL,
        matched_skills TEXT,
        missing_skills TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(portfolio_id) REFERENCES portfolios(id),
        FOREIGN KEY(job_id) REFERENCES jobs(id)
    );

    -- ER diagram entities
    CREATE TABLE IF NOT EXISTS education (
        education_id INTEGER PRIMARY KEY AUTOINCREMENT,
        degree TEXT, institution TEXT, specialization TEXT,
        start_year TEXT, end_year TEXT, cgpa TEXT, user_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS certification (
        certification_id INTEGER PRIMARY KEY AUTOINCREMENT,
        certificate_name TEXT, issuing_organization TEXT, issue_date TEXT,
        expiry_date TEXT, certificate_link TEXT, user_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS project (
        project_id INTEGER PRIMARY KEY AUTOINCREMENT,
        project_name TEXT, description TEXT, start_date TEXT, end_date TEXT,
        project_link TEXT, user_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS experience (
        experience_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT, job_role TEXT, start_date TEXT, end_date TEXT,
        description TEXT, user_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS achievement (
        achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT, description TEXT, achievement_date TEXT, user_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS skill (
        skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill_name TEXT NOT NULL, skill_type TEXT, user_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS company (
        company_id INTEGER PRIMARY KEY AUTOINCREMENT,
        company_name TEXT UNIQUE NOT NULL, industry TEXT, location TEXT,
        website TEXT, description TEXT
    );
    CREATE TABLE IF NOT EXISTS job (
        job_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_title TEXT NOT NULL, description TEXT, location TEXT,
        job_type TEXT, salary TEXT, experience_required TEXT, company_id INTEGER,
        FOREIGN KEY(company_id) REFERENCES company(company_id)
    );
    CREATE TABLE IF NOT EXISTS application (
        application_id INTEGER PRIMARY KEY AUTOINCREMENT,
        applied_date TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'Saved',
        remarks TEXT, user_id INTEGER, job_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(job_id) REFERENCES job(job_id)
    );
    CREATE TABLE IF NOT EXISTS saves (
        user_id INTEGER NOT NULL, job_id INTEGER NOT NULL,
        saved_at TEXT DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, job_id),
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(job_id) REFERENCES job(job_id)
    );
    CREATE TABLE IF NOT EXISTS job_match (
        match_id INTEGER PRIMARY KEY AUTOINCREMENT,
        match_percentage INTEGER, matched_skills TEXT, missing_skills TEXT,
        match_date TEXT DEFAULT CURRENT_TIMESTAMP, user_id INTEGER, job_id INTEGER,
        portfolio_id INTEGER,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(job_id) REFERENCES job(job_id),
        FOREIGN KEY(portfolio_id) REFERENCES portfolios(id)
    );
    CREATE TABLE IF NOT EXISTS job_required_skill (
        job_id INTEGER NOT NULL, skill_id INTEGER NOT NULL,
        PRIMARY KEY(job_id, skill_id),
        FOREIGN KEY(job_id) REFERENCES job(job_id),
        FOREIGN KEY(skill_id) REFERENCES skill(skill_id)
    );
    """)
    # Safe schema migration for existing local databases created by older versions.
    user_columns = [r['name'] for r in con.execute('PRAGMA table_info(users)').fetchall()]
    if 'role' not in user_columns:
        con.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'jobseeker'")
    count = con.execute('SELECT COUNT(*) c FROM jobs').fetchone()['c']
    if count == 0:
        con.executemany('INSERT INTO jobs(company,title,location,required_skills) VALUES (?,?,?,?)', SAMPLE_JOBS)
    for row in con.execute('SELECT company,title,location FROM jobs').fetchall():
        ensure_legacy_job(con, row['company'], row['title'], location=row['location'] or '')
    con.commit()

    # Seed the ER COMPANY/JOB/JOB_REQUIRED_SKILL tables from the same local job dataset.
    for company_name, title, location, required in SAMPLE_JOBS:
        con.execute('INSERT OR IGNORE INTO company(company_name,industry,location,description) VALUES(?,?,?,?)',
                    (company_name, 'Technology', location, f'{company_name} technology roles'))
        company_id = con.execute('SELECT company_id FROM company WHERE company_name=?', (company_name,)).fetchone()['company_id']
        existing = con.execute('SELECT job_id FROM job WHERE job_title=? AND company_id=?', (title, company_id)).fetchone()
        if not existing:
            cur = con.execute('INSERT INTO job(job_title,description,location,job_type,experience_required,company_id) VALUES(?,?,?,?,?,?)',
                              (title, f'{title} at {company_name}. Required skills: {required}', location, 'Full-time', 'Entry-level / role-dependent', company_id))
            er_job_id = cur.lastrowid
        else:
            er_job_id = existing['job_id']
        for skill_name in [normalize(x) for x in required.split(',') if normalize(x)]:
            row = con.execute('SELECT skill_id FROM skill WHERE user_id IS NULL AND lower(skill_name)=lower(?)', (skill_name,)).fetchone()
            if not row:
                cur = con.execute('INSERT INTO skill(skill_name,skill_type,user_id) VALUES(?,?,NULL)', (skill_name, 'Job requirement'))
                skill_id = cur.lastrowid
            else:
                skill_id = row['skill_id']
            con.execute('INSERT OR IGNORE INTO job_required_skill(job_id,skill_id) VALUES(?,?)', (er_job_id, skill_id))
    con.commit()
    con.close()


def normalize(s):
    return re.sub(r'\s+', ' ', s or '').strip()

def configure_tesseract():
    configured = os.environ.get('TESSERACT_CMD')
    candidates = [
        configured,
        r'C:\Program Files\Tesseract-OCR\tesseract.exe',
        r'C:\Program Files (x86)\Tesseract-OCR\tesseract.exe'
    ]
    if not shutil.which('tesseract'):
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                pytesseract.pytesseract.tesseract_cmd = candidate
                break

configure_tesseract()

def ocr_image(img):
    # Upscale and improve contrast before OCR; good source image quality still matters.
    from PIL import ImageOps, ImageEnhance, ImageFilter
    img = img.convert('RGB')
    img.thumbnail((2600, 3400))
    if img.width < 1600:
        img = img.resize((int(img.width * 1.5), int(img.height * 1.5)))
    gray = ImageOps.grayscale(img)
    gray = ImageOps.autocontrast(gray)
    gray = ImageEnhance.Sharpness(gray).enhance(1.5)
    return pytesseract.image_to_string(gray, config='--oem 3 --psm 6')

def extract_pdf(path):
    doc = fitz.open(path)
    pages, ocr = [], False
    for page in doc:
        text = page.get_text('text').strip()
        images = page.get_images(full=True)
        # Scan pages and image-heavy pages need OCR. Preserve selectable text as well.
        if len(text) < 120 or (images and len(text) < 500):
            ocr = True
            pix = page.get_pixmap(matrix=fitz.Matrix(2.5, 2.5), alpha=False)
            img = Image.frombytes('RGB', [pix.width, pix.height], pix.samples)
            scanned = ocr_image(img).strip()
            if len(scanned) > len(text):
                text = (text + '\n' + scanned).strip() if text else scanned
        pages.append(text)
    doc.close()
    return '\n'.join(pages), ocr

def extract_docx(path):
    """Extract DOCX text in document order; read table columns separately for resume layouts."""
    from docx.table import Table
    from docx.text.paragraph import Paragraph
    from docx.oxml.text.paragraph import CT_P
    from docx.oxml.table import CT_Tbl
    doc = Document(path)
    parts = []
    for child in doc.element.body.iterchildren():
        if isinstance(child, CT_P):
            value = Paragraph(child, doc).text.strip()
            if value: parts.append(value)
        elif isinstance(child, CT_Tbl):
            table = Table(child, doc)
            if not table.rows: continue
            columns = max(len(row.cells) for row in table.rows)
            # Many resume templates use one table with a left sidebar and a right content column.
            # Reading down each column prevents unrelated sections from being interleaved row by row.
            for col in range(columns):
                for row in table.rows:
                    if col < len(row.cells):
                        cell = row.cells[col]
                        value = '\n'.join(p.text.strip() for p in cell.paragraphs if p.text.strip())
                        if value: parts.extend(x for x in value.splitlines() if x.strip())
    return '\n'.join(parts), False

def extract_file(path):
    ext = Path(path).suffix.lower()
    if ext == '.pdf': return extract_pdf(path)
    if ext == '.docx': return extract_docx(path)
    if ext in {'.txt', '.csv'}: return Path(path).read_text(encoding='utf-8', errors='ignore'), False
    if ext in {'.png', '.jpg', '.jpeg'}:
        return ocr_image(Image.open(path)), True
    raise ValueError('Unsupported file type')

SECTION_ALIASES = {
    'skills': ['skills', 'technical skills', 'core skills', 'technical toolkit', 'skill set', 'competencies', 'tools and technologies', 'tools & skills', 'technical profile', 'programming languages'],
    'projects': ['projects', 'project', 'project work', 'project experience', 'academic projects', 'personal projects', 'key projects', 'selected projects', 'selected project', 'project portfolio', 'academic project', 'personal project', 'major projects', 'mini projects'],
    'education': ['education', 'educational details', 'academic background', 'academic qualification', 'qualifications', 'educational qualification', 'education details', 'academic details', 'educational background', 'academic qualifications', 'education qualification', 'education background'],
    'experience': ['experience', 'work experience', 'internship', 'internships', 'professional experience', 'employment history', 'work history', 'career experience', 'work experience and internships', 'internship experience', 'professional background', 'internship experience', 'professional experience'],
    'certifications': ['certifications', 'certification', 'certificates', 'certificate', 'licenses and certifications', 'licenses & certifications', 'courses', 'relevant courses', 'certifications & achievements', 'certifications and courses', 'certifications & courses'],
    'achievements': ['achievements', 'awards', 'honors', 'honours']
}
ALL_HEADINGS = [h for vals in SECTION_ALIASES.values() for h in vals] + [
    'profile', 'summary', 'professional summary', 'about me', 'career summary', 'objective', 'contact',
    'additional information', 'personal details', 'interests', 'languages', 'technical profile',
    'declaration', 'hobbies', 'references', 'publications', 'soft skills', 'cover letter', 'my contact', 'professional qualification', 'professional skills', 'technical skills', 'areas of interest'
]

def _clean_line(line):
    line = normalize(line).strip()
    line = re.sub(r'^(?:[•●▪◦*▪✓✔★☆►➢➤\-–—]+|\d+[.)])\s*', '', line)
    return normalize(line).strip(' |\t')

def heading_key(line):
    cleaned = _clean_line(line).lower().strip(': |-')
    cleaned = re.sub(r'\s+', ' ', cleaned)
    for key, names in SECTION_ALIASES.items():
        if cleaned in names:
            return key
    return None

def extract_section_lines(text, section):
    """Extract only the requested section, stopping at the next section heading."""
    out, active = [], False
    for original in text.replace('\r', '\n').splitlines():
        raw = _clean_line(original)
        if not raw:
            continue
        # Exact heading or heading with inline content (e.g. Education: B.E. ...).
        key = heading_key(raw)
        if key:
            active = key == section
            continue
        inline_match = None
        low = raw.lower()
        for key_name, aliases in SECTION_ALIASES.items():
            for alias in sorted(aliases, key=len, reverse=True):
                # Handle inline section heading followed by content, often seen in PDF extraction.
                m = re.match(r'^' + re.escape(alias) + r'\s*(?::|[|—–-])\s*(.+)$', raw, re.I)
                if not m and raw[:len(alias)].isupper() and len(alias) >= 6:
                    m = re.match(r'^' + re.escape(alias) + r'\s{1,}(.+)$', raw, re.I)
                if m and m.group(1).strip():
                    inline_match = (key_name, m.group(1).strip())
                    break
            if inline_match:
                break
        if inline_match:
            active = inline_match[0] == section
            if active and inline_match[1]: out.append(_clean_line(inline_match[1]))
            continue
        # A standalone heading with punctuation/numbering also ends the current section.
        if low.strip(': |-') in {h.lower() for h in ALL_HEADINGS}:
            active = False
            continue
        if active:
            out.append(raw)
    return out

def group_section_entries(lines, section):
    """Group wrapped resume lines into records; never treat each line as a record."""
    lines = [_clean_line(x) for x in lines if _clean_line(x)]
    if not lines: return []
    if section == 'certifications':
        entries=[]
        continuation = re.compile(r'^(?:issued by|offered by|provided by|issuer|date|valid until|credential id|https?://|www\.)', re.I)
        for line in lines:
            # DOCX/PDF export sometimes flattens several certificates into one paragraph.
            pieces=re.split(r'(?=\b(?:NPTEL\s*[-–:]|IEEE(?:\s+Certification)?\s*[-–:]|Coursera\s*[-–:]|Udemy\s*[-–:]|Internship\s+at\b))',line,flags=re.I)
            for piece in [x.strip() for x in pieces if x.strip()]:
                if entries and continuation.search(piece): entries[-1] += ' | ' + piece
                else: entries.append(piece)
        return _dedupe_entries(entries)
    if section == 'education':
        # A qualification starts at degree/class/level, or at an institution line carrying its own year.
        qual = re.compile(r'\b(?:B\.?E\.?|B\.?Tech\.?|B\.?Sc\.?|M\.?E\.?|M\.?Tech\.?|M\.?Sc\.?|M\.?Com\.?|B\.?Com\.?|Bachelor|Master|Ph\.?D|Diploma|HSC|SSLC|\b(?:Class|Grade)\s*(?:X|XII|10|12|10th|12th)|12th\s*(?:std|standard)|10th\s*(?:std|standard))\b', re.I)
        starts=[]
        for i,line in enumerate(lines):
            has_year=bool(re.search(r'\b(?:19|20)\d{2}\b', line))
            institution=bool(re.search(r'\b(?:college|university|school|institute|academy)\b', line, re.I))
            if qual.search(line) or (has_year and institution): starts.append(i)
        if not starts: starts=[0]
        # Institution-only lines immediately before a qualification are attached to that qualification.
        groups=[]
        for i,line in enumerate(lines):
            if not groups: groups.append(line); continue
            is_start=i in starts
            is_institution=bool(re.search(r'\b(?:college|university|school|institute|academy)\b',line,re.I))
            previous_has_institution=bool(re.search(r'\b(?:college|university|school|institute|academy)\b',groups[-1],re.I))
            previous_has_qualification=bool(qual.search(groups[-1]))
            # A second institution in the current entry is a new education record.
            if is_start or (is_institution and previous_has_institution and previous_has_qualification):
                groups.append(line)
            else: groups[-1] += ' | ' + line
        # Merge a leading institution-only line into the following degree entry when adjacent.
        fixed=[]
        for entry in groups:
            if fixed and re.search(r'\b(?:college|university|school|institute)\b', fixed[-1], re.I) and not qual.search(fixed[-1]) and qual.search(entry):
                fixed[-1] += ' | ' + entry
            else: fixed.append(entry)
        return _dedupe_entries(fixed)
    if section == 'projects':
        # Split flattened paragraphs when several dated project titles were merged together.
        expanded=[]
        title_boundary=re.compile(r'(?<=[.!])\s+(?=[A-Z][A-Za-z0-9 &/+-]{2,85}\s*\(\s*(?:19|20)\d{2}\s*\))')
        for original_line in lines:
            expanded.extend(x.strip() for x in title_boundary.split(original_line) if x.strip())
        lines=expanded
        entries=[]; current=[]
        action = re.compile(r'\b(?:developed|built|created|implemented|designed|engineered|worked|responsible|integrated|automated|analyzed|analysed|provided|used to|using|technologies used|tools used|features include|this application|the system|the project|project aims|objective)\b', re.I)
        metadata = re.compile(r'^(?:technologies(?: used)?|tech stack|tools(?: used)?|description|my role|role|duration|github|project link)\s*:', re.I)
        title_year = re.compile(r'\b(?:19|20)\d{2}\b')
        def looks_title(line):
            if metadata.search(line) or action.search(line): return False
            if len(line.split()) <= 9 and (title_year.search(line) or re.search(r'\b(?:system|application|platform|website|app|tracker|analyzer|analyser|management|dashboard|portal|project|buddy|connect|ordering|tracker)\b', line, re.I)):
                return True
            return False
        for line in lines:
            explicit = bool(re.match(r'^(?:project\s*\d*\s*[:.)-]|\d+[.)])\s*', line, re.I))
            title_desc = re.match(r'^(.{2,75}?)\s+[—–:]\s+(.+)$', line)
            # A dated project heading is a strong boundary even when its description
            # and technology stack were flattened into the same PDF/DOCX paragraph.
            if title_year.search(line) and not metadata.search(line) and not re.match(r'^(?:developed|built|created|implemented|designed|worked|responsible|using)\b', line, re.I):
                if current: entries.append(' | '.join(current)); current=[]
                current=[line]
            elif title_desc and len(title_desc.group(1).split()) <= 9 and (action.search(title_desc.group(2)) or title_year.search(title_desc.group(1))):
                if current: entries.append(' | '.join(current)); current=[]
                entries.append(line)
            elif explicit or (looks_title(line) and (current or not entries)):
                if current: entries.append(' | '.join(current))
                current=[re.sub(r'^(?:project\s*\d*\s*[:.)-]|\d+[.)])\s*','',line,flags=re.I)]
            elif looks_title(line) and entries:
                if current: entries.append(' | '.join(current))
                current=[line]
            else:
                if not current: current=[line]
                else: current.append(line)
        if current: entries.append(' | '.join(current))
        # A title followed by technology metadata and its bullet description remains one entry.
        return _dedupe_entries(entries)
    if section == 'experience':
        role = re.compile(r'\b(?:intern|internship|developer|engineer|analyst|designer|manager|consultant|administrator|architect|trainee|specialist|scientist|coordinator|executive|technician|branch manager|assistant manager|clerk|professional banker)\b', re.I)
        starts=[]
        for i,line in enumerate(lines):
            if role.search(line) and (re.search(r'\b(?:19|20)\d{2}\b|present|current|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec\b', line, re.I) or len(line.split())<=14):
                starts.append(i)
        if not starts: return [' | '.join(lines)]
        if not starts: return []
        lines=lines[starts[0]:]
        starts=[x-starts[0] for x in starts]
        groups=[]
        for i,line in enumerate(lines):
            if i in starts and groups: groups.append(line)
            elif groups: groups[-1] += ' | ' + line
            else: groups.append(line)
        return _dedupe_entries(groups)
    return _dedupe_entries(lines)

def _dedupe_entries(items):
    out=[]; seen=set()
    for item in items:
        item=normalize(item).strip(' |')
        key=re.sub(r'[^a-z0-9]+',' ',item.lower()).strip()
        if item and key not in seen: out.append(item); seen.add(key)
    return out

def extract_name(text):
    # Prefer a short first-line name, but avoid generic headings and role labels.
    skip = {'resume','curriculum vitae','portfolio','cv','profile','about me','software engineer','developer'}
    for line in text.splitlines()[:12]:
        line = normalize(line).strip('|•- ')
        if not line or '@' in line or re.search(r'\d{5,}', line):
            continue
        if line.lower().strip(':') in skip:
            continue
        if len(line.split()) <= 5 and re.fullmatch(r"[A-Za-z][A-Za-z .'-]+", line) :
            # Names in portfolios are often uppercase or title case; ignore all-caps section headings.
            if line.lower() not in [x.lower() for x in ALL_HEADINGS] and len(line) < 45:
                return line.title() if line.isupper() else line
    return ''

def extract_skills(text):
    low = text.lower()
    found = []
    # Match longer phrases first and enforce word boundaries to avoid e.g. C inside "CSS".
    catalog = sorted(SKILLS, key=len, reverse=True)
    for skill in catalog:
        variants = [skill]
        if skill == 'React.js': variants += ['ReactJS']
        if skill == 'Node.js': variants += ['NodeJS']
        if skill == 'Express.js': variants += ['ExpressJS']
        if skill == 'REST API': variants += ['REST APIs', 'RESTful API', 'RESTful APIs']
        if skill == 'OOP': variants += ['object-oriented programming', 'object oriented programming']
        if skill == 'HTML': variants += ['HTML5']
        if skill == 'CSS': variants += ['CSS3']
        if any(re.search(r'(?<![a-z0-9+#])' + re.escape(v.lower()) + r'(?![a-z0-9])', low) for v in variants):
            canonical = canonical_skill(skill)
            if canonical not in found:
                found.append(canonical)
    # Collapse aliases/duplicates and keep original catalog order by first detection.
    result = []
    for s in found:
        c = canonical_skill(s)
        if c not in result:
            result.append(c)
    return result

def extract_info(text):
    emails = re.findall(r'[\w.+-]+@[\w-]+\.[\w.-]+', text)
    phones = re.findall(r'(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)', text)
    urls = re.findall(r'(?:https?://)?(?:www\.)?(?:linkedin\.com|github\.com)/[^\s|,]+', text, re.I)

    projects = extract_section_lines(text, 'projects')
    education = extract_section_lines(text, 'education')
    experience = extract_section_lines(text, 'experience')
    certs = extract_section_lines(text, 'certifications')
    # Use fallback evidence lines only when the corresponding section wasn't found.
    if not projects:
        projects = [normalize(x).strip('•-* ') for x in text.splitlines()
                    if re.search(r'\b(project|system|application|website|platform|dashboard)\b', x, re.I)][:8]
    if not education:
        education = [normalize(x) for x in text.splitlines()
                     if re.search(r'\b(B\.?E\.?|B\.?Tech|Bachelor|Master|M\.?Tech|BSc|MSc|CGPA|GPA|University|College)\b', x, re.I)][:8]
    if not experience:
        experience = [normalize(x) for x in text.splitlines()
                      if re.search(r'\b(intern|developer|engineer|analyst|worked|employment|experience)\b', x, re.I)][:8]

    if not certs:
        # Some resumes place credentials under Professional Qualification or inline text
        # rather than a dedicated Certifications heading.
        certs = [normalize(x) for x in text.splitlines()
                 if re.search(r'\b(?:NPTEL|IEEE|Coursera|Udemy|CAIIB|JAIIB|certificate course|certification|certified|license)\b', x, re.I)][:15]
    skills = extract_skills(text)
    # A section's contents are stored as readable evidence; duplicates are removed.
    def dedupe(items):
        result = []
        for item in items:
            item = normalize(item)
            if item and item not in result:
                result.append(item)
        return result[:15]

    # Merge wrapped lines into logical entries before deduplication. This prevents
    # every line in a degree/job/project description from being counted separately.
    projects = group_section_entries(projects, 'projects')
    education = group_section_entries(education, 'education')
    experience = group_section_entries(experience, 'experience')
    certs = group_section_entries(certs, 'certifications')
    projects, education, experience, certs = map(dedupe, [projects, education, experience, certs])
    score = min(100, 15 + len(skills)*4 + min(20, len(projects)*4) +
                min(15, len(experience)*3) + (10 if education else 0) + (5 if certs else 0))
    return {
        'name': extract_name(text), 'email': emails[0] if emails else '',
        'phone': phones[0].strip() if phones else '', 'links': urls[:5],
        'skills': skills, 'projects': projects, 'education': education,
        'experience': experience, 'certifications': certs, 'portfolio_score': score
    }


def skill_key(skill):
    return re.sub(r'[^a-z0-9+#]', '', canonical_skill(skill).lower())

def job_match(profile, job):
    required = [normalize(x) for x in (job.get('required_skills') or '').split(',') if normalize(x)]
    candidate = {skill_key(x) for x in profile.get('skills', [])}
    matched, missing = [], []
    for item in required:
        key = skill_key(item)
        if key in candidate:
            matched.append(item)
        else:
            missing.append(item)
    skill_score = round(len(matched) / len(required) * 100) if required else 0
    project_bonus = 5 if profile.get('projects') else 0
    final = min(100, round(skill_score * 0.95 + project_bonus))
    return {'matched_skills': matched, 'missing_skills': missing,
            'skill_score': skill_score, 'compatibility': final}

def save_profile_sections(con, user_id, profile):
    if not user_id:
        return
    uid = int(user_id)
    # These ER tables represent the user's latest extracted profile. Portfolio history
    # itself remains preserved in portfolios, with the extracted JSON per upload.
    for table in ['education','certification','project','experience','achievement']:
        con.execute(f'DELETE FROM {table} WHERE user_id=?', (uid,))
    con.execute('DELETE FROM skill WHERE user_id=?', (uid,))
    for item in profile.get('skills', []):
        con.execute('INSERT INTO skill(skill_name,skill_type,user_id) VALUES(?,?,?)', (item, 'Extracted', uid))
    for item in profile.get('education', []):
        con.execute('INSERT INTO education(degree,institution,specialization,user_id) VALUES(?,?,?,?)',
                    (item[:250], '', '', uid))
    for item in profile.get('certifications', []):
        con.execute('INSERT INTO certification(certificate_name,issuing_organization,user_id) VALUES(?,?,?)',
                    (item[:250], '', uid))
    for item in profile.get('projects', []):
        con.execute('INSERT INTO project(project_name,description,user_id) VALUES(?,?,?)',
                    (item[:180], item[:1000], uid))
    for item in profile.get('experience', []):
        con.execute('INSERT INTO experience(job_role,description,user_id) VALUES(?,?,?)',
                    (item[:180], item[:1000], uid))


@app.route('/')
def index(): return send_from_directory(FRONTEND, 'index.html')

@app.post('/api/register')
def register():
    data=request.get_json() or {}; name=normalize(data.get('name')); email=normalize(data.get('email')).lower(); pw=data.get('password','')
    role=normalize(data.get('role','jobseeker')).lower()
    if role not in ('jobseeker','company'): return jsonify(error='Choose a valid account type.'),400
    if not name or not email or len(pw)<4: return jsonify(error='Enter name, valid email and password of at least 4 characters.'),400
    con=db()
    try:
        cur=con.execute('INSERT INTO users(name,email,password_hash,role) VALUES(?,?,?,?)',(name,email,generate_password_hash(pw),role)); uid=cur.lastrowid
        if role=='company':
            con.execute('INSERT INTO company_profiles(user_id,company_name,contact_person) VALUES(?,?,?)',(uid,normalize(data.get('company_name')) or name,name))
        con.commit()
        return jsonify(user_id=uid,name=name,email=email,role=role)
    except sqlite3.IntegrityError: return jsonify(error='Email already registered.'),409
    finally: con.close()

@app.post('/api/login')
def login():
    data=request.get_json() or {}; email=normalize(data.get('email')).lower(); pw=data.get('password',''); role=normalize(data.get('role','jobseeker')).lower()
    con=db(); u=con.execute('SELECT * FROM users WHERE email=?',(email,)).fetchone(); con.close()
    if not u or not check_password_hash(u['password_hash'],pw): return jsonify(error='Invalid email or password.'),401
    if (u['role'] or 'jobseeker') != role: return jsonify(error='This account belongs to the other login type. Choose the correct login.'),403
    return jsonify(user_id=u['id'],name=u['name'],email=u['email'],role=u['role'] or 'jobseeker')

@app.get('/api/company/profile')
def company_profile():
    uid=request.args.get('user_id',type=int)
    if not uid: return jsonify(error='Missing company account.'),400
    con=db(); row=con.execute('SELECT cp.*,u.email FROM company_profiles cp JOIN users u ON u.id=cp.user_id WHERE cp.user_id=? AND u.role=\'company\'',(uid,)).fetchone(); con.close()
    return jsonify(profile=dict(row) if row else {})

@app.post('/api/company/profile')
def update_company_profile():
    data=request.get_json() or {}; uid=data.get('user_id')
    if not uid: return jsonify(error='Missing company account.'),400
    con=db(); userrow=con.execute("SELECT id FROM users WHERE id=? AND role='company'",(uid,)).fetchone()
    if not userrow: con.close(); return jsonify(error='Company account not found.'),404
    values=(normalize(data.get('company_name')),normalize(data.get('industry')),normalize(data.get('location')),normalize(data.get('website')),normalize(data.get('description')),normalize(data.get('contact_person')))
    if not values[0]: con.close(); return jsonify(error='Company name is required.'),400
    con.execute("INSERT INTO company_profiles(user_id,company_name,industry,location,website,description,contact_person) VALUES(?,?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET company_name=excluded.company_name,industry=excluded.industry,location=excluded.location,website=excluded.website,description=excluded.description,contact_person=excluded.contact_person",(uid,*values))
    con.commit(); con.close(); return jsonify(ok=True)

@app.get('/api/company/jobs')
def company_jobs():
    uid=request.args.get('user_id',type=int)
    con=db(); rows=con.execute('SELECT * FROM company_jobs WHERE company_user_id=? ORDER BY id DESC',(uid,)).fetchall(); con.close()
    return jsonify(jobs=[dict(r) for r in rows])

@app.post('/api/company/jobs')
def create_company_job():
    data=request.get_json() or {}; uid=data.get('user_id'); title=normalize(data.get('title')); skills=normalize(data.get('required_skills'))
    if not uid or not title or not skills: return jsonify(error='Job title and required skills are required.'),400
    con=db(); userrow=con.execute("SELECT id FROM users WHERE id=? AND role='company'",(uid,)).fetchone()
    if not userrow: con.close(); return jsonify(error='Company account not found.'),404
    cur=con.execute('INSERT INTO company_jobs(company_user_id,title,description,location,job_type,salary,experience_required,required_skills) VALUES(?,?,?,?,?,?,?,?)',
        (uid,title,normalize(data.get('description')),normalize(data.get('location')),normalize(data.get('job_type')),normalize(data.get('salary')),normalize(data.get('experience_required')),skills))
    con.commit(); con.close(); return jsonify(ok=True,id=cur.lastrowid)

@app.post('/api/company/analyze-candidate')
def company_analyze_candidate():
    uid=request.form.get('user_id',type=int); f=request.files.get('portfolio')
    if not uid or not f: return jsonify(error='Choose a candidate resume and company account.'),400
    ext=Path(f.filename).suffix.lower()
    if ext not in ALLOWED: return jsonify(error='Supported: PDF, DOCX, TXT, CSV, PNG, JPG, JPEG'),400
    con=db(); company=con.execute("SELECT id FROM users WHERE id=? AND role='company'",(uid,)).fetchone()
    if not company: con.close(); return jsonify(error='Company account not found.'),404
    rows=con.execute('SELECT * FROM company_jobs WHERE company_user_id=?',(uid,)).fetchall(); con.close()
    if not rows: return jsonify(error='Add at least one company job before checking a candidate.'),400
    safe=secure_filename(f.filename); path=UPLOADS / f'{uuid.uuid4().hex}_{safe}'; f.save(path)
    try: text,ocr=extract_file(path); profile=extract_info(text)
    except Exception as e: return jsonify(error=f'Extraction failed: {e}'),500
    matches=[]
    for row in rows:
        job=dict(row); result=job_match(profile,job)
        matches.append({**job,**result})
    matches.sort(key=lambda x:(x['compatibility'],x['skill_score']),reverse=True)
    return jsonify(filename=f.filename,ocr_used=ocr,profile=profile,matches=matches)

@app.post('/api/analyze')
def analyze():
    user_id=request.form.get('user_id')
    f=request.files.get('portfolio')
    if not f: return jsonify(error='No portfolio file received.'),400
    ext=Path(f.filename).suffix.lower()
    if ext not in ALLOWED: return jsonify(error='Supported: PDF, DOCX, TXT, CSV, PNG, JPG, JPEG'),400
    safe=secure_filename(f.filename); path=UPLOADS / f'{uuid.uuid4().hex}_{safe}'; f.save(path)
    try: text,ocr=extract_file(path); profile=extract_info(text)
    except Exception as e: return jsonify(error=f'Extraction failed: {e}'),500
    con=db()
    valid_user_id = None
    if user_id:
        try:
            candidate_id = int(user_id)
            if con.execute('SELECT 1 FROM users WHERE id=?', (candidate_id,)).fetchone():
                valid_user_id = candidate_id
        except (TypeError, ValueError):
            valid_user_id = None
    cur=con.execute('INSERT INTO portfolios(user_id,filename,extracted_text,extracted_json,ocr_used) VALUES(?,?,?,?,?)',(valid_user_id,f.filename,text,json.dumps(profile),int(ocr)))
    portfolio_id=cur.lastrowid
    save_profile_sections(con, valid_user_id, profile)
    con.commit()
    jobs_rows=con.execute('SELECT * FROM jobs').fetchall()
    custom_rows=con.execute("SELECT -cj.id AS id,cj.title,cj.location,cj.required_skills,cp.company_name AS company,cj.description,cj.job_type,cj.salary,cj.experience_required FROM company_jobs cj JOIN company_profiles cp ON cp.user_id=cj.company_user_id").fetchall()
    con.close()
    recommendations=[]
    for row in list(jobs_rows)+list(custom_rows):
        job=dict(row)
        map_con=db()
        job['legacy_job_id']=ensure_legacy_job(map_con,job.get('company') or 'Company',job.get('title') or 'Job',job.get('description') or '',job.get('location') or '',job.get('job_type') or '',job.get('salary') or '',job.get('experience_required') or '')
        map_con.commit(); map_con.close()
        result=job_match(profile, job)
        recommendations.append({**job, **result})
    recommendations.sort(key=lambda x:(x['compatibility'], x['skill_score'], len(x['matched_skills'])), reverse=True)
    return jsonify(portfolio_id=portfolio_id,filename=f.filename,ocr_used=ocr,extracted_text=text[:12000],profile=profile,recommendations=recommendations[:3])

@app.get('/api/jobs')
def jobs():
    q=normalize(request.args.get('q','')).lower(); loc=normalize(request.args.get('location','')).lower()
    con=db(); rows=con.execute('SELECT * FROM jobs ORDER BY company,title').fetchall()
    custom=con.execute("SELECT -cj.id AS id,cj.title,cj.location,cj.required_skills,cp.company_name AS company,cj.description,cj.job_type,cj.salary,cj.experience_required FROM company_jobs cj JOIN company_profiles cp ON cp.user_id=cj.company_user_id ORDER BY cj.id DESC").fetchall()
    result=[]
    for r in list(rows)+list(custom):
        d=dict(r)
        hay=' '.join([str(d.get('company','')),str(d.get('title','')),str(d.get('location','')),str(d.get('required_skills',''))]).lower()
        if q and q not in hay: continue
        if loc and loc not in str(d.get('location') or '').lower(): continue
        d['legacy_job_id'] = ensure_legacy_job(con, d.get('company') or 'Company', d.get('title') or 'Job',
            d.get('description') or '', d.get('location') or '', d.get('job_type') or '',
            d.get('salary') or '', d.get('experience_required') or '')
        result.append(d)
    con.commit(); con.close()
    return jsonify(jobs=result)

def resolve_job_for_save_apply(con, job_id):
    """Accept either the legacy job_id or the ID returned by /api/jobs."""
    try:
        jid = int(job_id)
    except (TypeError, ValueError):
        return None
    row = con.execute('SELECT job_id FROM job WHERE job_id=?', (jid,)).fetchone()
    if row:
        return row['job_id']
    # Standard jobs are displayed with jobs.id; map them to the existing ER job table.
    row = con.execute('SELECT * FROM jobs WHERE id=?', (jid,)).fetchone()
    if row:
        d = dict(row)
        return ensure_legacy_job(con, d.get('company') or 'Company', d.get('title') or 'Job',
                                 d.get('description') or '', d.get('location') or '',
                                 d.get('job_type') or '', d.get('salary') or '',
                                 d.get('experience_required') or '')
    # Company-posted jobs use a negative display ID in the job list.
    if jid < 0:
        row = con.execute('''SELECT cj.*, cp.company_name AS company
                             FROM company_jobs cj JOIN company_profiles cp
                             ON cp.user_id=cj.company_user_id WHERE cj.id=?''', (-jid,)).fetchone()
        if row:
            d = dict(row)
            return ensure_legacy_job(con, d.get('company') or 'Company', d.get('title') or 'Job',
                                     d.get('description') or '', d.get('location') or '',
                                     d.get('job_type') or '', d.get('salary') or '',
                                     d.get('experience_required') or '')
    return None

def resolve_jobseeker(con, data):
    """Use the current ID first; email safely recovers stale browser sessions."""
    user_id = data.get('user_id')
    row = None
    if user_id:
        try:
            row = con.execute("SELECT id FROM users WHERE id=? AND role='jobseeker'", (int(user_id),)).fetchone()
        except (TypeError, ValueError):
            row = None
    if not row and data.get('email'):
        row = con.execute("SELECT id FROM users WHERE lower(email)=lower(?) AND role='jobseeker'",
                          (str(data.get('email')).strip(),)).fetchone()
    return row['id'] if row else None

@app.post('/api/save-job')
def save_job():
    data = request.get_json() or {}
    if not data.get('user_id') and not data.get('email'):
        return jsonify(error='Please sign in again, then save the job.'), 401
    if not data.get('job_id'):
        return jsonify(error='Choose a job before saving.'), 400
    con = db()
    user_id = resolve_jobseeker(con, data)
    job_id = resolve_job_for_save_apply(con, data.get('job_id'))
    if not user_id:
        con.close(); return jsonify(error='Your job-seeker account could not be found. Please sign out and sign in again.'), 404
    if not job_id:
        con.close(); return jsonify(error='This job is no longer available. Refresh the jobs list and try again.'), 404
    con.execute('INSERT OR IGNORE INTO saves(user_id,job_id) VALUES(?,?)', (user_id, job_id))
    con.commit(); con.close()
    return jsonify(ok=True, message='Job saved successfully.')

@app.post('/api/apply-job')
def apply_job():
    data = request.get_json() or {}
    if not data.get('user_id') and not data.get('email'):
        return jsonify(error='Please sign in again, then apply for the job.'), 401
    if not data.get('job_id'):
        return jsonify(error='Choose a job before applying.'), 400
    con = db()
    user_id = resolve_jobseeker(con, data)
    job_id = resolve_job_for_save_apply(con, data.get('job_id'))
    if not user_id:
        con.close(); return jsonify(error='Your job-seeker account could not be found. Please sign out and sign in again.'), 404
    if not job_id:
        con.close(); return jsonify(error='This job is no longer available. Refresh the jobs list and try again.'), 404
    existing = con.execute("SELECT application_id FROM application WHERE user_id=? AND job_id=? AND status='Applied'", (user_id, job_id)).fetchone()
    if existing:
        con.close(); return jsonify(ok=True, message='You have already applied for this job.')
    con.execute("INSERT INTO application(status,user_id,job_id) VALUES('Applied',?,?)", (user_id, job_id))
    con.commit(); con.close()
    return jsonify(ok=True, message='Your application has been recorded.')

@app.get('/api/my-jobs')
def my_jobs():
    user_id = request.args.get('user_id', type=int)
    if not user_id:
        return jsonify(saved=[], applied=[]), 400
    con = db()
    saved = con.execute('''SELECT j.job_id,j.job_title AS title,c.company_name AS company,j.location,s.saved_at
                           FROM saves s JOIN job j ON j.job_id=s.job_id JOIN company c ON c.company_id=j.company_id
                           WHERE s.user_id=? ORDER BY s.saved_at DESC''', (user_id,)).fetchall()
    applied = con.execute('''SELECT j.job_id,j.job_title AS title,c.company_name AS company,j.location,a.applied_date,a.status
                             FROM application a JOIN job j ON j.job_id=a.job_id JOIN company c ON c.company_id=j.company_id
                             WHERE a.user_id=? AND a.status='Applied' ORDER BY a.applied_date DESC''', (user_id,)).fetchall()
    con.close()
    return jsonify(saved=[dict(r) for r in saved], applied=[dict(r) for r in applied])

@app.post('/api/match')
def match():
    data=request.get_json() or {}; profile=data.get('profile') or {}; job=data.get('job') or {}; result=job_match(profile,job)
    user_id=data.get('user_id'); portfolio_id=data.get('portfolio_id'); job_id=job.get('id')
    if user_id and job_id and int(job_id) > 0:
        con=db()
        con.execute('INSERT INTO match_history(user_id,portfolio_id,job_id,compatibility,skill_score,matched_skills,missing_skills) VALUES(?,?,?,?,?,?,?)',
                    (user_id,portfolio_id,job_id,result['compatibility'],result['skill_score'],json.dumps(result['matched_skills']),json.dumps(result['missing_skills'])))
        legacy_job=con.execute('SELECT company,title FROM jobs WHERE id=?',(job_id,)).fetchone()
        er_job=None
        if legacy_job:
            er_job=con.execute('''SELECT j.job_id FROM job j JOIN company c ON c.company_id=j.company_id
                                  WHERE c.company_name=? AND j.job_title=?''',(legacy_job['company'],legacy_job['title'])).fetchone()
        if er_job:
            con.execute('INSERT INTO job_match(match_percentage,matched_skills,missing_skills,user_id,job_id,portfolio_id) VALUES(?,?,?,?,?,?)',
                        (result['compatibility'],json.dumps(result['matched_skills']),json.dumps(result['missing_skills']),user_id,er_job['job_id'],portfolio_id))
        con.commit(); con.close()
    return jsonify(result)

@app.get('/api/history')
def history():
    user_id=request.args.get('user_id', type=int)
    if not user_id: return jsonify(portfolios=[],matches=[])
    con=db()
    portfolios=con.execute('SELECT id,filename,ocr_used,created_at FROM portfolios WHERE user_id=? ORDER BY id DESC',(user_id,)).fetchall()
    matches=con.execute('''SELECT mh.id,mh.compatibility,mh.skill_score,mh.matched_skills,mh.missing_skills,mh.created_at,j.company,j.title,p.filename AS portfolio_filename FROM match_history mh JOIN jobs j ON j.id=mh.job_id LEFT JOIN portfolios p ON p.id=mh.portfolio_id WHERE mh.user_id=? ORDER BY mh.id DESC''',(user_id,)).fetchall()
    con.close()
    return jsonify(portfolios=[dict(r) for r in portfolios],matches=[{**dict(r),'matched_skills':json.loads(r['matched_skills'] or '[]'),'missing_skills':json.loads(r['missing_skills'] or '[]')} for r in matches])

@app.get('/api/health')
def health(): return jsonify(status='ok',service='PortfolioMatch backend',ocr='Tesseract + PyMuPDF',database='SQLite with ER tables')

init_db()

if __name__ == '__main__':
    print('PortfolioMatch backend running on http://127.0.0.1:5000')
    app.run(host='127.0.0.1',port=5000,debug=True)
