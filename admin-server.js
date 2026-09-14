#!/usr/bin/env node
/**
 * 트래커 관리 서버 — 공개 사이트(GitHub Pages)의 ➕추가 / 삭제 버튼이 호출한다.
 *  POST /api/auth             키 확인
 *  POST /api/trackers         {spec:"푸꾸옥, 나트랑 - 메오키친", direct:true} → 추가 + 첫 수집 + 배포
 *  POST /api/trackers/delete  {id}                                          → 삭제(기록은 보관) + 배포
 *  GET  /api/status           진행 중인 첫 수집
 * 인증: X-Admin-Key 헤더. 키 파일은 공개 저장소 밖(~/.openclaw/tracker-admin.key)에 둔다.
 */
const http = require("http");
const fs = require("fs");
const os = require("os");
const path = require("path");
const crypto = require("crypto");
const { execFile } = require("child_process");

const BASE = __dirname;
const PORT = Number(process.env.PORT || 4500);
const PY = "/opt/homebrew/bin/python3";
const KEY_FILE = path.join(os.homedir(), ".openclaw", "tracker-admin.key");
const ORIGINS = new Set(["https://alohang1985.github.io", `http://localhost:${PORT}`, `http://127.0.0.1:${PORT}`]);
const MIME = { ".html": "text/html; charset=utf-8", ".json": "application/json; charset=utf-8",
  ".js": "text/javascript", ".css": "text/css", ".png": "image/png", ".svg": "image/svg+xml" };
const jobs = new Map();

const log = (...a) => console.log(new Date().toISOString().slice(0, 19), ...a);

function cors(origin) {
  if (!ORIGINS.has(origin)) return {};
  return { "Access-Control-Allow-Origin": origin, "Vary": "Origin",
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,X-Admin-Key", "Access-Control-Max-Age": "600" };
}
function send(res, code, obj, origin) {
  res.writeHead(code, { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store", ...cors(origin) });
  res.end(JSON.stringify(obj));
}
function authed(req) {
  let key = "";
  try { key = fs.readFileSync(KEY_FILE, "utf-8").trim(); } catch {}
  const a = Buffer.from(key), b = Buffer.from(String(req.headers["x-admin-key"] || ""));
  return a.length > 0 && a.length === b.length && crypto.timingSafeEqual(a, b);
}
function readBody(req) {
  return new Promise((ok, fail) => {
    let s = "";
    req.on("data", c => { s += c; if (s.length > 1e5) req.destroy(); });
    req.on("end", () => { try { ok(JSON.parse(s || "{}")); } catch (e) { fail(e); } });
  });
}
function py(args, timeout = 60000) {
  return new Promise(ok => execFile(PY, args, { cwd: BASE, timeout, maxBuffer: 4 * 1024 * 1024 }, (err, stdout, stderr) => {
    let json = null;
    try { json = JSON.parse(String(stdout).trim().split("\n").pop()); } catch {}
    ok({ err, json, stderr: String(stderr).slice(-600) });
  }));
}
function publish() {
  execFile("bash", [path.join(BASE, "publish.sh")], { cwd: BASE, timeout: 300000 },
    (e, o, s) => log("배포:", String(o || s || e || "").trim()));
}
function firstCrawl(t) {
  const job = { id: t.id, label: t.label, state: "수집 중", started: Date.now() };
  jobs.set(t.id, job);
  execFile(PY, [path.join(BASE, "tracker_engine.py"), t.id, "--no-notify"], { cwd: BASE, timeout: 15 * 60000, maxBuffer: 8e6 },
    (err, _o, stderr) => {
      job.state = err ? "실패" : "완료";
      job.finished = Date.now();
      job.message = String(stderr).split("\n").filter(l => l.includes("[engine]")).slice(-2).join(" ");
      log("첫 수집", t.id, job.state, job.message);
      setTimeout(() => jobs.delete(t.id), 30 * 60000);
    });
}

const server = http.createServer(async (req, res) => {
  const origin = req.headers.origin || "";
  const url = new URL(req.url, "http://localhost");

  if (req.method === "OPTIONS") { res.writeHead(204, cors(origin)); return res.end(); }
  if (url.pathname === "/api/status") return send(res, 200, { ok: true, jobs: [...jobs.values()] }, origin);

  if (url.pathname.startsWith("/api/")) {
    if (req.method !== "POST") return send(res, 405, { ok: false, error: "POST만 가능합니다" }, origin);
    if (!authed(req)) return send(res, 401, { ok: false, error: "관리자 키가 틀렸습니다" }, origin);
    let body;
    try { body = await readBody(req); } catch { return send(res, 400, { ok: false, error: "잘못된 요청" }, origin); }

    if (url.pathname === "/api/auth") return send(res, 200, { ok: true }, origin);

    if (url.pathname === "/api/trackers") {
      const r = await py([path.join(BASE, "admin_cli.py"), "add", "--spec", String(body.spec || ""),
        "--direct", body.direct === false ? "0" : "1"]);
      if (!r.json || !r.json.ok)
        return send(res, 400, { ok: false, error: (r.json && r.json.error) || "추가 실패", detail: r.stderr }, origin);
      log("추가", r.json.tracker.id, r.json.tracker.label);
      publish();              // 탭이 사이트에 먼저 보이게
      firstCrawl(r.json.tracker); // 수집이 끝나면 엔진이 다시 배포
      return send(res, 200, { ok: true, tracker: r.json.tracker }, origin);
    }

    if (url.pathname === "/api/trackers/delete") {
      const r = await py([path.join(BASE, "admin_cli.py"), "delete", String(body.id || "")]);
      if (!r.json || !r.json.ok)
        return send(res, 400, { ok: false, error: (r.json && r.json.error) || "삭제 실패" }, origin);
      log("삭제", body.id);
      publish();
      return send(res, 200, { ok: true, tracker: r.json.tracker }, origin);
    }
    return send(res, 404, { ok: false, error: "없는 API" }, origin);
  }

  // 로컬(맥)에서 열면 사이트를 그대로 보여준다
  let p = decodeURIComponent(url.pathname);
  if (p === "/") p = "/index.html";
  const fp = path.normalize(path.join(BASE, p));
  const rel = path.relative(BASE, fp);
  if (rel.startsWith("..") || /(^|\/)\.|\.py$|\.log$|\.key$|\.sh$/.test(rel)) { res.writeHead(403); return res.end("forbidden"); }
  fs.readFile(fp, (err, data) => {
    if (err) { res.writeHead(404); return res.end("Not found"); }
    res.writeHead(200, { "Content-Type": MIME[path.extname(fp)] || "application/octet-stream", "Cache-Control": "no-store" });
    res.end(data);
  });
});

server.listen(PORT, "127.0.0.1", () => log(`트래커 관리 서버 http://127.0.0.1:${PORT}`));
