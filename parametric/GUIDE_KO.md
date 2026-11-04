# 수정 가능한 3D 아우세틱 모델 — 사용 안내

## 먼저 확인할 실행 범위

이 패키지의 **CadQuery 원본과 JSON 파라미터 파일은 실제로 실행 검증했다.** 기본 조건 및 변경 조건에서 단위 셀과 2×2×2 격자를 생성하고, STEP 재읽기·솔리드 수·연결·간섭·STL 검사를 수행했다.

**`.ipt`와 `.FCStd`는 이 환경에서 생성하지 않았다.** 실행 환경은 Linux이며 Autodesk Inventor/Windows COM 자동화 기능과 FreeCAD 실행기가 없다. 대신 사용자의 Inventor에서 네이티브 스케치와 피처를 생성하도록 작성한 iLogic 규칙 두 개를 제공한다. 이 규칙은 **Inventor에서 컴파일하거나 실행하지 못한 소스**이며, CadQuery 검증 결과가 Inventor 규칙의 성공을 보증하지 않는다. `.step`의 확장자를 `.ipt`로 바꾼 파일도 없다.

대상은 **Windows 64비트용 정식 Autodesk Inventor 2024–2026 + iLogic**이다. Inventor View, 웹 뷰어, Apprentice만으로는 이 규칙을 실행할 수 없다. 이 버전 범위는 작성 대상이며 실제 설치 버전별 호환성 시험을 마친 목록은 아니다.

## 제공 파일

| 위치 | 내용 |
|---|---|
| `config/paper_default.json` | 기본 독립 설계변수. CadQuery와 Inventor 초기 생성에서 함께 사용 |
| `config/angle_diameter_example.json` | 실제 실행한 각도·직경·배율 변경 예시 |
| `run_model.py`, `cad_core.py` | 파라미터 읽기, 형상 생성, 검사, STEP/STL 내보내기, 미리보기 |
| `inventor/CreateAuxeticModels.iLogicVb` | JSON을 읽고 두 개의 네이티브 IPT를 만드는 외부 규칙 |
| `inventor/RebuildAuxetic.iLogicVb` | 각 IPT에 삽입되는 스케치/돌출 재구성 규칙 |
| `generated/paper_default/` | 기본 단위 셀 및 2×2×2 STEP/STL/미리보기/검사 결과 |
| `generated/angle_diameter_example/` | 변경 예시의 동일한 실제 결과물 |
| `generated/*/user_parameters.csv` | 독립·종속 변수와 수식 표 |
| `verification/summary.json` | 실행 여부, 검증 상태, 수치 비교 |
| `tests/test_parameters.py` | 불가능한 입력, 배율, 반복 경계 검사 |
| `requirements.txt` | 현재 실행 환경과 같은 직접 패키지 버전 |

ZIP을 풀면 `auxetic_parametric` 폴더가 생긴다. 이하 터미널 명령은 이 폴더에서 실행한다. GitHub 소스에서는 같은 파일들이 `parametric/` 폴더에 있다. `generated/` 파일들은 다운로드 ZIP에 포함되며 저장소에는 중복 커밋하지 않는다.

## 설계변수 — 한곳에서 입력하기

처음 생성할 때는 `config/paper_default.json` 하나를 수정한다. 메모장이나 VS Code에서 열어 숫자를 바꾼다. JSON에는 주석을 쓰지 말고 소수점은 `.`을 사용한다. 길이는 mm, 각도는 degree다.

| 독립 변수 | 기본값 | 의미 및 출처 |
|---|---:|---|
| `L1_base` | 27.25896641474141 mm | 배율 적용 전 Type I 길이. 논문 L=77.1 mm, θ=22.5°, l₁=b에서 계산 |
| `L2_base` | 41.72621932127179 mm | 배율 적용 전 Type II 길이. 같은 조건에서 계산 |
| `D_base` | 5.581566304621142 mm | 공통 직경. 논문 식 (1)의 명목 μ=0.10에서 역산한 반지름의 2배 |
| `Theta` | 22.5° | 논문 §3.1 기본 각도 |
| `Phi` | 22.5° | 논문 §3.1 기본 각도 |
| `ScaleFactor` | 1 | 전체 길이·직경을 함께 확대/축소하는 모델링용 값 |
| `Nx`, `Ny`, `Nz` | 2, 2, 2 | 각 방향 반복 개수, 사용자 요청 |

`schema_version`은 1을 유지한다. `stl_tolerance_mm`은 형상 치수가 아닌 STL 출력 공차(기본 0.05 mm)다. 배율에 자동 연동하지 않으므로 아주 작은 모델에서는 더 작은 값을 사용한다.

