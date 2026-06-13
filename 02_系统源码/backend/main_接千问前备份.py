import requests

# ===== DeepSeek .env 强制读取补丁 =====
from pathlib import Path as _YZTEnvPath
import os as _YZTOS

_yzt_env_paths = [
    _YZTEnvPath.cwd() / ".env",
    _YZTEnvPath(__file__).resolve().parent.parent / ".env",
]

for _env_file in _yzt_env_paths:
    if _env_file.exists():
        for _line in _env_file.read_text(encoding="utf-8").splitlines():
            _line = _line.strip()
            if not _line or _line.startswith("#") or "=" not in _line:
                continue
            _k, _v = _line.split("=", 1)
            _YZTOS.environ[_k.strip()] = _v.strip().strip('"').strip("'")
        print("✅ 已读取 DeepSeek 配置文件:", _env_file)
        print("✅ DEEPSEEK_API_KEY 已配置:", bool(_YZTOS.environ.get("DEEPSEEK_API_KEY")))
        break
else:
    print("⚠️ 未找到 .env 文件，DeepSeek 将使用本地模式")
# ===== DeepSeek .env 强制读取补丁结束 =====


# 自动读取 .env 文件
from pathlib import Path as _EnvPath
import os as _env_os

_env_file = _EnvPath(".env")
if _env_file.exists():
    for _line in _env_file.read_text(encoding="utf-8").splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _k, _v = _line.split("=", 1)
        _env_os.environ[_k.strip()] = _v.strip()


from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
import sqlite3, hashlib, hmac, secrets, time, json, os, shutil, uuid, csv, urllib.request
from typing import Optional

from ai_service.detector import analyze as ai_analyze

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
UPLOADS = DATA / "uploads"
REPORTS = DATA / "reports"
EXPORTS = DATA / "exports"
DB = DATA / "yunzhutong_v9.sqlite3"
FRONT = BASE / "frontend"
SECRET = os.environ.get("YZT_SECRET_KEY", "yunzhutong-v9-change-me")

app = FastAPI(title="云筑天瞳 V9一键启动正式软件包", version="9.0.0")

def now(): return int(time.time())
def dt(ts=None): return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts or now()))
def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c
def rd(r): return dict(r) if r else None

def hpw(pw):
    salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000).hex()
    return salt + "$" + dk
def vpw(pw, stored):
    try:
        salt, dk = stored.split("$", 1)
        ck = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000).hex()
        return hmac.compare_digest(dk, ck)
    except Exception:
        return False
def token(uid):
    payload = f"{uid}:{now()+86400*7}:{secrets.token_hex(8)}"
    sig = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return payload + ":" + sig
def check_token(t):
    try:
        uid, exp, nonce, sig = t.split(":", 3)
        payload = f"{uid}:{exp}:{nonce}"
        good = hmac.new(SECRET.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, good) or int(exp) < now(): return None
        return int(uid)
    except Exception:
        return None
def user_from_req(req: Request):
    t = req.cookies.get("yzt_token") or req.headers.get("X-YZT-Token")
    uid = check_token(t or "")
    if not uid: raise HTTPException(401, "请先登录")
    c = conn()
    u = c.execute("SELECT id,username,role,org,phone,created_at FROM users WHERE id=?", (uid,)).fetchone()
    c.close()
    if not u: raise HTTPException(401, "用户不存在")
    return rd(u)
def need_role(user, allowed):
    if user["role"] not in allowed:
        raise HTTPException(403, "当前账号无权限")
def log(uid, action, detail=""):
    c = conn()
    c.execute("INSERT INTO logs(user_id,action,detail,created_at) VALUES(?,?,?,?)", (uid, action, detail, now()))
    c.commit(); c.close()

