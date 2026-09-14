#!/usr/bin/env python3
# -*- coding: utf-8 -*-
#pylint:disable=W0301
#  
#  Copyright 2018- William Martinez Bas <metfar@gmail.com>
#  
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#  
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#  
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#  
"""SUM build cache and active-session administration.""";
import datetime;
import json;
import os;
from pathlib import Path;
import shutil;
import signal;
import subprocess;
import time;
import uuid;


CACHE_ROOT_NAME="sumbuild";
PROFILE_META_NAME=".sumbuild-profile.json";
CURRENT_META_NAME="current.json";
SESSIONS_DIR_NAME="sessions";


def cache_root():
    return (Path.home()/".cache"/CACHE_ROOT_NAME).resolve();


def p4a_root():
    return cache_root()/"p4a";


def sources_root():
    return cache_root()/"p4a-sources";


def sessions_root():
    return cache_root()/SESSIONS_DIR_NAME;


def _now_iso():
    return datetime.datetime.now(datetime.timezone.utc).astimezone().isoformat(timespec="seconds");


def _read_json(path,default=None):
    try: return json.loads(Path(path).read_text(encoding="utf-8"));
    except (OSError,ValueError,TypeError): return {} if default is None else default;


def _atomic_json(path,data):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True);
    temp=path.with_name(path.name+".tmp-{}".format(os.getpid()));
    temp.write_text(json.dumps(data,indent=2,sort_keys=True)+"\n",encoding="utf-8");
    os.replace(str(temp),str(path));


def _dir_size(path):
    path=Path(path);
    if not path.exists(): return 0;
    du=shutil.which("du");
    if du:
        try:
            completed=subprocess.run([du,"-sb",str(path)],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,check=True);
            return int(completed.stdout.split(None,1)[0]);
        except (OSError,ValueError,subprocess.SubprocessError,IndexError): pass;
    total=0;
    for root,_dirs,files in os.walk(path,followlinks=False):
        for name in files:
            try: total+=(Path(root)/name).stat().st_size;
            except OSError: pass;
    return total;


def _human_size(value):
    value=float(max(0,int(value)));
    units=("B","K","M","G","T");
    index=0;
    while value >= 1024.0 and index < len(units)-1:
        value/=1024.0; index+=1;
    if index == 0: return "{}{}".format(int(value),units[index]);
    return "{:.1f}{}".format(value,units[index]);


def _mtime_iso(path):
    try: stamp=Path(path).stat().st_mtime;
    except OSError: return "-";
    return datetime.datetime.fromtimestamp(stamp).astimezone().strftime("%Y-%m-%d %H:%M");


def record_profile(path,metadata):
    path=Path(path).resolve(); path.mkdir(parents=True,exist_ok=True);
    previous=_read_json(path/PROFILE_META_NAME,{});
    data=dict(previous); data.update(dict(metadata or {}));
    data.setdefault("created_at",_now_iso()); data["last_used_at"]=_now_iso();
    data["path"]=str(path); data["profile_id"]=path.name;
    _atomic_json(path/PROFILE_META_NAME,data);
    current={"profile_id":path.name,"path":str(path),"updated_at":_now_iso()};
    _atomic_json(cache_root()/CURRENT_META_NAME,current);
    return data;


def current_profile_path():
    current=_read_json(cache_root()/CURRENT_META_NAME,{});
    value=str(current.get("path","") or "").strip();
    if not value: return None;
    path=Path(value).expanduser();
    return path.resolve() if path.exists() else None;


def _profile_rows():
    root=p4a_root(); root.mkdir(parents=True,exist_ok=True);
    current=current_profile_path(); rows=[];
    for path in sorted((item for item in root.iterdir() if item.is_dir()),key=lambda item:item.name):
        meta=_read_json(path/PROFILE_META_NAME,{});
        rows.append({
            "profile_id":path.name,
            "path":str(path.resolve()),
            "profile":str(meta.get("profile_revision") or meta.get("profile") or "unknown"),
            "size":_dir_size(path),
            "last_used":str(meta.get("last_used_at") or _mtime_iso(path)),
            "state":"current" if current is not None and path.resolve() == current else "old",
        });
    return rows;


def list_profiles(mode="all"):
    rows=_profile_rows();
    if mode == "current": rows=[row for row in rows if row["state"] == "current"];
    elif mode == "old": rows=[row for row in rows if row["state"] == "old"];
    elif mode != "all": raise ValueError("unknown profile list mode: {}".format(mode));
    return rows;


def format_profiles(mode="all"):
    rows=list_profiles(mode);
    header="CACHE ID          PROFILE                         SIZE      LAST USED         STATE";
    lines=[header];
    for row in rows:
        lines.append("{:<16}  {:<30}  {:>8}  {:<16}  {}".format(row["profile_id"][:16],row["profile"][:30],_human_size(row["size"]),str(row["last_used"])[:16],row["state"]));
    if not rows: lines.append("(none)");
    total=sum(row["size"] for row in _profile_rows());
    reclaim=sum(row["size"] for row in _profile_rows() if row["state"] == "old");
    lines.append("");
    lines.append("p4a cache:      {}".format(_human_size(total)));
    lines.append("source cache:   {}".format(_human_size(_dir_size(sources_root()))));
    lines.append("reclaimable:    {}".format(_human_size(reclaim)));
    return "\n".join(lines);