**L1과 L2는 독립적이고 L3는 종속적이다.** l₁=b는 기본값에서만 만족한다. 각도를 바꿀 때 두 독립 부재 길이를 유지하므로 l₁=b가 계속 유지되는 것은 아니다. 이를 의도적으로 자동 강제하지 않았다. 이 관계를 별도로 유지하고 싶으면 `L1_base = L2_base*cos(Theta)/sqrt(2)`가 되도록 두 입력 중 하나를 조정한다.

아래 종속 치수는 계산하여 사용하고, Inventor에서는 User Parameters의 수식으로 생성한다.

```text
L1 = L1_base * ScaleFactor
L2 = L2_base * ScaleFactor
StrutDiameter = D_base * ScaleFactor
CubeHalf = L2 * cos(Theta) / sqrt(2)       # b
L3 = CubeHalf / cos(Phi)
FaceInset = CubeHalf - L2 * sin(Theta)    # a
EdgeCoord = CubeHalf - L3 * sin(Phi)/sqrt(2)  # c
UnitPitch = 2 * (L1 + FaceInset)
SizeX = Nx * UnitPitch
SizeY = Ny * UnitPitch
SizeZ = Nz * UnitPitch
```

Python은 degree 입력을 radians로 변환하여 계산한다. Inventor는 `Theta`, `Phi`의 단위를 deg로 설정하고 자체 수식 엔진에서 삼각함수를 계산한다. API 내부 길이는 cm이므로 규칙에서 mm↔cm 변환을 명시했다.

불가능한 입력은 오류로 중단한다: 음수·0·무한대 길이/배율, 비정수 반복, 0<θ<35.264389° 또는 0<φ<54.735610° 범위 위반, 지나치게 굵은 부재, 셀 경계를 침범하는 치수, 비접합 부재의 잠재 간섭. 반복 개수는 각 축 1~10, 총 64셀까지 제한한다. 간섭 전수 검사는 부재 수의 제곱에 비례하므로 큰 반복은 오래 걸린다.

## CadQuery: 파일 열기 → 변수 변경 → 재계산 → STEP

1. ZIP을 풀고 `config/paper_default.json`을 연다. 원본을 보존하려면 `my_parameters.json`으로 복사한다.
2. 원하는 숫자를 수정하고 저장한다. 예를 들어 `D_base`를 5.0, `Theta`를 20.0, `Phi`를 25.0, `ScaleFactor`를 0.5로 바꾼다.
3. Python 3.12 환경에서 아래 명령으로 패키지를 설치한다. 클라우드에서는 이 패키지들이 이미 설치되어 있었으며, 별도 PC의 설치는 실행 검증하지 않았다.

```bash
python -m venv .venv
```

Windows PowerShell에서는 `.\.venv\Scripts\Activate.ps1`, macOS/Linux에서는 `source .venv/bin/activate`를 실행한 뒤:

```bash
python -m pip install -r requirements.txt
python run_model.py --config config/paper_default.json --output my_result
```

4. 위 명령은 재계산·검사를 수행하고 STEP/STL/네 방향 PNG를 자동으로 내보낸다. 단위 셀은 `my_result/unit_cell.step`, 반복 격자는 `my_result/lattice_2x2x2.step`이다. 반복 수를 바꾸면 격자 파일명도 바뀐다.
5. 같은 폴더에 재생성하려면 `--replace`를 붙인다. 이전 결과는 `.previous-1`, `.previous-2` 등으로 보존한다. 새 출력은 임시 폴더에서 모든 검사가 성공한 뒤에만 교체한다.

```bash
python run_model.py --config config/angle_diameter_example.json --output my_variant
python run_model.py --config config/paper_default.json --output my_result --replace
```

형상 생성 전 입력/연결/간섭만 검사하려면 `--check-only`를 추가한다. 원본은 **Python 코드와 JSON**이다. STEP은 호환용 솔리드이며 설계 이력이나 JSON 연결을 담고 있지 않다.

## Inventor: 최초 네이티브 IPT 생성

1. Inventor 2024–2026 정식 데스크톱을 열고 **새로 만들기 → 부품(Standard.ipt 등)**으로 빈 부품을 하나 연다.
2. **관리(Manage) → iLogic → iLogic 브라우저**를 표시한다. **외부 규칙(External Rules)** 탭에서 우클릭 → **외부 규칙 추가(Add External Rule)**로 `inventor/CreateAuxeticModels.iLogicVb`를 등록한다. 버전/언어에 따라 브라우저 위치나 메뉴 번역이 다를 수 있다.
3. 등록한 규칙을 우클릭 → **규칙 실행(Run Rule)**한다.
4. 첫 파일 선택창에서 함께 받은 `inventor/RebuildAuxetic.iLogicVb`를 선택한다. 두 번째 창에서 `config/paper_default.json`을 선택한다. 마지막으로 새 IPT를 저장할 폴더를 고른다. 같은 이름의 파일이 있으면 덮어쓰지 않고 중단한다.
5. 실행에 성공하면 `unit_cell_parametric.ipt`와 `lattice_2x2x2_parametric.ipt`를 저장한다. 두 파일의 매개변수는 동일하지만, 단위 셀의 Nx/Ny/Nz는 각각 1이다. 초기 JSON에서 반복 수를 바꾸면 두 번째 파일명도 바뀐다.

