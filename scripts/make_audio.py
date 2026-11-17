#!/usr/bin/env python3
"""news.json -> 듣기 대본(narration.txt) -> 브리핑_YYYY-MM-DD.mp3  (오프라인 espeak-ng, 대체용)
사용: python3 make_audio.py news.json"""
import json, re, sys, datetime, pathlib, subprocess
data = json.loads(pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "news.json").read_text(encoding="utf-8"))
items = data["items"]; d = datetime.date.fromisoformat(data["date"])
weekly = data.get("mode") == "weekly"
D = "영일이삼사오육칠팔구"
def grp(n):  # 0<n<10000
    s = ""
    for v, u in ((1000, "천"), (100, "백"), (10, "십")):
        q = n // v % 10
        if q: s += ("" if q == 1 else D[q]) + u
    q = n % 10
    return s + (D[q] if q else "")
def num(n):
    if n == 0: return "영"
    out = ""
    for i, u in ((3, "조"), (2, "억"), (1, "만"), (0, "")):
        g = n // 10000**i % 10000
        if g:
            out += ("" if (g == 1 and u == "만") else grp(g)) + u
    return out
UNITS = [("km", "킬로미터"), ("mm", "밀리미터"), ("%p", "퍼센트포인트"), ("%", "퍼센트"), ("m", "미터")]
def spoken(t):
    t = re.sub(r"(\d)\s*~\s*(\d)", r"\1에서 \2", t)
    t = re.sub(r"(\d+)월", lambda m: {"6": "유월", "10": "시월"}.get(m.group(1), num(int(m.group(1))) + "월"), t)
    t = re.sub(r"(\d[\d,]*)(\.\d+)?", lambda m: num(int(m.group(1).replace(",", ""))) + ("점 " + " ".join(D[int(c)] for c in m.group(2)[1:]) if m.group(2) else ""), t)
    for a, b in UNITS: t = re.sub(a + r"(?![A-Za-z])", " " + b, t)
    for a, b in (("AI", "에이아이"), ("PER", "피이알"), ("IPO", "아이피오"), ("SK", "에스케이"), ("PHP", "피에이치피"), ("CGT", "씨지티"), ("APEC", "에이펙"), ("AP", "에이피"), ("NATO", "나토")):
        t = t.replace(a, b)
    t = re.sub(r"[…·'\"“”‘’()\[\]]", " ", t).replace("/", " ").replace("&", " 그리고 ")
    return re.sub(r"\s+", " ", t).strip()
K = ["첫", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열"]
wd = "월화수목금토일"[d.weekday()]
if weekly:
    L = [f"{d.month}월 {d.day}일 {wd}요일, 이번 주 뉴스 브리핑입니다. 이번 주는 {len(items)}건을 전해 드립니다."]
else:
    L = [f"{d.month}월 {d.day}일 {wd}요일 아침 뉴스 브리핑입니다. 오늘은 {len(items)}건을 전해 드립니다."]
for i, it in enumerate(items):
    L.append(f"{K[i] if i < 10 else str(i+1)} 번째 소식. {it['title']}.")
    L.append(it["summary"])
    L += [p + "." for p in it.get("points", [])[:3]]
    if it.get("context"): L.append("배경입니다. " + it["context"])
L.append("이상 이번 주 뉴스 브리핑이었습니다." if weekly else "이상 아침 뉴스 브리핑이었습니다.")
txt = "\n".join(spoken(x) for x in L)
pathlib.Path("narration.txt").write_text(txt, encoding="utf-8")
out = f"{'주간브리핑' if weekly else '브리핑'}_{d.isoformat()}"
subprocess.run([sys.executable, str(pathlib.Path(__file__).with_name("espeak_tts.py")), "narration.txt", out + ".wav", "150"], check=True)
subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", out + ".wav", "-ac", "1", "-b:a", "64k", out + ".mp3"], check=True)
pathlib.Path(out + ".wav").unlink()
print("완성:", out + ".mp3")
