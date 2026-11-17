#!/usr/bin/env python3
# 휴대폰용 웹 페이지(brief.html) 생성. 디자인과 듣기 기능은 고정 — 고치지 않는다. (일간/주간은 제목·파일명만 다름)
import json, sys, html, datetime, pathlib

src = sys.argv[1] if len(sys.argv) > 1 else "news.json"
data = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
items = data.get("items", [])
weekly = data.get("mode") == "weekly"
try:
    d = datetime.date.fromisoformat(data["date"])
    date_ko = f"{d.year}년 {d.month}월 {d.day}일 {'월화수목금토일'[d.weekday()]}요일"
    tag = d.isoformat()
except Exception:
    date_ko = tag = str(data.get("date", ""))

E = lambda s: html.escape(str(s or ""))
COL = {"정치": "#7C3AED", "경제": "#0F766E", "사회": "#DC2626", "교육": "#2563EB",
       "문화": "#D97706", "국제": "#4338CA", "IT·산업": "#0891B2", "IT·문화": "#0891B2",
       "생활": "#65A30D"}

PDF_NAME = f"{'주간브리핑' if weekly else '브리핑'}_{tag}.pdf"
KICKER = "WEEKLY BRIEF" if weekly else "MORNING BRIEF"
H1 = f"이번 주 뉴스 {len(items)}" if weekly else f"오늘의 뉴스 {len(items)}"
PAGE_TITLE = "주간 뉴스 브리핑" if weekly else "아침 뉴스 브리핑"

def card(i, it):
    c = COL.get(it.get("category"), "#6B7280")
    pts = "".join(f"<li>{E(p)}</li>" for p in (it.get("points") or [])[:3])
    url = it.get("url")
    link = f'<a class="src" href="{E(url)}" target="_blank" rel="noopener">원문 보기</a>' if url else ""
    ctx = it.get("context")
    return f"""<article class="card" style="--c:{c}">
<div class="head"><span class="num">{i+1:02d}</span><span class="cat">{E(it.get('category') or '뉴스')}</span><span class="press">{E(it.get('press'))}</span><button class="spk" data-i="{i}" aria-label="이 기사 듣기">🔊</button></div>
<h2>{E(it.get('title'))}</h2>
<p class="lead">{E(it.get('summary'))}</p>
{f'<ul>{pts}</ul>' if pts else ''}
{f'<p class="ctx"><b>배경</b> {E(ctx)}</p>' if ctx else ''}
{link}
</article>"""

toc = "".join(f'<li><a href="#n{i+1}"><span>{i+1:02d}</span>{E(it.get("title"))}</a></li>' for i, it in enumerate(items))
cards = "".join(f'<div id="n{i+1}">{card(i, it)}</div>' for i, it in enumerate(items))


EXTRA_CSS = """
.bar{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin:-4px 0 18px}
.bar button{font:inherit;font-size:14px;font-weight:700;padding:10px 14px;border-radius:10px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.bar label{font-size:13px;color:var(--mute);display:flex;gap:6px;align-items:center}
.bar select{font:inherit;font-size:13px;padding:8px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink)}
.spk{margin-left:8px;font-size:16px;line-height:1;padding:6px 8px;border-radius:8px;border:1px solid var(--line);background:transparent;cursor:pointer}
.card.on{outline:2px solid var(--acc)}
"""

SCRIPT = r"""
<script>
(function(){
  var synth = window.speechSynthesis;
  var bar = document.getElementById('bar');
  var spks = [].slice.call(document.querySelectorAll('.spk'));
  if(!synth || typeof SpeechSynthesisUtterance === 'undefined'){
    if(bar) bar.style.display='none';
    spks.forEach(function(b){b.style.display='none';});
    return;
  }
  var cards = [].slice.call(document.querySelectorAll('article.card'));
  var voice = null, token = 0;
  function pickVoice(){
    var v = synth.getVoices().filter(function(x){return /^ko/i.test(x.lang);});
    voice = v.length ? v[0] : null;
  }
  pickVoice();
  if(synth.onvoiceschanged !== undefined) synth.onvoiceschanged = pickVoice;
  function rate(){ return parseFloat(document.getElementById('rate').value) || 1; }
  function textOf(c){
    var t = [c.querySelector('h2').textContent, c.querySelector('.lead').textContent];
    c.querySelectorAll('ul li').forEach(function(l){ t.push(l.textContent); });
    var ctx = c.querySelector('.ctx'); if(ctx) t.push(ctx.textContent);
    return t.join('. ');
  }
  function chunks(s){
    var parts = s.replace(/\s+/g,' ').match(/[^.!?]+[.!?]*/g) || [s];
    var out = [], cur = '';
    parts.forEach(function(p){
      p = p.trim(); if(!p) return;
      if(cur && (cur + ' ' + p).length > 110){ out.push(cur); cur = p; }
      else cur = cur ? cur + ' ' + p : p;
    });
    if(cur) out.push(cur);
    return out;
  }
  function mark(i){
    cards.forEach(function(c,k){ c.classList.toggle('on', k === i); });
    if(i >= 0 && cards[i]) cards[i].scrollIntoView({behavior:'smooth', block:'center'});
  }
  function stop(){ token++; synth.cancel(); mark(-1); }
  function speak(list){
    stop();
    var my = ++token, queue = [];
    list.forEach(function(i){
      chunks(textOf(cards[i])).forEach(function(c,k){ queue.push({i:i, t:c, first:k===0}); });
    });
    var n = 0;
    (function next(){
      if(my !== token) return;
      if(n >= queue.length){ mark(-1); return; }
      var q = queue[n++];
      var u = new SpeechSynthesisUtterance(q.t);
      u.lang = 'ko-KR'; if(voice) u.voice = voice; u.rate = rate();
      if(q.first) mark(q.i);
      u.onend = next;
      u.onerror = function(){ if(my === token) next(); };
      synth.speak(u);
    })();
  }
  document.getElementById('playAll').addEventListener('click', function(){
    speak(cards.map(function(_,i){return i;}));
  });
  document.getElementById('stopAll').addEventListener('click', stop);
  spks.forEach(function(b){
    b.addEventListener('click', function(){ speak([parseInt(b.getAttribute('data-i'),10)]); });
  });
  window.addEventListener('pagehide', function(){ synth.cancel(); });
})();
</script>
"""