이 스크립트는 빈 부품 두 개를 새로 만든다. 원기둥 부재 하나마다 네이티브 작업평면, 원형 2D 스케치, 직경 치수, 돌출 피처를 생성한다. 처음은 New Body, 다음부터는 이미 연결된 부재에 Join하는 순서로 구성한다. 기본 단위 셀은 54개, 격자는 432개의 돌출 피처를 만든다. 배열 기능 하나로 압축하는 구현이 아니므로 생성·재구성에 시간이 걸릴 수 있다.

스케치 직경은 `StrutDiameter`에, 돌출 길이는 `L1`, `L2`, `L3`에 수식으로 연결한다. 최종 본체 수와 피처 HealthStatus를 검사하고 실패하면 저장 절차를 중단한다. 이 로직의 실행 결과는 **사용자의 Inventor에서 확인해야 한다**. 성공하지 않았다면 만들어졌다고 가정하지 말고 iLogic 오류 메시지와 행 번호를 확인한다.

## Inventor: 만든 IPT 열기 → 변수 변경 → 재계산 → STEP

1. 위 생성 절차로 얻은 IPT를 연다. 제공한 STEP을 가져온 부품과 구분한다.
2. **관리(Manage) → 매개변수(Parameters)**에서 **사용자 매개변수(User Parameters)**를 찾는다.
3. `L1_base`, `L2_base`, `D_base`, `Theta`, `Phi`, `ScaleFactor`, `Nx`, `Ny`, `Nz` 중 필요한 값만 바꾼다. `L1`, `L2`, `L3`, `UnitPitch` 등의 종속 수식과 `AX_Managed`는 수정하지 않는다.
4. 대화상자를 닫고 iLogic 브라우저의 **규칙(Rules) → RebuildAuxetic → 규칙 실행(Run Rule)**을 실행한다. 이 규칙은 최초 생성 시 각 IPT 내부에 삽입된다.
5. **업데이트(Update)** 후 모델 브라우저에서 **솔리드 본체(Solid Bodies)가 1개**인지 확인하고, 피처 오류가 없으면 IPT를 저장한다.
6. **파일 → 다른 이름으로 저장 → 사본 저장(Save Copy As)**에서 **STEP (*.stp; *.step)**을 선택하여 내보낸다. STL도 같은 메뉴에서 선택하고, 내보내기 옵션의 단위를 mm로 맞춘다. STL 자체에는 단위 정보가 없다.

**Update만 누르는 것으로는 충분하지 않다.** 작업평면 위치와 방향은 생성 시 고정 수치이므로 각도·길이·배율·반복 수 변경 시 반드시 `RebuildAuxetic`을 실행해야 한다. 이 모델은 **iLogic으로 구동하는 네이티브 스케치/피처 모델**이며, 모든 절점이 Inventor 스케치 구속식만으로 자동 이동하는 모델은 아니다. STEP 가져오기 방식과는 달리 스케치·돌출·사용자 매개변수가 남지만, 규칙 실행 시 생성 피처를 재작성한다. 피처의 내부 ID/참조는 유지되지 않는다.

따라서 이 생성 부품에 직접 후처리 피처를 붙이기보다 별도의 복사본/파생 부품에서 후처리하는 것이 적합하다. 규칙은 `AX_`가 아닌 피처를 발견하면 재구성을 거부한다. 실패 시 재구성 트랜잭션만 되돌리고, 그 전에 사용자가 바꾼 매개변수는 되돌리지 않는다. 이전 수치로 복구하거나 올바른 수치로 수정하여 다시 규칙을 실행한 뒤 내보낸다. 수동으로 이름을 `AX_`로 바꾼 피처를 생성 부품 안에 추가하지 않는다.

JSON은 최초 생성 때 읽는 입력이고, 생성 후에는 각 IPT의 User Parameters가 해당 부품의 입력이다. IPT 수정값이 JSON에 역으로 저장되거나 다른 IPT에 자동 동기화되지는 않는다. 두 환경을 같은 조건으로 비교하려면 같은 수치를 적용한다.

