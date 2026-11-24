# TileNamer 개발 현황

확인일 2026-11-24 · 기본 브랜치 `main` · [개발 브랜치](https://github.com/rodetoast/TileNamer/tree/codex/migration-checkpoint-20261117) · [조사 기준 소스 커밋](https://github.com/rodetoast/TileNamer/commit/71f4080994b7bb33015dd11ac23d51529514b368)

타일 아티스트가 영역을 지정하고 명명 규칙에 맞춰 PNG로 내보냅니다.

- 제품 표시명 **TileNamer** · 런처 app_id `tilenamer`
- 기술 구성 Python, PySide6, PyInstaller
- 구현 기능 격자 기반 영역 지정, 배치 미리보기, 타일 이름 규칙과 가이드, PNG 출력

## 배포 상태

**0.1.6 RC3** · `0.1.6-rc3-8ba7a1e` · `tilenamer--0.1.6-rc3-8ba7a1e.zip` (onefile) · 실행 파일 `TileNamer.exe`. [Rod 운영 카탈로그](https://github.com/rodetoast/creative-group-releases/releases/tag/rodetoast-catalog-000015)

소스 저장소의 독립 Latest Release는 확인되지 않았습니다.

## 개발과 검증

RC3 운영. 배포 기록에서 실행에 필요한 내장 규칙 데이터를 포함합니다.

**알려진 제약과 미검증** 후속 실행 후보와 별도 실기동 검증은 확인되지 않았습니다.

이번 확인에서는 원격 Git과 공개 서명 카탈로그를 대조했습니다. 기능 시험과 패키징은 기존 보고서의 범위를 따릅니다.

## 패키징과 다음 단계

run_app.bat, TileNamer.spec. Aseprite는 운영 ZIP에 포함되지 않습니다. [공통 배포 절차](https://github.com/rodetoast/southpaw-development-hub/blob/main/docs/RELEASE_GUIDE.md)

**다음 단계** 후속 배포 시 규칙 데이터 및 Aseprite 연동 범위를 Windows에서 확인합니다.

[README.md](https://github.com/rodetoast/TileNamer/blob/71f4080994b7bb33015dd11ac23d51529514b368/README.md) · [run_app.bat](https://github.com/rodetoast/TileNamer/blob/71f4080994b7bb33015dd11ac23d51529514b368/run_app.bat) · [TileNamer.spec](https://github.com/rodetoast/TileNamer/blob/71f4080994b7bb33015dd11ac23d51529514b368/TileNamer.spec) · [개발 허브 요약](https://github.com/rodetoast/southpaw-development-hub/blob/main/projects/tilenamer.md)
