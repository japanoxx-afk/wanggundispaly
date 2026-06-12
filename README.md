# wanggundispaly

태조왕건 `WangGun.exe` / `iCARUS.dll` 해상도 패치 도구입니다.

## 확인한 내용

- 원본 게임은 `800x600` 값을 EXE 내부에 하드코딩해서 `_iCARUS_Init@32`에 넘깁니다.
- 이 도구는 해당 값과 관련 창/전역 해상도 값, 그리고 하단 UI를 제외한 게임 플레이 영역 높이(`기본 449`)를 원하는 해상도에 맞춰 바꿉니다.
- `--scale` 모드는 게임 내부 렌더링을 원본 `800x600`으로 유지하고, `iCARUS.dll`의 최종 DirectDraw 복사를 원하는 출력 해상도로 확대합니다.
- 원본 EXE/DLL은 자동으로 `.bak` 백업을 만든 뒤 수정합니다.

## 4K 모니터 권장 모드

4K 화면에 맞추려면 이 방식을 먼저 쓰세요. 내부 게임 화면은 `800x600`으로 안정적으로 유지하고, 마지막 출력만 `3840x2160`으로 확대합니다.

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\patch_wanggun_resolution.py 3840 2160 --scale
```

적용 전 확인만 하려면:

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\patch_wanggun_resolution.py 3840 2160 --scale --dry-run
```

## 내부 해상도 확장 모드

`--scale` 없이 실행하면 게임 내부 해상도 상수를 직접 바꿉니다. 오래된 RTS라 검은 여백이 생기거나 UI/마우스 좌표가 맞지 않을 수 있습니다. 먼저 4:3 해상도를 권장합니다.

- `1024 768`
- `1280 960`
- `1600 1200`

와이드 해상도도 입력은 가능하지만, 오래된 RTS라 UI/맵/마우스 좌표 일부가 `800x600` 전제를 가질 수 있습니다.

## 검은 여백이 보일 때

초기 버전 도구로 패치한 경우 화면 표면은 커졌지만 게임 플레이 영역 높이 `449`가 그대로 남아 검은 여백이 생길 수 있습니다. 최신 도구로 같은 해상도를 다시 실행하면 이 값을 `height - 151`로 보정합니다.

## 사용법

PowerShell에서 이 저장소 폴더로 이동한 뒤 실행합니다.

```powershell
python .\patch_wanggun_resolution.py 1024 768
```

Python 경로 문제가 있으면 Codex 번들 Python을 직접 사용할 수 있습니다.

```powershell
& "$env:USERPROFILE\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe" .\patch_wanggun_resolution.py 1024 768
```

다른 설치 경로를 쓰는 경우:

```powershell
python .\patch_wanggun_resolution.py 1280 960 --exe "C:\Program Files\태조왕건\WangGun.exe"
```

패치 가능 여부만 확인:

```powershell
python .\patch_wanggun_resolution.py 1024 768 --dry-run
```

원복:

```powershell
Copy-Item "C:\Program Files\태조왕건\WangGun.exe.bak" "C:\Program Files\태조왕건\WangGun.exe" -Force
Copy-Item "C:\Program Files\태조왕건\iCARUS.dll.bak" "C:\Program Files\태조왕건\iCARUS.dll" -Force
```

## 현재 지원 대상

- `WangGun.exe`
- SHA256: `5E80AAD54982DDF8CAFBB367B70E65B9438B093ADE414F36B3959E9E8B08E5FE`
- `iCARUS.dll`
- SHA256: `972ED0742EFD966852F93503AA4B7DB9B7532A34B54E3ED0C9BB56B9942EB6A1`

다른 버전의 EXE는 기본적으로 막습니다. 강제로 시도하려면 `--force`를 사용하세요.
한 번 패치한 EXE는 `WangGun.exe.bak` 백업이 남아 있으면 같은 명령으로 다시 다른 해상도로 바꿀 수 있습니다.
