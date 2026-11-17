#!/usr/bin/env python3
"""news.json / weekly.json -> 음성 대본 -> Gemini TTS(API) -> mp3

사용: python3 gemini_tts.py 입력.json 출력.mp3 [--dry]
환경변수: GEMINI_API_KEY (필수, --dry 제외), GEMINI_VOICE (기본 Erinome),
          GEMINI_TTS_MODELS (쉼표로 구분한 모델 우선순위)
"""
import json, os, sys, re, time, datetime, pathlib, subprocess, wave

MODELS = [m.strip() for m in os.environ.get(
    "GEMINI_TTS_MODELS",
    "gemini-3.1-flash-tts-preview,gemini-2.5-flash-preview-tts").split(",") if m.strip()]
VOICE = os.environ.get("GEMINI_VOICE") or "Erinome"
SR = 24000  # Gemini TTS 출력: 24kHz, 16bit, mono PCM
ORD = ["첫", "두", "세", "네", "다섯", "여섯", "일곱", "여덟", "아홉", "열"]


def build_narration(data):
    items = data.get("items", [])
    d = datetime.date.fromisoformat(data["date"])
    wd = "월화수목금토일"[d.weekday()]
    weekly = data.get("mode") == "weekly"
    parts = []  # (문단 텍스트) 리스트. 문단 사이에 쉼을 넣는다.
    if weekly:
        parts.append(f"{d.month}월 {d.day}일 {wd}요일, 이번 주 뉴스 브리핑입니다.")
    else:
        parts.append(f"{d.month}월 {d.day}일 {wd}요일 아침 뉴스 브리핑입니다.")
    if data.get("headline"):
        parts.append(data["headline"])
    top3 = [i for i in data.get("top3", []) if 1 <= i <= len(items)]
    if top3:
        titles = [items[i - 1]["title"] for i in top3]
        lead = "이번 주 가장 눈여겨볼 소식은 " if weekly else "오늘 가장 눈여겨볼 소식은 "
        parts.append(lead + ", ".join(titles) + " 입니다.")
    parts.append("그럼 순서대로 전해 드립니다.")
    for n, it in enumerate(items):
        o = ORD[n] if n < len(ORD) else str(n + 1)
        script = (it.get("script") or "").strip()
        if not script:  # 대본이 없으면 화면용 글로 대체
            script = " ".join([it.get("summary", "")] + list(it.get("points", [])[:3]) + [it.get("context", "")])
        parts.append(f"{o} 번째 소식입니다. {script}")
    if data.get("closing"):  # 주간판: 다음 주 볼 일정 등 마무리 멘트(화면에는 나오지 않음)
        parts.append(str(data["closing"]))
    parts.append("이상 이번 주 뉴스 브리핑이었습니다." if weekly else "이상 아침 뉴스 브리핑이었습니다.")
    return [re.sub(r"\s+", " ", p).strip() for p in parts if p and p.strip()]


def chunks(paras, limit=1200):
    """문단을 문장 단위로 모아 limit 글자 안팎의 덩어리로 만든다(한 문단은 쪼개지 않으려 노력)."""
    out, cur = [], ""
    for p in paras:
        sents = re.findall(r"[^.!?]+[.!?]*", p) or [p]
        for s in sents:
            s = s.strip()
            if not s:
                continue
            if cur and len(cur) + len(s) + 1 > limit:
                out.append(cur)
                cur = s
            else:
                cur = (cur + " " + s).strip()
    if cur:
        out.append(cur)
    return out


def tts_chunk(key, text, model):
    """공식 REST(generateContent)로 직접 호출. 반환: PCM 바이트"""
    import base64, urllib.request, urllib.error
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = {
        "contents": [{"parts": [{"text": "다음 글을 차분하고 또렷한 아나운서 톤으로, 뉴스 브리핑처럼 읽어 주세요.\n\n" + text}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": VOICE}}},
        },
    }
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"HTTP {e.code}: {e.read().decode('utf-8', 'replace')[:300]}")
    for cand in resp.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inl = part.get("inlineData") or part.get("inline_data")
            if inl and inl.get("data"):
                return base64.b64decode(inl["data"])
    raise RuntimeError("응답에 오디오가 없음: " + json.dumps(resp)[:300])


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    dry = "--dry" in sys.argv
    data = json.loads(pathlib.Path(src).read_text(encoding="utf-8"))
    paras = build_narration(data)
    text_all = "\n".join(paras)
    print(f"대본 {len(text_all)}자, 문단 {len(paras)}개")
    pathlib.Path(out + ".txt").write_text(text_all, encoding="utf-8")
    cs = chunks(paras)
    print(f"덩어리 {len(cs)}개")
    if dry:
        return
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    print(f"API 키 길이: {len(key)}자")
    if not key:
        raise SystemExit("GEMINI_API_KEY 가 비어 있음")

    pcm_all = bytearray()
    used = None
    silence = b"\x00\x00" * int(SR * 0.6)
    for idx, c in enumerate(cs, 1):
        pcm = None
        last_err = None
        order = ([used] if used else []) + [m for m in MODELS if m != used]
        for model in order:
            for attempt in range(4):
                try:
                    pcm = tts_chunk(key, c, model)
                    used = model
                    break
                except Exception as e:  # 한도(429)·일시 오류 재시도
                    last_err = e
                    msg = str(e)
                    print(f"[{idx}/{len(cs)}] {model} 시도 {attempt+1} 실패: {msg[:200]}")
                    time.sleep(30 if "429" in msg or "RESOURCE_EXHAUSTED" in msg or "HTTP 429" in msg else 8)
            if pcm:
                break
        if not pcm:
            raise SystemExit(f"덩어리 {idx} 실패: {last_err}")
        pcm_all += pcm + silence
        print(f"[{idx}/{len(cs)}] 완료 ({model if pcm else ''}), 누적 {len(pcm_all)/2/SR:.0f}초")
        time.sleep(4)  # 무료 구간 분당 한도 여유

    wav = out + ".wav"
    with wave.open(wav, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes(bytes(pcm_all))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", wav, "-ac", "1", "-b:a", "64k", out], check=True)
    os.remove(wav)
    dur = len(pcm_all) / 2 / SR
    pathlib.Path(out + ".meta").write_text(f"model={used}\nvoice={VOICE}\nseconds={dur:.0f}\nchars={len(text_all)}\n")
    print(f"완성: {out} ({dur/60:.1f}분, 모델 {used}, 목소리 {VOICE})")


if __name__ == "__main__":
    main()