def initdb():
    DATA.mkdir(exist_ok=True); UPLOADS.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True); EXPORTS.mkdir(exist_ok=True)
    c = conn()
    c.executescript("""
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL,
      org TEXT DEFAULT '',
      phone TEXT DEFAULT '',
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS projects(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      location TEXT DEFAULT '',
      category TEXT DEFAULT '',
      owner TEXT DEFAULT '',
      status TEXT DEFAULT '进行中',
      created_by INTEGER,
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS inspections(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id INTEGER NOT NULL,
      title TEXT NOT NULL,
      mode TEXT DEFAULT 'site',
      description TEXT DEFAULT '',
      image_path TEXT DEFAULT '',
      annotated_path TEXT DEFAULT '',
      ai_engine TEXT DEFAULT '',
      ai_json TEXT DEFAULT '',
      risk_level TEXT DEFAULT '待确认',
      created_by INTEGER,
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS risks(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id INTEGER NOT NULL,
      inspection_id INTEGER,
      risk_type TEXT NOT NULL,
      risk_level TEXT NOT NULL,
      confidence REAL DEFAULT 0,
      bbox TEXT DEFAULT '',
      status TEXT DEFAULT '待整改',
      responsible TEXT DEFAULT '',
      deadline TEXT DEFAULT '',
      advice TEXT DEFAULT '',
      before_path TEXT DEFAULT '',
      after_path TEXT DEFAULT '',
      review_result TEXT DEFAULT '',
      reviewer TEXT DEFAULT '',
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS reports(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      project_id INTEGER,
      file_path TEXT NOT NULL,
      created_by INTEGER,
      created_at INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS logs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      action TEXT NOT NULL,
      detail TEXT DEFAULT '',
      created_at INTEGER NOT NULL
    );
    """)
    if not c.execute("SELECT id FROM users WHERE username='admin'").fetchone():
        c.execute("INSERT INTO users(username,password_hash,role,org,phone,created_at) VALUES(?,?,?,?,?,?)",
                  ("admin", hpw("admin123456"), "超级管理员", "云筑天瞳", "", now()))
    if not c.execute("SELECT id FROM projects").fetchone():
        cur = c.execute("INSERT INTO projects(name,location,category,owner,created_by,created_at) VALUES(?,?,?,?,?,?)",
                        ("C村公共服务中心改造项目", "示范乡镇C村", "房建工程", "项目负责人", 1, now()))
        pid = cur.lastrowid
        c.execute("""INSERT INTO risks(project_id,risk_type,risk_level,confidence,status,responsible,deadline,advice,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (pid, "临边防护缺失", "高", .92, "待整改", "安全员", "48小时内", "立即设置防护栏杆、安全网和警示标识，并安排专人复查。", now(), now()))
    c.commit(); c.close()

@app.on_event("startup")
def startup(): initdb()

def save_upload(file: UploadFile, prefix="file"):
    suf = Path(file.filename or ".jpg").suffix.lower()
    if suf not in [".jpg",".jpeg",".png",".webp",".pdf",".dxf",".txt",".csv"]:
        suf = ".bin"
    name = f"{prefix}_{uuid.uuid4().hex}{suf}"
    path = UPLOADS / name
    with path.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return path

@app.get("/api/system")
async def system(req:Request):
    user_from_req(req)
    site_model = BASE / os.environ.get("YOLO_SITE_MODEL", "models/site_safety.pt")
    crack_model = BASE / os.environ.get("YOLO_CRACK_MODEL", "models/crack_detection.pt")
    try:
        import ultralytics
        yolo_installed = True
    except Exception:
        yolo_installed = False
    site_ready = yolo_installed and site_model.exists()
    crack_ready = yolo_installed and crack_model.exists()
    demo_mode = not site_ready
    return {
        "app_version": "V9 一键启动正式软件包",
        "demo_mode": demo_mode,
        "engine_label": "真实YOLO识别模式" if site_ready else "试点演示模式（本地图像分析）",
        "yolo_mode": os.environ.get("YOLO_MODE","auto"),
        "yolo_installed": yolo_installed,
        "site_model_exists": site_model.exists(),
        "crack_model_exists": crack_model.exists(),
        "deepseek_configured": bool(os.environ.get("DEEPSEEK_API_KEY")),
        "site_model": str(site_model),
        "crack_model": str(crack_model)
    }

@app.post("/api/register")
async def register(username:str=Form(...), password:str=Form(...), role:str=Form("安全员"), org:str=Form(""), phone:str=Form("")):
    if len(username)<3 or len(password)<6: raise HTTPException(400, "用户名至少3位，密码至少6位")
    c=conn()
    try:
        c.execute("INSERT INTO users(username,password_hash,role,org,phone,created_at) VALUES(?,?,?,?,?,?)",
                  (username,hpw(password),role,org,phone,now()))
        c.commit()
    except sqlite3.IntegrityError:
        raise HTTPException(400, "用户名已存在")
    finally:
        c.close()
    return {"ok":True}

@app.post("/api/login")
async def login(username:str=Form(...), password:str=Form(...)):
    c=conn(); u=c.execute("SELECT * FROM users WHERE username=?", (username,)).fetchone(); c.close()
    if not u or not vpw(password, u["password_hash"]): raise HTTPException(401, "用户名或密码错误")
    resp=JSONResponse({"ok":True,"user":{"id":u["id"],"username":u["username"],"role":u["role"],"org":u["org"],"phone":u["phone"]}})
    resp.set_cookie("yzt_token", token(u["id"]), httponly=True, samesite="lax", max_age=86400*7)
    log(u["id"], "登录系统", username)
    return resp

@app.post("/api/logout")
async def logout():
    r=JSONResponse({"ok":True}); r.delete_cookie("yzt_token"); return r

@app.get("/api/me")
async def me(req:Request): return user_from_req(req)

@app.get("/api/users")
async def users(req:Request):
    u=user_from_req(req); need_role(u, ["超级管理员"])
    c=conn(); rows=c.execute("SELECT id,username,role,org,phone,created_at FROM users ORDER BY id DESC").fetchall(); c.close()
    return [rd(x) for x in rows]

@app.post("/api/users/{uid}/role")
async def set_role(req:Request, uid:int, role:str=Form(...)):
    u=user_from_req(req); need_role(u, ["超级管理员"])
    c=conn(); c.execute("UPDATE users SET role=? WHERE id=?", (role,uid)); c.commit(); c.close()
    log(u["id"], "修改用户角色", f"user={uid}, role={role}")
    return {"ok":True}

@app.get("/api/dashboard")
async def dashboard(req:Request):
    user_from_req(req)
    c=conn()
    d={
        "projects":c.execute("SELECT COUNT(*) c FROM projects").fetchone()["c"],
        "risks":c.execute("SELECT COUNT(*) c FROM risks").fetchone()["c"],
        "high":c.execute("SELECT COUNT(*) c FROM risks WHERE risk_level='高'").fetchone()["c"],
        "pending":c.execute("SELECT COUNT(*) c FROM risks WHERE status NOT IN ('已完成','已归档')").fetchone()["c"],
        "today":c.execute("SELECT COUNT(*) c FROM inspections WHERE created_at>?", (now()-86400,)).fetchone()["c"]
    }
    c.close(); return d

@app.get("/api/projects")
async def projects(req:Request):
    user_from_req(req)
    c=conn(); rows=c.execute("SELECT * FROM projects ORDER BY id DESC").fetchall(); c.close()
    return [rd(x) for x in rows]

@app.post("/api/projects")
async def new_project(req:Request, name:str=Form(...), location:str=Form(""), category:str=Form("房建工程"), owner:str=Form("")):
    u=user_from_req(req)
    c=conn(); cur=c.execute("INSERT INTO projects(name,location,category,owner,created_by,created_at) VALUES(?,?,?,?,?,?)",
                            (name,location,category,owner,u["id"],now()))
    c.commit(); pid=cur.lastrowid; c.close()
    log(u["id"], "创建项目", name)
    return {"ok":True,"id":pid}

@app.post("/api/inspections")
async def new_inspection(req:Request, project_id:int=Form(...), title:str=Form(...), mode:str=Form("site"), description:str=Form(""), image:UploadFile=File(...)):
    u=user_from_req(req)
    path=save_upload(image, "inspection")
    analysis=ai_analyze(str(path), "crack" if mode=="crack" else "site")
    c=conn()
    cur=c.execute("""INSERT INTO inspections(project_id,title,mode,description,image_path,annotated_path,ai_engine,ai_json,risk_level,created_by,created_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?,?)""",
                  (project_id,title,mode,description,str(path.relative_to(BASE)),analysis["annotated_path"],analysis.get("engine",""),json.dumps(analysis,ensure_ascii=False),analysis["risk_level"],u["id"],now()))
    iid=cur.lastrowid
    for det in analysis.get("detections", []):
        c.execute("""INSERT INTO risks(project_id,inspection_id,risk_type,risk_level,confidence,bbox,status,advice,created_at,updated_at)
                     VALUES(?,?,?,?,?,?,?,?,?,?)""",
                  (project_id,iid,det.get("label","风险"),det.get("level","中"),float(det.get("confidence",0)),json.dumps(det.get("bbox",[]),ensure_ascii=False),
                   "待整改" if det.get("level") in ["高","中"] else "待确认",det.get("advice","请人工复核。"),now(),now()))
    c.commit(); c.close()
    log(u["id"], "上传巡检照片", f"{title} / {analysis.get('engine')}")
    return {"ok":True,"inspection_id":iid,"analysis":analysis}

@app.get("/api/inspections")
async def get_inspections(req:Request):
    user_from_req(req)
    c=conn(); rows=c.execute("""SELECT inspections.*, projects.name project_name FROM inspections
                              LEFT JOIN projects ON projects.id=inspections.project_id ORDER BY inspections.id DESC LIMIT 200""").fetchall(); c.close()
    out=[]
    for r in rows:
        d=rd(r)
        try: d["ai_json"]=json.loads(d.get("ai_json") or "{}")
        except Exception: pass
        out.append(d)
    return out

@app.get("/api/risks")
async def get_risks(req:Request):
    user_from_req(req)
    c=conn(); rows=c.execute("""SELECT risks.*, projects.name project_name FROM risks
                              LEFT JOIN projects ON projects.id=risks.project_id ORDER BY risks.id DESC LIMIT 300""").fetchall(); c.close()
    return [rd(x) for x in rows]

@app.post("/api/risks/{rid}/update")
async def update_risk(req:Request, rid:int, status:str=Form(...), responsible:str=Form(""), deadline:str=Form(""), review_result:str=Form(""), reviewer:str=Form("")):
    u=user_from_req(req)
    c=conn(); c.execute("""UPDATE risks SET status=?, responsible=?, deadline=?, review_result=?, reviewer=?, updated_at=? WHERE id=?""",
                        (status,responsible,deadline,review_result,reviewer,now(),rid))
    c.commit(); c.close()
    log(u["id"], "更新隐患单", f"#{rid} {status}")
    return {"ok":True}

@app.post("/api/risks/{rid}/photo")
async def risk_photo(req:Request, rid:int, kind:str=Form(...), photo:UploadFile=File(...)):
    u=user_from_req(req)
    path=save_upload(photo, f"risk_{rid}_{kind}")
    field = "after_path" if kind=="after" else "before_path"
    c=conn(); c.execute(f"UPDATE risks SET {field}=?, updated_at=? WHERE id=?", (str(path.relative_to(BASE)),now(),rid)); c.commit(); c.close()
    log(u["id"], "上传整改照片", f"#{rid} {kind}")
    return {"ok":True,"path":str(path.relative_to(BASE))}


@app.post("/api/ai-agent")
async def ai_agent(request: Request):
    body = await request.json()
    question = body.get("question") or body.get("message") or body.get("prompt") or ""

    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    model = os.environ.get("DEEPSEEK_MODEL", "deepseek-chat").strip()

    # 每次请求都强制读取 .env
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                key = line.split("=", 1)[1].strip().strip('"').strip("'")
            if line.startswith("DEEPSEEK_MODEL="):
                model = line.split("=", 1)[1].strip().strip('"').strip("'")

    local_answer = f"""【AI安全员本地建议】

针对：{question}

建议立即按以下流程处理：
1. 现场安全员确认隐患位置、影响范围和风险等级；
2. 高处作业、临边洞口、临时用电、脚手架、墙体裂缝等问题，先设置警戒和防护；
3. 系统内生成隐患单，明确责任人、整改期限和复查人；
4. 整改前后必须拍照上传，复查合格后归档；
5. 涉及结构安全或重大风险时，必须由监理或专业工程师复核确认。

说明：未配置 DEEPSEEK_API_KEY，当前为本地安全建议。"""

    if not key:
        return {"mode": "local", "answer": local_answer}

    try:
        r = requests.post(
            "https://api.deepseek.com/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json"
            },
            json={
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "你是云筑天瞳平台的AI安全员，面向乡村建设、房屋改造和中小型工地安全巡检。请用中文给出专业、简洁、可执行的隐患处理建议。必须强调AI仅作辅助，高风险隐患需安全员、监理或专业工程师复核。"
                    },
                    {
                        "role": "user",
                        "content": question
                    }
                ],
                "temperature": 0.3,
                "max_tokens": 800
            },
            timeout=30
        )

        if r.status_code != 200:
            return {
                "mode": "deepseek-error",
                "answer": "DeepSeek 调用失败，状态码：" + str(r.status_code) + "\\n" + r.text[:500]
            }

        data = r.json()
        answer = data["choices"][0]["message"]["content"]
        return {"mode": "deepseek", "answer": answer}

    except Exception as e:
        return {
            "mode": "deepseek-error",
            "answer": "DeepSeek 调用异常：" + str(e)
        }


@app.get("/api/report/{pid}")
async def report(req:Request, pid:int):
    u=user_from_req(req)
    c=conn()
    p=c.execute("SELECT * FROM projects WHERE id=?", (pid,)).fetchone()
    risks=c.execute("SELECT * FROM risks WHERE project_id=? ORDER BY id DESC", (pid,)).fetchall()
    inspections=c.execute("SELECT * FROM inspections WHERE project_id=? ORDER BY id DESC LIMIT 10", (pid,)).fetchall()
    c.close()
    if not p: raise HTTPException(404, "项目不存在")
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    fp=REPORTS / f"report_{pid}_{uuid.uuid4().hex[:8]}.pdf"
    can=canvas.Canvas(str(fp), pagesize=A4)
    W,H=A4
    can.setFont("STSong-Light",18); can.drawCentredString(W/2,H-25*mm,"云筑天瞳工地安全巡检与AI隐患识别报告")
    can.setFont("STSong-Light",10.5)
    y=H-42*mm
    lines=[
        f"项目名称：{p['name']}", f"项目地点：{p['location'] or '-'}", f"工程类型：{p['category'] or '-'}",
        f"负责人/单位：{p['owner'] or '-'}", f"生成时间：{dt()}", f"生成人：{u['username']}（{u['role']}）",
        "", "重要声明：本报告用于工地安全辅助管理。AI识别结果不能替代安全员、监理或专业工程师的最终判断。",
        "涉及重大隐患、结构安全、坍塌风险、严重裂缝等情况，必须由专业人员现场复核。",
        "", "AI巡检记录："
    ]
    for line in lines:
        can.drawString(20*mm,y,line[:82]); y-=7*mm
    for ins in inspections:
        if y<35*mm:
            can.showPage(); can.setFont("STSong-Light",10.5); y=H-22*mm
        can.drawString(22*mm,y,f"巡检#{ins['id']}：{ins['title']}｜引擎：{ins['ai_engine']}｜等级：{ins['risk_level']}｜时间：{dt(ins['created_at'])}")
        y-=7*mm
    can.drawString(20*mm,y,"隐患记录："); y-=7*mm
    for r in risks:
        if y<35*mm:
            can.showPage(); can.setFont("STSong-Light",10.5); y=H-22*mm
        can.drawString(22*mm,y,f"#{r['id']} {r['risk_type']}｜等级：{r['risk_level']}｜置信度：{round((r['confidence'] or 0)*100)}%｜状态：{r['status']}")
        y-=6*mm
        can.drawString(26*mm,y,f"建议：{(r['advice'] or '-')[:75]}")
        y-=6*mm
        if r["review_result"]:
            can.drawString(26*mm,y,f"复查：{r['review_result'][:75]}")
            y-=6*mm
        y-=2*mm
    can.save()
    c=conn(); c.execute("INSERT INTO reports(project_id,file_path,created_by,created_at) VALUES(?,?,?,?)",(pid,str(fp.relative_to(BASE)),u["id"],now())); c.commit(); c.close()
    log(u["id"], "导出PDF报告", p["name"])
    return FileResponse(fp, filename=f"云筑天瞳_{p['name']}_AI安全报告.pdf")

@app.get("/api/export/risks.csv")
async def export_risks(req:Request):
    u=user_from_req(req)
    fp=EXPORTS / f"risks_{uuid.uuid4().hex[:8]}.csv"
    c=conn(); rows=c.execute("""SELECT risks.id,projects.name project,risks.risk_type,risks.risk_level,risks.confidence,risks.status,risks.responsible,risks.deadline,risks.advice,risks.review_result,risks.created_at
                                FROM risks LEFT JOIN projects ON projects.id=risks.project_id ORDER BY risks.id DESC""").fetchall(); c.close()
    with fp.open("w", newline="", encoding="utf-8-sig") as f:
        writer=csv.writer(f); writer.writerow(["编号","项目","隐患类型","等级","置信度","状态","责任人","期限","建议","复查结论","创建时间"])
        for r in rows:
            writer.writerow([r["id"],r["project"],r["risk_type"],r["risk_level"],r["confidence"],r["status"],r["responsible"],r["deadline"],r["advice"],r["review_result"],dt(r["created_at"])])
    log(u["id"], "导出隐患CSV", "")
    return FileResponse(fp, filename="云筑天瞳_隐患台账.csv")

@app.get("/api/logs")
async def logs(req:Request):
    u=user_from_req(req); need_role(u, ["超级管理员","政府监管人员","项目负责人"])
    c=conn(); rows=c.execute("""SELECT logs.*, users.username FROM logs LEFT JOIN users ON users.id=logs.user_id ORDER BY logs.id DESC LIMIT 300""").fetchall(); c.close()
    return [rd(x) for x in rows]

app.mount("/data", StaticFiles(directory=str(DATA)), name="data")
app.mount("/", StaticFiles(directory=str(FRONT), html=True), name="frontend")
