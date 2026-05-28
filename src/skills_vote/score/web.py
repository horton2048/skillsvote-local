from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from skills_vote.score.assess import assess_skill
from skills_vote.score.environment import LocalEnvironment, detect_environment
from skills_vote.score.fetch import SkillFetchError
from skills_vote.score.model import UserProfile
from skills_vote.score.usage_scan import scan_user_profile

# TailGrids-styled single page (Tailwind via Play CDN, no build step).
_PAGE = """<!doctype html><html lang="zh-CN"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>SkillsVote · 该不该装</title>
<script src="https://cdn.tailwindcss.com"></script>
<script>
tailwind.config={theme:{extend:{
  colors:{primary:'#3056D3',dark:'#1C2434','body-color':'#637381',stroke:'#E7E7E7',
    'blue-light':'#EAF0FF','green-light':'#E1F8EF','amber-light':'#FFF4E5'},
  boxShadow:{card:'0 8px 40px rgba(15,23,42,.06)'},
  fontFamily:{sans:['Inter','-apple-system','Segoe UI','Microsoft YaHei','sans-serif']}}}}
</script></head>
<body class="bg-gray-50 font-sans text-dark antialiased">
<div class="mx-auto max-w-3xl px-5 py-12 sm:py-16">

  <div class="mb-9 text-center">
    <span class="mb-4 inline-block rounded-full bg-blue-light px-4 py-1 text-sm font-medium text-primary">
      SkillsVote · 个性化评估</span>
    <h1 class="text-3xl font-bold leading-tight sm:text-[40px]">这个 skill，<span class="text-primary">该不该装？</span></h1>
    <p class="mx-auto mt-3 max-w-xl text-base text-body-color">
      粘一个 skill 链接（GitHub / skills.vote）。基于你本地的使用习惯与环境，给出只属于你的评分和安装建议。</p>
  </div>

  <div class="rounded-xl border border-stroke bg-white p-2 shadow-card sm:flex sm:items-center sm:gap-2">
    <input id="link" autofocus placeholder="https://github.com/owner/repo/tree/main/path-to-skill"
      class="w-full rounded-lg bg-transparent px-4 py-3 text-base outline-none placeholder:text-body-color/70">
    <button id="go"
      class="mt-2 inline-flex w-full items-center justify-center rounded-lg bg-primary px-8 py-3 text-base font-medium text-white transition hover:bg-opacity-90 disabled:opacity-50 sm:mt-0 sm:w-auto">
      评估</button>
  </div>
  <p class="mt-3 px-1 text-sm text-body-color">
    例：github.com/MemTensor/skills-vote/tree/main/integration/skills/skills-vote</p>

  <div id="spin" class="mt-6 hidden items-center gap-3 rounded-xl border border-stroke bg-white px-5 py-4 text-sm text-body-color">
    <span class="h-4 w-4 animate-spin rounded-full border-2 border-stroke border-t-primary"></span>
    正在抓取并评估…</div>
  <div id="err" class="mt-6 hidden rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700"></div>

  <div id="card" class="mt-6 hidden rounded-2xl border border-stroke bg-white p-7 shadow-card sm:p-8">
    <div class="flex items-start justify-between gap-4">
      <div class="min-w-0">
        <h2 id="sname" class="truncate text-xl font-semibold"></h2>
        <span id="verdict" class="mt-2 inline-flex rounded-full px-3 py-1 text-sm font-semibold"></span>
      </div>
      <div class="shrink-0 text-right">
        <div id="sval" class="text-[44px] font-extrabold leading-none"></div>
        <div class="mt-1 text-xs text-body-color">综合价值分</div>
      </div>
    </div>
    <p id="reason" class="mt-4 text-sm leading-relaxed text-body-color"></p>
    <div id="dims" class="mt-6 grid grid-cols-2 gap-x-5 gap-y-4 sm:grid-cols-5"></div>
    <div id="env" class="mt-6 flex flex-wrap items-center gap-2 rounded-xl bg-gray-50 px-4 py-3 text-sm"></div>
    <div class="mt-7 flex items-center justify-between">
      <h3 class="text-sm font-semibold">一键安装提示词 · 粘给你的 Claude Code</h3>
      <button id="copy" class="inline-flex items-center rounded-md bg-dark px-4 py-2 text-xs font-medium text-white transition hover:bg-opacity-90">复制</button>
    </div>
    <pre id="prompt" class="mt-3 max-h-80 overflow-auto whitespace-pre-wrap break-words rounded-xl bg-dark p-5 text-[12.5px] leading-relaxed text-gray-100"></pre>
  </div>

  <p class="mt-10 text-center text-xs text-body-color/80">
    评分维度：相关 · 需求 · 时效 · 缺口 · 适配 ｜ 数据全部来自本地，未上传</p>
</div>

<script>
const $=id=>document.getElementById(id);
const DIMS=[["relevance","相关"],["demand","需求"],["recency","时效"],["gap","缺口"],["fit","适配"]];
const VMAP={install:["bg-green-light text-green-700","建议安装"],
  optional:["bg-blue-light text-primary","可装可不装"],
  skip:["bg-gray-100 text-gray-600","暂不建议"],
  already:["bg-amber-light text-amber-700","已安装"]};
const show=(el,on)=>$(el).classList[on?"remove":"add"]("hidden");
function scoreColor(v){return v>=60?"#0a7a43":v>=40?"#3056D3":"#9aa3ad";}
async function run(){
  const link=$("link").value.trim();if(!link)return;
  $("go").disabled=true;show("card",false);show("err",false);
  $("spin").classList.remove("hidden");$("spin").classList.add("flex");
  try{
    const r=await fetch("/api/assess?link="+encodeURIComponent(link));
    const d=await r.json();
    if(d.error)throw new Error(d.error);
    $("sname").textContent=d.skill_name;
    const val=Math.round(d.score.value);
    $("sval").innerHTML=val+'<span class="text-base font-medium text-body-color">/100</span>';
    $("sval").style.color=scoreColor(val);
    const v=VMAP[d.verdict]||["bg-gray-100 text-gray-600",d.verdict_label];
    $("verdict").className="mt-2 inline-flex rounded-full px-3 py-1 text-sm font-semibold "+v[0];
    $("verdict").textContent=d.verdict_label;
    $("reason").textContent=d.verdict_reason;
    $("dims").innerHTML=DIMS.map(([k,l])=>{const x=Math.round(d.score.dimensions[k]*100);
      return `<div><div class="mb-1.5 flex justify-between text-xs text-body-color">
        <span>${l}</span><span class="font-semibold text-dark">${x}</span></div>
        <div class="h-2 w-full rounded-full bg-gray-200"><div class="h-2 rounded-full bg-primary" style="width:${x}%"></div></div></div>`;}).join("");
    const e=d.env;const chips=[];
    chips.push(e.os_supported?'<span class="rounded-md bg-green-light px-2.5 py-1 text-green-700">系统 ✓ 支持</span>'
      :'<span class="rounded-md bg-red-50 px-2.5 py-1 text-red-700">系统 ✗ 不支持</span>');
    if(e.required_bins.length)chips.push('<span class="rounded-md bg-white px-2.5 py-1 text-body-color ring-1 ring-stroke">依赖 '+e.required_bins.join(", ")+'</span>');
    if(e.missing_bins.length)chips.push('<span class="rounded-md bg-amber-light px-2.5 py-1 text-amber-700">缺失 '+e.missing_bins.join(", ")+'</span>');
    if(e.already_installed)chips.push('<span class="rounded-md bg-gray-100 px-2.5 py-1 text-gray-600">已安装</span>');
    $("env").innerHTML='<span class="mr-1 font-semibold text-dark">环境适配</span>'+chips.join("");
    $("prompt").textContent=d.install_prompt;
    show("card",true);
  }catch(err){$("err").textContent="出错了："+err.message;show("err",true);}
  finally{$("go").disabled=false;$("spin").classList.add("hidden");$("spin").classList.remove("flex");}
}
$("go").onclick=run;$("link").addEventListener("keydown",e=>{if(e.key==="Enter")run();});
$("copy").onclick=()=>{navigator.clipboard.writeText($("prompt").textContent).then(()=>{
  $("copy").textContent="已复制 ✓";setTimeout(()=>$("copy").textContent="复制",1500);});};
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    profile: UserProfile
    env: LocalEnvironment

    def log_message(self, *args):  # silence default logging
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/":
            self._send(200, _PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if parsed.path == "/api/assess":
            link = (parse_qs(parsed.query).get("link") or [""])[0]
            self._send(200, self._assess_json(link), "application/json; charset=utf-8")
            return
        self._send(404, b"not found", "text/plain")

    def _assess_json(self, link: str) -> bytes:
        try:
            result = assess_skill(link, profile=self.profile, env=self.env)
            payload = result.model_dump()
        except SkillFetchError as exc:
            payload = {"error": str(exc)}
        except Exception as exc:  # noqa: BLE001 - surface any failure to the UI
            payload = {"error": f"{type(exc).__name__}: {exc}"}
        return json.dumps(payload, ensure_ascii=False).encode("utf-8")


def serve(
    *,
    host: str = "127.0.0.1",
    port: int = 8773,
    claude_home: Path | None = None,
    open_browser: bool = True,
) -> None:
    # Scan local usage + environment once at startup; reuse across requests.
    _Handler.profile = scan_user_profile(claude_home)
    _Handler.env = detect_environment(claude_home)

    server = None
    for candidate in range(port, port + 12):
        try:
            server = ThreadingHTTPServer((host, candidate), _Handler)
            port = candidate
            break
        except OSError:
            continue
    if server is None:
        raise RuntimeError(f"找不到可用端口({port}-{port + 11} 都被占用)")

    url = f"http://{host}:{port}/"
    print(f"SkillsVote 本地服务已启动: {url}")
    print(f"(已扫描 {_Handler.profile.prompt_count} 条本地使用记录，环境: {_Handler.env.os_kind})")
    print("按 Ctrl+C 停止。")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n已停止。")
    finally:
        server.server_close()