def _pid_alive(pid):
    try: os.kill(int(pid),0); return True;
    except (OSError,ValueError,TypeError): return False;


def _session_path(session_id):
    return sessions_root()/(str(session_id)+".json");


def register_session(project,target,backend,profile_path=None,command=None):
    sessions_root().mkdir(parents=True,exist_ok=True);
    session_id="bld-{}-{}".format(os.getpid(),uuid.uuid4().hex[:8]);
    data={
        "session_id":session_id,
        "owner_pid":os.getpid(),
        "builder_pid":None,
        "pgid":None,
        "project":str(project),
        "target":str(target),
        "backend":str(backend),
        "profile_path":str(profile_path) if profile_path is not None else None,
        "command":list(command or []),
        "started_at":_now_iso(),
    };
    _atomic_json(_session_path(session_id),data);
    return data;


def attach_builder(session,pid):
    data=dict(session); data["builder_pid"]=int(pid);
    try: data["pgid"]=int(os.getpgid(int(pid)));
    except OSError: data["pgid"]=int(pid);
    _atomic_json(_session_path(data["session_id"]),data);
    return data;


def finish_session(session):
    try: _session_path(session["session_id"]).unlink();
    except OSError: pass;


def active_sessions():
    root=sessions_root(); root.mkdir(parents=True,exist_ok=True); rows=[];
    for path in sorted(root.glob("*.json")):
        data=_read_json(path,{}); pid=data.get("builder_pid") or data.get("owner_pid");
        if not pid or not _pid_alive(pid):
            try: path.unlink();
            except OSError: pass;
            continue;
        rows.append(data);
    return rows;


def format_sessions():
    rows=active_sessions();
    lines=["SESSION                 PID       PROJECT                    TARGET   BACKEND  STARTED"];
    for row in rows:
        pid=row.get("builder_pid") or row.get("owner_pid") or "-";
        project=Path(str(row.get("project") or "-")).name;
        started=str(row.get("started_at") or "-");
        lines.append("{:<23} {:>8}  {:<26} {:<8} {:<8} {}".format(str(row.get("session_id","-"))[:23],str(pid),project[:26],str(row.get("target","-"))[:8],str(row.get("backend","-"))[:8],started[:19]));
    if not rows: lines.append("(none)");
    return "\n".join(lines);


def _session_uses_profile(session,path):
    raw=str(session.get("profile_path") or "").strip();
    if not raw: return False;
    try: return Path(raw).resolve() == Path(path).resolve();
    except OSError: return False;


def remove_profiles(mode="old"):
    rows=list_profiles("all"); sessions=active_sessions(); removed=[]; blocked=[];
    for row in rows:
        should=(mode == "all") or (mode == "old" and row["state"] == "old") or (mode == "current" and row["state"] == "current");
        if not should: continue;
        path=Path(row["path"]);
        users=[session for session in sessions if _session_uses_profile(session,path)];
        if users:
            blocked.append({"profile_id":row["profile_id"],"sessions":[item["session_id"] for item in users]}); continue;
        shutil.rmtree(path,ignore_errors=False); removed.append(row["profile_id"]);
    if mode in ("all","current"):
        current=cache_root()/CURRENT_META_NAME;
        if current.exists() and current_profile_path() is None:
            try: current.unlink();
            except OSError: pass;
    return {"removed":removed,"blocked":blocked};


def kill_session(identifier,timeout=3.0):
    identifier=str(identifier).strip(); sessions=active_sessions(); match=None;
    for session in sessions:
        values={str(session.get("session_id","")),str(session.get("builder_pid","")),str(session.get("owner_pid",""))};
        if identifier in values: match=session; break;
    if match is None: raise ValueError("active sumbuild session not found: {}".format(identifier));
    pid=int(match.get("builder_pid") or match.get("owner_pid")); pgid=int(match.get("pgid") or pid);
    try: os.killpg(pgid,signal.SIGTERM);
    except OSError:
        try: os.kill(pid,signal.SIGTERM);
        except OSError: pass;
    deadline=time.monotonic()+max(0.1,float(timeout));
    while time.monotonic() < deadline and _pid_alive(pid): time.sleep(0.05);
    if _pid_alive(pid):
        try: os.killpg(pgid,signal.SIGKILL);
        except OSError:
            try: os.kill(pid,signal.SIGKILL);
            except OSError: pass;
    return match;


def kill_all_sessions(timeout=3.0):
    killed=[];
    for session in list(active_sessions()):
        try:
            kill_session(session["session_id"],timeout=timeout); killed.append(session["session_id"]);
        except ValueError: pass;
    return killed;
