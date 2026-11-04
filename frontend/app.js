let user=null, profile=null, portfolioId=null, allJobs=[], lastMatch=null, registerMode=false;
function updateAuthRole(){const roleSelect=$('accountRole');document.body.classList.toggle('auth-company',roleSelect.value==='company');const company=roleSelect.value==='company';$('loginNameLabel').textContent=company?'Contact person name':'Full name';$('loginName').placeholder=company?'Recruiter / contact person name':'Enter your name';$('authHeading').textContent=registerMode?(company?'Create company account':'Create your account'):'Welcome back';$('authSubtitle').textContent=registerMode?(company?'Set up your company recruiter workspace.':'Create an account to find your best job matches.'):'Sign in to continue to your workspace.';}
function toggleRegister(){registerMode=!registerMode;document.body.classList.toggle('auth-register',registerMode);$('authSubmit').innerHTML=registerMode?'Create account <span>→</span>':'Sign in <span>→</span>'; $('authToggle').textContent=registerMode?'Back to sign in':'Create account';$('authMsg').textContent='';updateAuthRole();}
const roleSelect=document.getElementById('accountRole'); if(roleSelect) roleSelect.addEventListener('change',updateAuthRole);
const $=id=>document.getElementById(id);
function showPage(page){
  document.querySelectorAll('.page').forEach(x=>x.classList.add('hidden'));
  $(page).classList.remove('hidden');
  document.querySelectorAll('.nav').forEach(x=>x.classList.toggle('active',x.dataset.page===page));
  const titles={overview:'Overview',analyzer:'Portfolio Analyzer',jobs:'Job Matcher',myjobs:'My Jobs',insights:'Skill Insights'};
  $('pageTitle').textContent=titles[page];
  if(page==='jobs')loadJobs();
  if(page==='myjobs')loadMyJobs();
  if(page==='insights')renderInsights();
}
document.querySelectorAll('.nav').forEach(b=>b.onclick=()=>showPage(b.dataset.page));

async function auth(type){
  if(type==='login' && registerMode) type='register';
  const name=$('loginName').value.trim(), email=$('loginEmail').value.trim(), password=$('loginPassword').value, role=$('accountRole').value, company_name=$('companyName').value.trim();
  $('authMsg').textContent='';
  try{
    const r=await fetch('/api/'+(type==='login'?'login':'register'),{
      method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({name,email,password,role,company_name})
    });
    const d=await r.json();
    if(!r.ok){$('authMsg').textContent=d.error||'Unable to sign in. Please check your details.';return}
    user=d;localStorage.setItem('pm_user',JSON.stringify(user));startApp();
  }catch(e){$('authMsg').textContent='Cannot reach the backend. Start Flask and try again.'}
}
function startApp(){
  if(!user)return;
  $('login').classList.add('hidden');$('app').classList.remove('hidden');
  $('sideName').textContent=user.name;$('sideEmail').textContent=user.email;
  $('avatar').textContent=(user.name||'U')[0].toUpperCase();
  if(user.role==='company'){
    document.querySelectorAll('.page').forEach(x=>x.classList.add('hidden'));
    $('companyPanel').classList.remove('hidden');$('mainNav').classList.add('hidden');
    $('pageTitle').textContent='Employer workspace';$('pageTitle').parentElement.querySelector('.eyebrow').textContent='COMPANY MATCHING';
    loadCompanyProfile();loadCompanyJobs();
  }else{
    $('companyPanel').classList.add('hidden');$('mainNav').classList.remove('hidden');
    $('profileAvatar').textContent=(user.name||'?')[0].toUpperCase();
    showPage('overview');loadJobs();loadHistory();
  }
}
function logout(){localStorage.removeItem('pm_user');location.reload()}