PAGE = f"""<!doctype html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{PAGE_TITLE}</title>
<style>
:root{{--bg:#F4F5F7;--card:#fff;--ink:#111827;--sub:#4B5563;--mute:#9CA3AF;--line:#E5E7EB;--acc:#1D4ED8}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#0F1115;--card:#181B21;--ink:#F3F4F6;--sub:#C4C9D2;--mute:#7C8594;--line:#2A2F38;--acc:#7AA2FF}}}}
:root[data-theme="dark"]{{--bg:#0F1115;--card:#181B21;--ink:#F3F4F6;--sub:#C4C9D2;--mute:#7C8594;--line:#2A2F38;--acc:#7AA2FF}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--ink);font-family:Pretendard,-apple-system,"Noto Sans KR","맑은 고딕",sans-serif;line-height:1.65;-webkit-text-size-adjust:100%}}
main{{max-width:680px;margin:0 auto;padding:24px 16px 56px}}
.kicker{{font-size:12px;font-weight:800;letter-spacing:2px;color:var(--acc)}}
h1{{font-size:30px;line-height:1.2;margin:6px 0 4px;letter-spacing:-.5px}}
.date{{color:var(--mute);font-size:14px;margin-bottom:16px}}
.pdf{{display:inline-block;margin:0 0 18px;padding:10px 16px;border-radius:10px;background:var(--acc);color:#fff;font-weight:700;font-size:14px;text-decoration:none}}
.toc{{list-style:none;margin:0 0 22px;padding:0;background:var(--card);border:1px solid var(--line);border-radius:12px}}
.toc li+li{{border-top:1px solid var(--line)}}
.toc a{{display:flex;gap:12px;padding:12px 14px;color:var(--ink);text-decoration:none;font-weight:600;font-size:15px}}
.toc span{{color:var(--acc);font-weight:800;min-width:24px}}
.card{{background:var(--card);border:1px solid var(--line);border-left:6px solid var(--c);border-radius:12px;padding:18px 16px;margin-bottom:14px}}
.head{{display:flex;align-items:center;gap:8px;margin-bottom:8px}}
.num{{font-weight:900;color:var(--c)}}
.cat{{background:var(--c);color:#fff;font-size:12px;font-weight:700;padding:2px 10px;border-radius:20px}}
.press{{margin-left:auto;color:var(--mute);font-size:12px}}
h2{{font-size:20px;line-height:1.35;margin:0 0 8px;letter-spacing:-.3px}}
.lead{{margin:0;color:var(--sub);font-size:15.5px}}
ul{{margin:12px 0 0;padding-left:20px;color:var(--sub);font-size:15px}}
li{{margin-bottom:4px}}
.ctx{{margin:12px 0 0;padding-top:10px;border-top:1px solid var(--line);color:var(--mute);font-size:14px}}
.ctx b{{color:var(--acc);margin-right:4px}}
.src{{display:inline-block;margin-top:10px;color:var(--acc);font-size:14px;font-weight:600}}
{EXTRA_CSS}</style></head><body><main>
<div class="kicker">{KICKER}</div>
<h1>{H1}</h1>
<div class="date">{E(date_ko)}</div>
<a class="pdf" href="{E(PDF_NAME)}">PDF 내려받기</a>
<div id="bar" class="bar"><button id="playAll" type="button">▶ 전체 듣기</button><button id="stopAll" type="button">■ 정지</button><label>속도 <select id="rate"><option value="0.9">느리게</option><option value="1" selected>보통</option><option value="1.2">빠르게</option><option value="1.4">더 빠르게</option></select></label></div>
<ol class="toc">{toc}</ol>
{cards}
</main>{SCRIPT}</body></html>"""

pathlib.Path("brief.html").write_text(PAGE, encoding="utf-8")
print(f"완성: brief.html ({len(items)}건)")
