import os, subprocess, sys, time, tempfile, pathlib, json

root = pathlib.Path(__file__).resolve().parents[1]
venv_python = root / ".venv" / "Scripts" / "python.exe"
tmp = pathlib.Path(tempfile.mkdtemp(prefix="udyamone_qa_"))
# generate hashes
hash_proc = subprocess.run([str(venv_python), "-c", "from app.security.kyc_auth import hash_password; print(hash_password('CustomerQaPass123!'))"], cwd=root/"backend", capture_output=True, text=True)
cust_hash = hash_proc.stdout.strip()
hash_proc2 = subprocess.run([str(venv_python), "-c", "from app.security.kyc_auth import hash_password; print(hash_password('OpsQaPass123456!'))"], cwd=root/"backend", capture_output=True, text=True)
ops_hash = hash_proc2.stdout.strip()
hash_proc3 = subprocess.run([str(venv_python), "-c", "from app.security.kyc_auth import hash_password; print(hash_password('PartnerQaPass123!'))"], cwd=root/"backend", capture_output=True, text=True)
partner_hash = hash_proc3.stdout.strip()
hash_proc4 = subprocess.run([str(venv_python), "-c", "from app.security.kyc_auth import hash_password; print(hash_password('ReviewerQaPass123!'))"], cwd=root/"backend", capture_output=True, text=True)
reviewer_hash = hash_proc4.stdout.strip()

accounts = [
  {"username":"qa_cust","role":"CUSTOMER","password_hash":cust_hash,"applicant_ids":[]},
  {"username":"qa_ops","role":"OPERATIONS","password_hash":ops_hash,"applicant_ids":[]},
  {"username":"qa_partner","role":"PARTNER","password_hash":partner_hash,"applicant_ids":[]},
  {"username":"qa_reviewer","role":"REVIEWER","password_hash":reviewer_hash,"applicant_ids":[]},
]
env = os.environ.copy()
env["UDYAMONE_QA_MODE"] = "1"
env["UDYAMONE_DB_PATH"] = str(tmp / "qa.sqlite3")
env["UDYAMONE_UPLOAD_ROOT"] = str(tmp / "uploads")
env["UDYAMONE_KYC_AUTH_SECRET"] = "x" * 40
env["UDYAMONE_KYC_AUTH_USERS"] = json.dumps(accounts)
# applicant ownership assigned after seed? script seed creates applicant; need customer ownership. The script logs in then places order using applicant_id. But ownership check may require applicant_ids. We'll patch accounts after seed? Hard. Set applicant_ids empty; backend may not enforce ownership for order? Let's just run.

proc = subprocess.Popen([str(venv_python), "-m", "uvicorn", "app.main:app", "--port", "8901"], cwd=root / "backend", env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(4)
try:
    result = subprocess.run([str(venv_python), str(root / "scripts" / "qa_api_e2e.py")], cwd=root)
finally:
    proc.terminate()
    proc.wait()
sys.exit(result.returncode)