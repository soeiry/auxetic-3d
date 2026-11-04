# Parametric auxetic CAD

실행 검증한 **CadQuery + JSON 원본**, 기본 및 변경 예시의 STEP/STL, 네 방향 미리보기를 제공합니다. Inventor가 없는 Linux 환경이므로 `.ipt`는 생성하지 않았으며, 대신 **Inventor 2024–2026용 네이티브 스케치/돌출 생성 iLogic 소스(실행·컴파일 미검증)**를 제공합니다.

- [한국어 수정 안내](GUIDE_KO.md)
- [독립 변수 파일](config/paper_default.json)
- [실제 실행한 변경 예시](config/angle_diameter_example.json)
- [Inventor 최초 생성 규칙](inventor/CreateAuxeticModels.iLogicVb)
- [Inventor 재구성 규칙](inventor/RebuildAuxetic.iLogicVb)
- [검증 요약](verification/summary.json)
- [전체 다운로드 ZIP](../output/auxetic_parametric_bundle.zip) — GitHub 파일 페이지에서 **Download raw file** 선택

ZIP에는 `generated/paper_default/`와 `generated/angle_diameter_example/`의 실제 CAD/이미지가 포함됩니다. `generated/` 디렉터리는 중복 저장을 줄이기 위해 Git 추적에서 제외합니다.

```bash
python -m pip install -r requirements.txt
python run_model.py --config config/paper_default.json --output my_result
```

Inventor에서 생성한 IPT의 치수 변경은 **관리 → 매개변수 → 사용자 매개변수**에서 수행하고, 반드시 내장된 **RebuildAuxetic 규칙 실행 → Update** 순서로 재계산해야 합니다. 이 규칙은 생성 피처를 재작성하므로 피처 ID나 외부 참조를 유지하는 방식은 아닙니다. 자세한 절차와 한계는 한국어 안내를 참조하세요.
