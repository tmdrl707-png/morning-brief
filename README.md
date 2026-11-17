# morning-brief
아침 뉴스 브리핑 자동화 저장소.
- `news/YYYY-MM-DD.json`, `weekly/YYYY-MM-DD.json` 이 올라오면 GitHub Actions(`tts.yml`)가 Gemini API로 음성(mp3)을 만들어 `audio` 브랜치에 올립니다.
- 필요한 설정: Secret `GEMINI_API_KEY`, (선택) Variable `GEMINI_VOICE`.
