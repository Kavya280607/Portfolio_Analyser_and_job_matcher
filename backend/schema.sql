-- PortfolioMatch ER schema reference (SQLite)
-- The same tables are created automatically by backend/app.py -> init_db().
-- Existing lowercase legacy tables (users, portfolios, jobs, match_history) are retained for compatibility.
CREATE TABLE IF NOT EXISTS education (education_id INTEGER PRIMARY KEY AUTOINCREMENT, degree TEXT, institution TEXT, specialization TEXT, start_year TEXT, end_year TEXT, cgpa TEXT, user_id INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS certification (certification_id INTEGER PRIMARY KEY AUTOINCREMENT, certificate_name TEXT, issuing_organization TEXT, issue_date TEXT, expiry_date TEXT, certificate_link TEXT, user_id INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS project (project_id INTEGER PRIMARY KEY AUTOINCREMENT, project_name TEXT, description TEXT, start_date TEXT, end_date TEXT, project_link TEXT, user_id INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS experience (experience_id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT, job_role TEXT, start_date TEXT, end_date TEXT, description TEXT, user_id INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS achievement (achievement_id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, description TEXT, achievement_date TEXT, user_id INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS skill (skill_id INTEGER PRIMARY KEY AUTOINCREMENT, skill_name TEXT NOT NULL, skill_type TEXT, user_id INTEGER REFERENCES users(id));
CREATE TABLE IF NOT EXISTS company (company_id INTEGER PRIMARY KEY AUTOINCREMENT, company_name TEXT UNIQUE NOT NULL, industry TEXT, location TEXT, website TEXT, description TEXT);
CREATE TABLE IF NOT EXISTS job (job_id INTEGER PRIMARY KEY AUTOINCREMENT, job_title TEXT NOT NULL, description TEXT, location TEXT, job_type TEXT, salary TEXT, experience_required TEXT, company_id INTEGER REFERENCES company(company_id));
CREATE TABLE IF NOT EXISTS application (application_id INTEGER PRIMARY KEY AUTOINCREMENT, applied_date TEXT DEFAULT CURRENT_TIMESTAMP, status TEXT DEFAULT 'Saved', remarks TEXT, user_id INTEGER REFERENCES users(id), job_id INTEGER REFERENCES job(job_id));
CREATE TABLE IF NOT EXISTS saves (user_id INTEGER NOT NULL REFERENCES users(id), job_id INTEGER NOT NULL REFERENCES job(job_id), saved_at TEXT DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(user_id,job_id));
CREATE TABLE IF NOT EXISTS job_match (match_id INTEGER PRIMARY KEY AUTOINCREMENT, match_percentage INTEGER, matched_skills TEXT, missing_skills TEXT, match_date TEXT DEFAULT CURRENT_TIMESTAMP, user_id INTEGER REFERENCES users(id), job_id INTEGER REFERENCES job(job_id), portfolio_id INTEGER REFERENCES portfolios(id));
CREATE TABLE IF NOT EXISTS job_required_skill (job_id INTEGER NOT NULL REFERENCES job(job_id), skill_id INTEGER NOT NULL REFERENCES skill(skill_id), PRIMARY KEY(job_id,skill_id));