## 형상 근거와 모델링 가정

기존 `/workspace/auxetic-3d/model_auxetic.py`, STEP/STL 및 ZIP이 존재함을 확인하고 기존 생성 코드를 `cad_core.py`로 활용했다. 제공 PDF에서 추출해 보관한 **Fig. 2와 S1–S4를 다시 직접 확인**했다. 형상은 general 3D re-entrant이고 Type III를 제거하지 않았다.

- D 꼭짓점 8개: (±b, ±b, ±b).
- 면 안쪽 절점 6개: 각 축 ±a 위치. Type II 4개가 각 절점에서 해당 큐브 면의 D 4개로 연결.
- 외부 끝점 6개: 각 축 ±(a+l₁) 위치. 면 안쪽 절점과 Type I로 연결.
- 모서리 중간 절점 12개: (0,±c,±c)의 좌표 순열. 원래 모서리의 양쪽 D에서 Type III로 연결.
- 총 32절점, 54부재: Type I 6개 + Type II 24개 + Type III 24개.
- 각 축 피치 L=2(a+l₁)로 반복하며, 인접 Type I 끝점의 원형 면 전체에서 접합.

논문에서 직접 확인한 값은 θ=φ=22.5°, l₁=b, 시편 외곽 크기 77.1 mm, 동일 반지름 및 상대밀도 조건들이다. b와 l₁/l₂/l₃의 수치, 직경은 그 조건과 식 (1)에서 계산한 값이며 직접 치수표에 보고된 값으로 표현하지 않는다. 배율, JSON 방식, iLogic 재구성 방식은 구현상 선택이다.

접합부는 중심선 끝점까지의 유한 원기둥을 합친 형상이다. 논문 그림으로 특정 필렛 반지름을 확인하지 못했으므로 별도 구/필렛을 넣지 않았다. 중심선 연결과 기본 기하 조건의 재현이며 원저자 SolidWorks 접합면의 완전한 복제는 아니다. 기본 명목 μ=0.10은 부재 체적을 중복 합산한 값이고, 결합 후 실제 체적비는 약 0.08352436이다. 직경을 독립 변수로 바꾸면 μ는 자동으로 고정되지 않는다.

자세한 유도와 Fig. 2 절점군 대응은 `GEOMETRY_REFERENCE_KO.md`에 있다. 이 파일은 이전 작업의 기하 설명을 보존한 문서이며, 실행 경로·입력 인터페이스에 대해서는 현재 안내를 따른다.

## 실제 검증 결과와 미검증 범위

| 항목 | 기본 | 변경 예시 |
|---|---:|---:|
| θ / φ | 22.5° / 22.5° | 20° / 25° |
| 기준 직경 / 배율 | 5.581566 mm / 1 | 5 mm / 0.5 |
| 실제 직경 | 5.581566 mm | 2.5 mm |
| 셀 피치 | 77.1 mm | 40.713289 mm |
| 반복 크기 | 154.2 mm 각 변 | 81.426578 mm 각 변 |
| STEP 재읽기 솔리드 수: 단위 셀 / 격자 | 1 / 1 | 1 / 1 |
| STEP 형상 유효성 | 통과 | 통과 |
| 격자 내부 경계 접합 수 | 12 | 12 |
| 비접합 부재의 최소 보수적 간격 | 8.218084 mm | 4.072315 mm |
| STL 열린/비다양체 모서리 | 0 / 0 | 0 / 0 |

두 조건의 4개 STEP을 실제로 내보내고 다시 읽었다. 간섭은 부재를 감싸는 캡슐의 최소 간격으로 보수적으로 검사하며, 공유 절점은 의도된 접합이므로 제외한다. 최종 단일 솔리드와 격자 체적 합계도 검사했다. 유효하지 않은 조합 및 배율/반복 경계 관련 자동 검사 10개가 통과했다.

실행 환경: Python 3.12.14, CadQuery 2.7.0, cadquery-ocp 7.8.1.1.post1, NumPy 2.3.5, Matplotlib 3.10.8, Pillow 12.3.0. 상세는 각 결과의 `environment.json`에 있다.

**Inventor 규칙의 컴파일·실행, 실제 IPT 저장·재열기, Inventor에서 변수 변경 후 재생성, ANSYS 가져오기는 검증하지 않았다.** 성공했다고 표시하지 않으며, 실제 생성한 CAD 결과는 CadQuery 경로의 STEP/STL이다. 논문 재료는 PLA이고, 이 작업은 TPU용 형상 후보 제작까지다. y 인장에 따른 x·z 팽창, 대변형 잠김, 출력 안정성, 슬리브 착용 성능은 해석/실험하지 않았다.
