# Daily Market Input Collector

내부망의 Gemini가 요약할 입력자료를 만들기 위해 공개 Telegram 채널의 최근
게시물과 오선의 미국 증시 요약 YouTube Posts를 모읍니다. Telegram 로그인,
Bot Token, YouTube API Key는 필요하지 않습니다.

기본 수집 구간은 실행 시각 직전 12시간입니다. 비공개·삭제 게시물이나 공개
웹페이지에 노출되지 않는 콘텐츠, 사진·영상 파일 자체는 수집하지 않습니다.

## 최신 결과 바로 받기

- [전체 결과 ZIP](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/market-inputs.zip)
- [Gemini용 JSON](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/market_inputs.json)
- [Excel용 CSV](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/market_inputs.csv)
- [전체 JSONL](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/market_inputs.jsonl)
- [수집 결과 manifest](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/manifest.json)
- [Gemini 보고서 프롬프트](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/gemini_market_brief_prompt.md)

각 자동·수동 실행이 성공하면 `latest-data` Release의 파일들이 새 결과로
교체됩니다. 내부망은 같은 URL을 반복해서 내려받으면 됩니다.

자동 실행 시각은 매일 06:55, 07:55, 16:15(KST)입니다.

## GitHub에서 수동 실행

1. 저장소의 `Actions` 탭을 엽니다.
2. `Collect daily market inputs`를 선택합니다.
3. `Run workflow`를 누릅니다.
4. 완료되면 위 고정 링크 또는 실행 화면의 Artifact에서 결과를 받습니다.

입력값:

- `channels`: 쉼표 또는 공백으로 구분한 채널 ID/공개 URL입니다. 비우면
  `channels.json`의 기본 채널을 사용합니다.
- `window_hours`: 실행 시각부터 몇 시간 전까지 수집할지 정합니다. 기본값은
  `12`입니다.
- `max_pages_per_channel`: 최근 구간을 찾기 위한 안전 한도입니다. 기본
  `100`이면 일일 수집에 충분합니다.
- `workers`: 동시에 수집할 채널 수입니다.
- `request_delay_seconds`: 같은 채널의 다음 페이지를 요청하기 전 대기시간입니다.

기본 채널은 NH선물과 국내 증권사 채권·경제·전략 채널 10개입니다. 한기평,
인포맥스(`kwtok`)와 해외 실시간 속보(`FinancialJuice`, `firstsquaw`,
`livesquaw`)는 제외했습니다.

## 결과물

- `market_inputs.json`: 내부 Gemini에 바로 전달할 메타데이터 포함 단일 JSON
- `market_inputs.jsonl`: Telegram과 오선 게시물을 합친 전체 원본
- `market_inputs.csv`: Excel에서 확인할 수 있는 전체 자료
- `telegram_messages.jsonl`: Telegram 게시물만 모은 원본
- `futuresnow_posts.jsonl`: 오선 게시물만 모은 원본
- `by_channel/<채널>.jsonl`: 채널별 Telegram 자료
- `manifest.json`: 수집 구간, 채널별 건수, 오선 상태, 오류 및 파일 해시
- `gemini_market_brief_prompt.md`: 07:10·08:10·16:30 보고서 공용 프롬프트

내부 Gemini는 `market_inputs.json`의 `window_kst`와 각 항목의
`published_at_kst`를 사용해 보고 구간을 필터링합니다. 오선 게시물은
YouTube가 정확한 ISO 게시시각을 제공하지 않으므로 `report_date`와
`published_text`를 사용합니다.

## 로컬 시험

Python 3.11 이상에서 외부 패키지 없이 실행됩니다.

```bash
python -m unittest discover -s tests -v
python collector.py \
  --channels nhfutures \
  --window-hours 12 \
  --max-pages 10 \
  --workers 1 \
  --output-dir output
```

사내 TLS 검사 인증서를 사용해야 하는 환경에서는 검증을 끄지 말고
`--ca-bundle /path/to/company-ca.pem`을 사용합니다.

## 운영상 제한

- Telegram 또는 YouTube의 공개 HTML 구조가 바뀌면 파서 수정이 필요할 수
  있습니다.
- 너무 빠른 요청은 일시적인 차단을 유발할 수 있으므로 기본 요청 간격을
  유지하는 편이 좋습니다.
- 회사가 차단한 외부 자료를 반입하는 용도라면 내부 보안정책 승인을 먼저
  확인하십시오.
- 공개 저장소에서는 채널 목록, Actions 로그와 Release 결과가 외부에
  노출됩니다. Hermes 설정·인증정보·사내 보고서는 포함하지 마십시오.