async function loadJobs(){
  try{
    const r=await fetch('/api/jobs');const d=await r.json();allJobs=d.jobs||[];
    renderJobs(allJobs);$('ovJobs').textContent=allJobs.length;
  }catch(e){$('jobsList').innerHTML='<div class="result-card">Could not load jobs. Check that the backend is running.</div>'}
}
function jobCard(j, recommended=false){
  const required=(j.required_skills||'').split(',').map(s=>s.trim()).filter(Boolean);
  const score=Number(j.compatibility||0);
  const matched=j.matched_skills||[], missing=j.missing_skills||[];
  return `<article class="job ${recommended?'job-featured':''}">
    <div class="job-top"><div><span class="real">${recommended?'✦ RECOMMENDED MATCH':'OPPORTUNITY'}</span>
    <h3>${esc(j.title)}</h3><p>${esc(j.company)} · ${esc(j.location||'Location not specified')}</p></div>
    <span class="compat ${recommended?'compat-score':''}">${recommended?score+'%':'—'}</span></div>
    ${recommended?`<div class="match-meter"><i style="width:${Math.max(0,Math.min(100,score))}%"></i></div><p class="match-caption">${matched.length} of ${required.length} listed skills matched</p>`:''}
    <div class="chips">${required.map(s=>`<span class="chip">${esc(s)}</span>`).join('')}</div>
    ${recommended?`<div class="recommend-details"><div><b>Matched</b><p>${esc(matched.join(', ')||'No direct skill matches yet')}</p></div><div><b>To build</b><p>${esc(missing.slice(0,5).join(', ')||'No major skill gaps in this dataset')}</p></div></div>`:''}
    <button onclick="matchJob(${Number(j.id)})">${recommended?'View detailed comparison':'Compare portfolio'} →</button>
    <div class="job-actions"><button class="ghost" onclick="saveJob(${Number(j.legacy_job_id||0)})">Save Job</button><button onclick="applyJob(${Number(j.legacy_job_id||0)})">Apply Now</button></div>
  </article>`;
}
function renderJobs(jobs){$('jobsList').innerHTML=jobs.map(j=>jobCard(j,false)).join('')||'<div class="result-card">No jobs found. Try another search.</div>'}
function renderRecommendations(jobs){
  const el=$('recommendedJobs');
  if(!jobs||!jobs.length){el.innerHTML='<div class="recommend-empty">No recommendations yet. Upload a portfolio with readable skills and project details.</div>';return}
  el.innerHTML=jobs.slice(0,3).map(j=>jobCard(j,true)).join('');
}
function searchJobs(){
  const q=$('jobSearch').value.toLowerCase().trim(),l=$('locationSearch').value.toLowerCase().trim();
  renderJobs(allJobs.filter(j=>(!q||`${j.company} ${j.title} ${j.required_skills}`.toLowerCase().includes(q))&&(!l||(j.location||'').toLowerCase().includes(l))));
}
function clearJobs(){$('jobSearch').value='';$('locationSearch').value='';renderJobs(allJobs)}

async function saveJob(jobId){
  if(!user){alert('Please sign in first.');return}
  if(!jobId){alert('Job information is not ready. Reload the jobs list.');return}
  try{const r=await fetch('/api/save-job',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:user.user_id,email:user.email,job_id:jobId})});const d=await r.json();alert(d.message||d.error||'Could not save job.');if(r.ok)loadMyJobs();}catch(e){alert('Could not reach the backend.')}
}
async function applyJob(jobId){
  if(!user){alert('Please sign in first.');return}
  if(!jobId){alert('Job information is not ready. Reload the jobs list.');return}
  if(!confirm('Apply for this job? Your application will be recorded in My Jobs.'))return;
  try{const r=await fetch('/api/apply-job',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({user_id:user.user_id,email:user.email,job_id:jobId})});const d=await r.json();alert(d.message||d.error||'Could not submit application.');if(r.ok)loadMyJobs();}catch(e){alert('Could not reach the backend.')}
}
async function loadMyJobs(){
  if(!user)return;
  try{const r=await fetch('/api/my-jobs?user_id='+encodeURIComponent(user.user_id));const d=await r.json();
    $('savedJobsList').innerHTML=(d.saved||[]).map(j=>`<div class="line"><b>${esc(j.company)} — ${esc(j.title)}</b><p>${esc(j.location||'Location not specified')}</p><small>Saved ${esc(j.saved_at||'')}</small></div>`).join('')||'<div class="line">No saved jobs yet.</div>';
    $('appliedJobsList').innerHTML=(d.applied||[]).map(j=>`<div class="line"><b>${esc(j.company)} — ${esc(j.title)}</b><p>${esc(j.location||'Location not specified')}</p><small>Applied ${esc(j.applied_date||'')} · Status: ${esc(j.status||'Applied')}</small></div>`).join('')||'<div class="line">No applications yet.</div>';
  }catch(e){$('savedJobsList').textContent='Could not load saved jobs.'}
}

async function matchJob(id){
  if(!profile){alert('Analyze a portfolio first.');showPage('analyzer');return}
  const job=allJobs.find(x=>Number(x.id)===Number(id));
  if(!job){alert('Job record not found. Please reload the job list.');return}
  try{
    const r=await fetch('/api/match',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({profile,job,user_id:user?.user_id,portfolio_id:portfolioId})});
    const d=await r.json();if(!r.ok){alert(d.error||'Could not compare this job.');return}
    lastMatch={job,...d};$('ovScore').textContent=d.compatibility+'%';
    loadHistory();renderInsights();
    const insightButton=document.querySelector('[data-page="insights"]');
    if(insightButton)insightButton.textContent='Skill Insights';
    alert(`Compatibility: ${d.compatibility}%\nMatched: ${d.matched_skills.join(', ')||'None'}\nMissing: ${d.missing_skills.join(', ')||'None'}`);
  }catch(e){alert('Could not reach the backend. Please check that Flask is running.')}
}
$('portfolioFile').onchange=e=>$('fileName').textContent=e.target.files[0]?.name||'No file selected';

