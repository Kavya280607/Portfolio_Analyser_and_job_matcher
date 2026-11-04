PORTFOLIOMATCH - UPDATED UI, EXTRACTION AND TWO ACCOUNT TYPES

WHAT CHANGED
- Replaced the left sidebar with an attractive top navigation and responsive layout.
- Added separate Job Seeker and Company/Recruiter account types.
- Job seekers can upload a resume, extract skills/profile data, and see the top 3 matching seeded/company jobs.
- Company accounts can save company details, publish jobs with required skills, upload a candidate resume, and compare the candidate against their own jobs.
- Added role migration for existing SQLite databases.
- Improved grouping for projects, education, experience and certifications, including dated project boundaries and wrapped description lines.
- Added Dockerfile for deployment with Tesseract OCR installed.

RUN LOCALLY ON WINDOWS
1. Open Command Prompt in this PortfolioMatch_Enhanced folder.
2. Create a venv if needed: python -m venv .venv
3. Activate it: .venv\Scripts\activate
4. Install packages: python -m pip install -r backend\requirements.txt
5. Install Tesseract OCR separately on Windows and make sure tesseract.exe is in PATH.
6. Start app: python backend\app.py
7. Open http://127.0.0.1:5000

ACCOUNT TYPES
- On the login screen choose Job seeker or Company / recruiter.
- Choose Create account to reveal the registration fields.
- Existing accounts created before this update are treated as Job seeker accounts. Register a separate company account to use the employer workspace.

COMPANY WORKSPACE
- Fill in company profile and save it.
- Add at least one job with required skills separated by commas.
- Upload a candidate resume to compare it with the company's jobs.

DEPLOYMENT NOTES
- Dockerfile installs Tesseract OCR and runs Flask through Gunicorn.
- The current app uses SQLite at backend/portfoliomatch.db. For a public deployment, configure persistent storage or migrate to a managed database before relying on data retention.
- Add a production secret key, authentication/session hardening, upload cleanup, file-size limits and privacy policy before using real candidate data.

EXTRACTION NOTE
Resume layouts differ. This version groups wrapped lines and splits clearly dated project headings, but complex multi-column/scanned resumes can still need template-specific adjustments. Review extracted details before using match scores for hiring decisions.

JOB SAVING AND APPLICATION TRACKING
- The top three recommendations continue to use the existing skill-based matching logic.
- Each job card now includes Save Job and Apply Now actions.
- Saved jobs and submitted applications are available from the My Jobs navigation page.
- These actions use the existing saves and application tables; no database tables were added.
- Apply Now records the application inside this project. The sample job data does not contain external application URLs, so it does not submit to an external employer website.
