# Auxetic 3D CAD 결과물 받기

## 새 파라메트릭 패키지

**[auxetic_parametric_bundle.zip](auxetic_parametric_bundle.zip)** — 파일 페이지의 **Download raw file**로 받으세요.

CadQuery + JSON 원본, 기본 및 변경 조건의 실제 STEP/STL, 네 방향 미리보기, 한국어 수정 안내, Inventor 2024–2026용 iLogic 소스가 들어 있습니다. **Inventor 실행 환경이 없어 `.ipt`는 생성하지 않았으며 iLogic 규칙도 Inventor에서 컴파일/실행하지 못했습니다.** CadQuery 경로의 생성과 검증은 실제로 수행했습니다.

- [한국어 사용 안내](../parametric/GUIDE_KO.md)
- [검증 결과](../parametric/verification/summary.json)
- [기본 단위 셀 네 방향](parametric_default_unit_views.png)
- [기본 반복 격자 네 방향](parametric_default_lattice_views.png)
- [각도·직경·배율 변경 예시 네 방향](parametric_variant_unit_views.png)

아래 내용은 이전 버전 `auxetic_3d_cad_bundle.zip`에 대한 검증 기록입니다.

이 폴더의 `auxetic_3d_cad_bundle.zip`은 실제 CAD 결과물과 재생성 코드를 담고 있습니다. GitHub에서 해당 파일을 열고 **Download raw file** 버튼을 눌러 내려받으세요. 저장소가 비공개이면 저장소 접근 권한이 있는 GitHub 계정으로 로그인해야 합니다.

## 파일 검증

2026-11-04에 원본 ZIP과 이 폴더에 복사한 파일을 검사했습니다.

- 크기: **10,036,059 bytes** (약 9.57 MiB)
- ZIP 항목: **28개**, 전체 CRC 검사 통과
- 내부 SHA-256 목록에 있는 **27개 파일**의 해시 일치
- ZIP SHA-256: `b21a235a6730d43607b35f40ef9e3a3d6693765245062a1c95d59153a37f3b1c`

다운로드 후 ZIP 파일과 `.sha256` 파일을 같은 폴더에 두고 확인할 수 있습니다.

```bash
sha256sum -c auxetic_3d_cad_bundle.zip.sha256
python -m zipfile -t auxetic_3d_cad_bundle.zip
python -m zipfile -e auxetic_3d_cad_bundle.zip auxetic_cad
```

Windows PowerShell에서는 `Get-FileHash .\auxetic_3d_cad_bundle.zip -Algorithm SHA256`의 값을 위 SHA-256과 비교하면 됩니다.

## ZIP에 포함된 주요 파일

| ZIP 내부 위치 | 내용 |
|---|---|
| `outputs/unit_cell.step` | 단위 셀 STEP, 1,133,418 bytes |
| `outputs/unit_cell.stl` | 단위 셀 STL, 791,484 bytes |
| `outputs/lattice_2x2x2.step` | 2×2×2 격자 STEP, 9,189,281 bytes |
| `outputs/lattice_2x2x2.stl` | 2×2×2 격자 STL, 6,232,884 bytes |
| `model_auxetic.py` | CadQuery 생성·검사·미리보기 코드 |
| `requirements-cad.txt` | Python 의존성 목록 |
| `MODEL_NOTES_KO.md` | 한국어 모델 설명, 논문 값과 모델링 가정, 재생성 방법 |
| `outputs/*_views.png` 및 개별 PNG | 단위 셀과 반복 격자의 등각도·정면·측면·윗면 |
| `outputs/design_variables.csv` | 설계변수 표 |
| `outputs/validation.json` | 기존 생성 시 수행한 STEP 재읽기 및 형상 검사 결과 |

저장소의 전달 폴더 이름은 `output/`이며, ZIP 안의 생성 결과 폴더 이름은 `outputs/`입니다. 압축 해제 후 재생성하려면 해제한 폴더에서 `python model_auxetic.py`를 실행하세요. 모델 설명서에는 원래 클라우드 작업 디렉터리도 기재되어 있습니다.

이번 전달 점검에서는 기존 ZIP의 무결성을 확인하고 그대로 복사했습니다. 형상을 다시 생성하거나 해석하지 않았습니다. 기존 STEP 재읽기 검사에서 두 모델은 각각 유효한 단일 솔리드였습니다. TPU의 변형, z방향 팽창 또는 잠김 성능을 검증한 결과는 아닙니다.
