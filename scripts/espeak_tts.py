#!/usr/bin/env python3
"""오프라인 한국어 음성 합성(espeak-ng). 사용: python3 espeak_tts.py 입력.txt 출력.wav [속도]"""
import sys, ctypes, wave, array, espeakng_loader
lib = ctypes.CDLL(espeakng_loader.get_library_path())
sr = lib.espeak_Initialize(1, 0, espeakng_loader.get_data_path().encode(), 0)  # SYNCHRONOUS
assert sr > 0, "espeak init failed"
buf = array.array("h")
CB = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.POINTER(ctypes.c_short), ctypes.c_int, ctypes.c_void_p)
def cb(wav, n, ev):
    if wav and n > 0: buf.extend(wav[:n])
    return 0
cbf = CB(cb); lib.espeak_SetSynthCallback(cbf)
assert lib.espeak_SetVoiceByName(b"ko") == 0, "ko voice missing"
rate = int(sys.argv[3]) if len(sys.argv) > 3 else 150
lib.espeak_SetParameter(1, rate, 0)   # espeakRATE
text = open(sys.argv[1], encoding="utf-8").read()
for para in [p.strip() for p in text.split("\n") if p.strip()]:
    b = para.encode("utf-8") + b"\0"
    lib.espeak_Synth(b, len(b), 0, 0, 0, 1, None, None)   # espeakCHARS_UTF8
    lib.espeak_Synchronize()
    buf.extend([0] * (sr // 2))   # 0.5초 쉼
lib.espeak_Terminate()
w = wave.open(sys.argv[2], "wb"); w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr); w.writeframes(buf.tobytes()); w.close()
print(f"완성: {sys.argv[2]} ({len(buf)/sr:.1f}초)")