async function analyze(fileOverride=null){
  const file=fileOverride||$('portfolioFile').files[0];
  if(!file){$('analyzeMsg').textContent='Choose a portfolio first.';return}
  const fd=new FormData();fd.append('portfolio',file);if(user)fd.append('user_id',user.user_id);
  $('analyzeMsg').textContent='Extracting document text, improving image readability and matching jobs…';
  $('recommendedJobs').innerHTML='<div class="recommend-empty">Analyzing your portfolio and ranking job matches…</div>';
  try{
    const r=await fetch('/api/analyze',{method:'POST',body:fd});const d=await r.json();
    if(!r.ok){$('analyzeMsg').textContent=d.error||'Extraction failed.';return}
    profile=d.profile;portfolioId=d.portfolio_id||null;
    $('analyzeMsg').textContent=(d.ocr_used?'OCR was used for scanned/image content. ':'Text was extracted from the document. ')+
      'Review the extracted details below; OCR accuracy depends on image clarity.';
    renderProfile(d.profile);renderRecommendations(d.recommendations||[]);
    $('ovOCR').textContent=d.ocr_used?'Used':'Text';
    $('ovScore').textContent='—';
    loadHistory();
  }catch(e){$('analyzeMsg').textContent='Could not reach the backend. Start Flask and try again.'}
}
function renderProfile(p){
  $('candidateName').textContent=p.name||'Candidate profile';
  $('candidateContact').textContent=[p.email,p.phone].filter(Boolean).join(' · ')||'Contact details not detected';
  $('profileScore').textContent=p.portfolio_score+'%';$('scoreBar').style.width=p.portfolio_score+'%';
  $('countSkills').textContent=p.skills.length;$('countProjects').textContent=p.projects.length;
  $('countExp').textContent=p.experience.length;$('countEdu').textContent=p.education.length;
  $('ovSkills').textContent=p.skills.length;
  $('skills').innerHTML=p.skills.map(s=>`<span class="chip">${esc(s)}</span>`).join('')||'<span class="line">No skills detected. Check document quality or try a clearer scan.</span>';
  $('projects').innerHTML=p.projects.map(x=>`<div class="line">${esc(x)}</div>`).join('')||'<div class="line">No project evidence detected</div>';
  $('eduExp').innerHTML=[...p.education.map(x=>`<div class="line"><b>Education</b> — ${esc(x)}</div>`),...p.experience.map(x=>`<div class="line"><b>Experience</b> — ${esc(x)}</div>`),...p.certifications.map(x=>`<div class="line"><b>Certification / achievement</b> — ${esc(x)}</div>`)].join('')||'<div class="line">No education/experience section detected</div>';
}
async function loadSample(){
  const url=$('sampleSelect').value;if(!url)return;
  try{const r=await fetch(url);if(!r.ok)throw new Error('Sample not found');const blob=await r.blob();
    const file=new File([blob],url.split('/').pop(),{type:blob.type||'text/plain'});
    $('fileName').textContent=file.name;analyze(file);
  }catch(e){$('analyzeMsg').textContent='Could not load this sample. Please upload a file instead.'}
}
async function loadHistory(){
  if(!user)return;
  try{
    const r=await fetch('/api/history?user_id='+encodeURIComponent(user.user_id));if(!r.ok)return;
    const d=await r.json();
    $('portfolioHistory').innerHTML=d.portfolios.length?d.portfolios.map(x=>`<div class="line"><b>${esc(x.filename)}</b> · ${esc(x.created_at)}${x.ocr_used?' · OCR':''}</div>`).join(''):'<div class="line">No previous portfolios.</div>';
    $('matchHistory').innerHTML=d.matches.length?d.matches.map(x=>`<div class="line"><b>${esc(x.company)} — ${esc(x.title)}</b> · ${x.compatibility}%<br><small>Matched: ${esc(x.matched_skills.join(', ')||'None')} · Missing: ${esc(x.missing_skills.join(', ')||'None')}</small></div>`).join(''):'<div class="line">No previous job matches.</div>';
  }catch(e){}
}
function renderInsights(){
  const matched=$('matchingSkills'),missing=$('missingSkills');
  if(!lastMatch){matched.innerHTML='<span class="line">Choose a recommended job or compare a job to see matching skills.</span>';missing.innerHTML='<span class="line">Missing requirements will appear here.</span>';return}
  matched.innerHTML=lastMatch.matched_skills?.length?lastMatch.matched_skills.map(s=>`<span class="chip">${esc(s)}</span>`).join(''):'<span class="line">No matching skills</span>';
  missing.innerHTML=lastMatch.missing_skills?.length?lastMatch.missing_skills.map(s=>`<span class="chip missing">${esc(s)}</span>`).join(''):'<span class="line">No missing skills</span>';
}

