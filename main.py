from datetime import datetime
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
import sqlite3, jwt

app = FastAPI(title="RooTX Engine Backend")
DB_FILE = "rootx_persistence.db"
SECRET_KEY = "ETBV_LAYER_ZERO_KEY_STUB"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("CREATE TABLE IF NOT EXISTS assessments (assessment_id TEXT PRIMARY KEY, project_name TEXT NOT NULL, status TEXT NOT NULL, assigned_member_id TEXT NOT NULL, last_updated TEXT NOT NULL)")
        c.execute("CREATE TABLE IF NOT EXISTS audit_logs (log_id INTEGER PRIMARY KEY AUTOINCREMENT, assessment_id TEXT NOT NULL, modified_by TEXT NOT NULL, timestamp TEXT NOT NULL, previous_state TEXT NOT NULL, new_state TEXT NOT NULL)")
        conn.commit()
init_db()

class AssessmentPayload(BaseModel):
    assessment_id: str
    project_name: str
    status: str
    assigned_member_id: str

def verify_reviewer_identity(token: str = Depends(oauth2_scheme)) -> str:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload.get("sub", "")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Could not validate reviewer signature credential")

def validate_staffing_allocation(member_id: str, exclude_id: Optional[str] = None):
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        if exclude_id:
            c.execute("SELECT assessment_id FROM assessments WHERE assigned_member_id = ? AND assessment_id != ?", (member_id, exclude_id))
        else:
            c.execute("SELECT assessment_id FROM assessments WHERE assigned_member_id = ?", (member_id,))
        conflict = c.fetchone()
        if conflict:
            raise HTTPException(status_code=400, detail=f"Staffing Conflict: Member {member_id} is already allocated.")

@app.get("/api/assessments")
def list_assessments():
    with sqlite3.connect(DB_FILE) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.cursor().execute("SELECT * FROM assessments").fetchall()]

@app.post("/api/assessments/update")
def update_assessment(payload: AssessmentPayload, reviewer: str = Depends(verify_reviewer_identity)):
    validate_staffing_allocation(payload.assigned_member_id, exclude_id=payload.assessment_id)
    timestamp = datetime.utcnow().isoformat()
    with sqlite3.connect(DB_FILE) as conn:
        c = conn.cursor()
        c.execute("SELECT status, assigned_member_id FROM assessments WHERE assessment_id = ?", (payload.assessment_id,))
        row = c.fetchone()
        prev = f"Status: {row[0]}, Member: {row[1]}" if row else "NULL_INITIAL"
        new_st = f"Status: {payload.status}, Member: {payload.assigned_member_id}"
        c.execute("INSERT INTO assessments VALUES (?, ?, ?, ?, ?) ON CONFLICT(assessment_id) DO UPDATE SET status=excluded.status, assigned_member_id=excluded.assigned_member_id, last_updated=excluded.last_updated", (payload.assessment_id, payload.project_name, payload.status, payload.assigned_member_id, timestamp))
        c.execute("INSERT INTO audit_logs (assessment_id, modified_by, timestamp, previous_state, new_state) VALUES (?, ?, ?, ?, ?)", (payload.assessment_id, reviewer, timestamp, prev, new_st))
        conn.commit()
    return {"status": "success", "logged_at": timestamp}
