#!/usr/bin/env node
/**
 * 로컬 관리자 서버.
 * - 대시보드(index.html, data/, trackers.json)를 그대로 서빙
 * - POST /api/add-tracker {label, brand, queries} → add_tracker.py 실행 (추가+수집+배포)
 * 공개 URL이 아닌 내 맥(localhost)에서만 동작. 실행: node admin-server.js  →  http://localhost:4500
 */
const http = require("http");
const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");

const BASE = __dirname;
const PORT = process.env.PORT || 4500;
const MIME = { ".html":"text/html; charset=utf-8", ".json":"application/json; charset=utf-8",
  ".js":"text/javascript", ".css":"text/css", ".png":"image/png", ".svg":"image/svg+xml" };

function serveFile(res, fp) {
  fs.readFile(fp, (err, data) => {
    if (err) { res.writeHead(404); res.end("Not found"); return; }
    res.writeHead(200, { "Content-Type": MIME[path.extname(fp)] || "application/octet-stream",
      "Cache-Control": "no-store" });
    res.end(data);
  });
}

const server = http.createServer((req, res) => {
  // API: 트래커 추가
  if (req.method === "POST" && req.url === "/api/add-tracker") {
    let body = "";
    req.on("data", c => body += c);
    req.on("end", () => {
      let p; try { p = JSON.parse(body); } catch { res.writeHead(400); return res.end('{"error":"bad json"}'); }
      const { label, brand, queries } = p || {};
      if (!label || !queries) { res.writeHead(400); return res.end('{"error":"label/queries 필요"}'); }
      execFile("python3", [path.join(BASE, "add_tracker.py"), String(label), String(brand || label), String(queries)],
        { timeout: 180000 }, (err, stdout, stderr) => {
          if (err) { res.writeHead(500, {"Content-Type":"application/json"});
            return res.end(JSON.stringify({ error: "실행 실패", detail: (stderr||err.message).slice(-400) })); }
          res.writeHead(200, {"Content-Type":"application/json"});
          res.end(JSON.stringify({ ok: true, message: (stdout||"").trim().split("\n").slice(-2).join(" ") }));
        });
    });
    return;
  }
  // 정적 파일
  let url = decodeURIComponent(req.url.split("?")[0]);
  if (url === "/") url = "/index.html";
  const fp = path.normalize(path.join(BASE, url));
  if (!fp.startsWith(BASE)) { res.writeHead(403); return res.end("forbidden"); }
  serveFile(res, fp);
});

server.listen(PORT, "127.0.0.1", () => {
  console.log(`✅ 메오키친 아카이브 관리자 서버: http://localhost:${PORT}`);
  console.log(`   (여기서 "➕ 추가" 버튼이 실제로 동작합니다)`);
});