async function loadCompanyProfile(){
  try{const r=await fetch('/api/company/profile?user_id='+encodeURIComponent(user.user_id));const d=await r.json();const p=d.profile||{};
    $('cpName').value=p.company_name||'';$('cpIndustry').value=p.industry||'';$('cpLocation').value=p.location||'';$('cpWebsite').value=p.website||'';$('cpContact').value=p.contact_person||user.name||'';$('cpDescription').value=p.description||'';
  }catch(e){}
}
async function saveCompanyProfile(e){
  e.preventDefault();const payload={user_id:user.user_id,company_name:$('cpName').value,industry:$('cpIndustry').value,location:$('cpLocation').value,website:$('cpWebsite').value,contact_person:$('cpContact').value,description:$('cpDescription').value};
  const r=await fetch('/api/company/profile',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();$('companyProfileMsg').textContent=r.ok?'Company details saved.':(d.error||'Could not save profile.');
}
async function createCompanyJob(e){
  e.preventDefault();const payload={user_id:user.user_id,title:$('cjTitle').value,required_skills:$('cjSkills').value,location:$('cjLocation').value,job_type:$('cjType').value,salary:$('cjSalary').value,experience_required:$('cjExperience').value,description:$('cjDescription').value};
  const r=await fetch('/api/company/jobs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});const d=await r.json();$('companyJobMsg').textContent=r.ok?'Job published successfully.':(d.error||'Could not publish job.');if(r.ok){e.target.reset();loadCompanyJobs();}
}
async function loadCompanyJobs(){
  try{const r=await fetch('/api/company/jobs?user_id='+encodeURIComponent(user.user_id));const d=await r.json();const el=$('companyJobs');el.innerHTML=(d.jobs||[]).map(j=>`<article class="job"><span class="real">YOUR OPENING</span><h3>${esc(j.title)}</h3><p>${esc(j.location||'Location not specified')} · ${esc(j.job_type||'Role')}</p><div class="chips">${esc(j.required_skills)}</div><p>${esc(j.description||'No description added')}</p></article>`).join('')||'<div class="recommend-empty">No jobs published yet. Add your first role above.</div>';}catch(e){$('companyJobs').textContent='Could not load company jobs.'}
}
$('candidateFile')?.addEventListener('change',e=>{$('candidateFileName').textContent=e.target.files[0]?.name||'PDF, DOCX or image'});
async function analyzeCompanyCandidate(e){
  e.preventDefault();const file=$('candidateFile').files[0];if(!file)return;const fd=new FormData();fd.append('portfolio',file);fd.append('user_id',user.user_id);$('companyCandidateResults').innerHTML='<p>Extracting candidate resume and comparing it with your jobs…</p>';
  try{const r=await fetch('/api/company/analyze-candidate',{method:'POST',body:fd});const d=await r.json();if(!r.ok){$('companyCandidateResults').innerHTML=`<p class="error-text">${esc(d.error||'Analysis failed')}</p>`;return}
    const p=d.profile||{};$('companyCandidateResults').innerHTML=`<div class="candidate-summary"><h3>${esc(p.name||'Candidate profile')}</h3><p>${esc([p.email,p.phone].filter(Boolean).join(' · ')||'Contact details not detected')}</p><div class="chips">${(p.skills||[]).map(s=>`<span class="chip">${esc(s)}</span>`).join('')}</div><p>${(p.projects||[]).length} projects · ${(p.education||[]).length} education records · ${(p.experience||[]).length} experience records</p></div><div class="jobs">${(d.matches||[]).map(j=>`<article class="job job-featured"><div class="job-top"><div><span class="real">SKILL MATCH</span><h3>${esc(j.title)}</h3><p>${esc(j.location||'Location not specified')}</p></div><span class="compat compat-score">${j.compatibility}%</span></div><div class="match-meter"><i style="width:${j.compatibility}%"></i></div><p><b>Matched:</b> ${esc((j.matched_skills||[]).join(', ')||'None')}</p><p><b>Missing:</b> ${esc((j.missing_skills||[]).join(', ')||'None')}</p></article>`).join('')}</div>`;
  }catch(err){$('companyCandidateResults').innerHTML='<p class="error-text">Could not reach the backend.</p>'}
}

function esc(s){return String(s??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
const saved=localStorage.getItem('pm_user');if(saved){try{user=JSON.parse(saved);startApp()}catch{}}
