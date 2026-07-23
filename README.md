# Telegram Public History Collector

Telegram 로그인이나 Bot Token 없이 공개 채널의 `t.me/s/` 페이지를 과거
방향으로 탐색해 메시지를 모으는 수집기입니다. 비공개 채널, 삭제된 게시물,
Telegram 공개 웹페이지에 노출되지 않는 콘텐츠는 수집할 수 없습니다.
사진·영상 파일은 내려받지 않고 해당 메시지 링크와 미디어 존재 여부만
기록합니다.

## 최신 결과 바로 받기

- [전체 결과 ZIP](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/telegram-public-history.zip)
- [Excel용 CSV](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/all_messages.csv)
- [전체 JSONL](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/all_messages.jsonl)
- [수집 결과 manifest](https://github.com/leeminhong/telegram-public-history-collector/releases/download/latest-data/manifest.json)

각 수동 실행이 성공하면 `latest-data` Release의 파일들이 새 결과로
교체됩니다. 따라서 위 링크는 그대로 두고 반복해서 사용할 수 있습니다.

## GitHub에서 버튼으로 실행

1. 이 디렉터리의 내용만 새 개인 **공개** GitHub 저장소에 올립니다.
2. 저장소의 기본 브랜치에서 `Actions` 탭을 엽니다.
3. `Collect Telegram public history`를 선택합니다.
4. `Run workflow`를 누릅니다.
5. 완료된 실행 화면의 `Artifacts`에서
   `telegram-public-history-...` 파일을 내려받습니다.

입력값:

- `channels`: 쉼표 또는 공백으로 구분한 채널 ID/공개 URL입니다. 비우면
  `channels.json`의 전체 채널을 수집합니다.
- `max_pages_per_channel`: `0`이면 Telegram이 더 이상 과거 페이지를
  반환하지 않을 때까지 진행합니다. 시험 실행은 `2`나 `5`가 적당합니다.
- `workers`: 동시에 수집할 채널 수입니다.
- `request_delay_seconds`: 같은 채널의 다음 페이지를 요청하기 전 대기시간입니다.

GitHub의 `Run workflow` 버튼은 `workflow_dispatch` 워크플로가 기본 브랜치에
있어야 나타나며, 실행자에게 저장소 쓰기 권한이 필요합니다.

## 결과물

- `manifest.json`: 채널별 페이지·메시지 수, 수집 완결 여부, 오류, 파일 해시
- `all_messages.jsonl`: 전체 채널을 시간순으로 합친 원본
- `all_messages.csv`: Excel에서 바로 열 수 있는 전체 자료
- `by_channel/<채널>.jsonl`: 채널별 시간순 자료

실행 제한이나 사용자의 취소로 수집기가 강제 종료되면 완료된
`<채널>.jsonl` 외에 `<채널>.partial.jsonl`이 남을 수 있습니다. partial
파일은 최신 페이지부터 과거 방향으로 기록된 복구용 자료입니다.

`complete`가 `false`이고 `stop_reason`이 `max_pages`이면 사용자가 지정한
페이지 제한에서 멈춘 것입니다. `error`가 있으면 그 채널은 일부 자료만
포함됐을 수 있습니다.

## 로컬 시험

Python 3.11 이상에서 외부 패키지 없이 실행됩니다.

```bash
python -m unittest discover -s tests -v
python collector.py \
  --channels nhfutures \
  --max-pages 2 \
  --workers 1 \
  --output-dir output
```

사내 TLS 검사 인증서를 사용해야 하는 환경에서는 검증을 끄지 말고
`--ca-bundle /path/to/company-ca.pem`을 사용합니다.

## 운영상 제한

- GitHub 호스티드 러너의 한 작업은 최대 6시간입니다. 게시물이 매우 많은
  채널은 먼저 작은 `max_pages_per_channel`로 규모를 확인하십시오.
- 공개 HTML 구조가 바뀌면 파서 수정이 필요할 수 있습니다.
- 너무 빠른 요청은 일시적인 차단을 유발할 수 있으므로 기본 요청 간격을
  유지하는 편이 좋습니다.
- 회사가 차단한 외부 자료를 반입하는 용도라면 저장소 생성과 데이터 반입
  전에 내부 보안정책 승인을 확인하십시오.
- 공개 저장소에서는 채널 목록, Actions 실행 로그와 생성된 Artifact가 외부에
  노출될 수 있습니다. Hermes 설정·인증정보·사내 보고서는 이 저장소에
  커밋하거나 Artifact에 포함하지 마십시오.
