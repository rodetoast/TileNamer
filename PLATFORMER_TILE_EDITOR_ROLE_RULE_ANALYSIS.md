# Platformer Tile Editor v1.0.2 Role / Bridge / Resolver Priority 재분석

분석일: 2026-08-21  
분석 대상: `Platformer.Tile.Editor.v1.0.2`, `타일샘플`, TileNamer v0.1.6 미커밋 상태  
분석 방식: 기존 보고서 재검토, Unity managed assembly metadata/IL, 순수 static resolver 호출,
manifest, PNG 크기, Unity `.meta` sprite layout의 읽기 전용 교차 검증

## 1. 결론 요약

가장 중요한 결론은 다음과 같다.

1. Solid Bridge는 “긴 hole” 자체를 보고 고르는 role이 아니다.
2. Solid가 참조하는 `PlatformAutoTile`이 있고, 좌우의 호환 Terrain cell이
   `top=false && bottom=false`라 Platform 표현으로 위임될 때
   `leftBridge/rightBridge` 연결이 생긴다.
3. 이 bridge bit가 생기면 해당 방향의 일반 cardinal 연결은 강제로 false가 되고,
   일반 `Left/Right/corner` 대신 대응 Bridge role이 즉시 선택된다.
4. 1×1 Bridge role 판정은 8-neighbor와 좌우 bridge bit로 끝난다. cavity 폭을 세거나
   5×3 장거리 topology를 요구하지 않는다. 단 bridge bit는 단순 occupancy가 아니라
   연결된 Auto Tile identity와 Platform 위임 여부를 포함하는 의미론적 상태다.
5. Bridge PNG는 1×1일 수도, Solid anchor + Platform cell의 2×1 pattern일 수도 있다.
   role 판정과 multi-cell candidate 선택은 서로 다른 단계다.
6. Reference의 Solid 종합 sample은 Top/Middle/Bottom의 좌우 Bridge 6종을 모두
   의도적으로 발생시키는 topology다.
7. 현재 TileNamer resolver에는 linked Platform 관계, Platform 위임,
   `leftBridge/rightBridge`, Bridge role 분기가 모두 없다. 따라서 같은 sample에서
   Bridge 6종과 Platform strip 9칸을 전부 일반 Solid role로 잘못 처리한다.

## 2. Evidence 등급

| 등급 | 의미 |
|---|---|
| Confirmed by code | `SP.PlatformerTiles.dll` metadata/IL 또는 static method 직접 호출로 확인 |
| Confirmed by serialized data | `.platformertileset`, Unity `.meta`에서 확인 |
| Confirmed by sample asset | 실제 PNG 이름·크기·분할 sprite에서 확인 |
| Strong inference | 여러 confirmed 근거가 일치하지만 실제 GUI runtime 캡처는 하지 않음 |
| Unknown | 현재 정적 자료만으로 확정 불가 |

## 3. Reference Resolver Architecture

### 3.1 최상위 순서

`TerrainAutoTile.ResolveTile(position, tilemap)`의 실제 IL 순서는 다음과 같다.

1. 현재 Terrain cell이 `ShouldUsePlatformAutoTile(position)`인지 검사한다.
2. Platform mode라면 왼쪽 Terrain anchor의 horizontal Bridge multi-cell pattern을 검사한다.
3. 없으면 오른쪽 Terrain anchor의 horizontal Bridge multi-cell pattern을 검사한다.
4. 둘 다 없으면 연결된 `PlatformAutoTile.ResolveTile()`로 위임한다.
5. Platform mode가 아니면 `ResolveTerrainTile()`로 간다.
6. multi-cell pattern이 있으면 outer winner를 먼저, inner winner를 다음으로 찾는다.
7. winner가 있으면 pattern의 현재 cell sprite를 반환한다.
8. winner가 없으면 `ConnectionState`로 단일 role을 계산한다.
9. 해당 role의 single-cell candidate를 좌표 기반 deterministic weight로 고른다.
10. Wall Slash/Backslash pool이 비면 빨간 `Inner` fallback을 사용한다.
11. Bridge pool이 비면 대응 일반 role로 fallback한다.

근거: `ResolveTile`, `ResolveTerrainTile`, `ResolvePatternTile`,
`TryGetBridgePatternHorizontalTile`, `TryFindWinningPattern` IL.

### 3.2 ConnectionState

실제 state는 10개의 boolean이다.

```text
LT T RT
 L   R
LB B RB

leftBridge, rightBridge
```

Solid일 때만 좌우 bridge bit를 계산한다. Wall에서는 두 bit가 항상 false다.

`ConnectionState` 생성자의 중요한 순서:

```text
leftBridge  = IsBridgeConnected(left)
rightBridge = IsBridgeConnected(right)
left  = !leftBridge  && IsConnected(left)
right = !rightBridge && IsConnected(right)
```

즉 같은 방향이 Bridge로 판정되면 일반 cardinal 연결은 동시에 true가 될 수 없다.

## 4. Platform 위임과 Bridge 연결

### 4.1 Platform mode

`TerrainAutoTile.ShouldUsePlatformAutoTile(hasTop, hasBottom)`의 static 결과는 정확히:

```text
!hasTop && !hasBottom
```

이다. 연결된 `platformAutoTile`이 존재해야 실제 runtime 위임이 가능하다.

따라서 1-cell 높이의 가로 strip에서 각 Terrain cell의 위·아래가 모두 비어 있으면
그 cell은 Solid sprite가 아니라 연결된 Platform sprite로 표시된다.

### 4.2 BridgeConnected의 의미

`IsBridgeConnected(neighbor)`는 단순히 “옆이 occupied”인지 묻지 않는다.

- 이 Terrain이 포함하는 Platform pattern cell인 `TileAsset`, 또는
- 자신과 같거나 selection을 공유하는 호환 `TerrainAutoTile`이면서
  그 neighbor 위치가 Platform mode인 경우

에 true가 된다.

따라서 Bridge는 raw binary occupancy만으로 완전히 정의할 수 없다.
같은 3×3 모양이어도 다른 Auto Tile GUID이거나 연결된 Platform reference가 없으면
Bridge가 아닐 수 있다.

근거: `ConnectionState` constructor 및 `IsBridgeConnected` IL.  
등급: Confirmed by code.

## 5. Solid Role Atlas

다음 표의 `L/R`은 bridge suppression이 적용된 ConnectionState 값이다.

| Role | Required connected | Required empty | 추가 조건 | local priority |
|---|---|---|---|---:|
| Inner | T,L,R,B,LT,RT,LB,RB | - | - | 마지막 |
| Top | L,R | T | - | outer top branch |
| Bottom | T,L,R | B | - | outer bottom branch |
| Left | T,R,B | L | leftBridge=false | side branch |
| Right | T,L,B | R | rightBridge=false | side branch |
| LeftTop | R | T,L | leftBridge=false | first outer corner |
| RightTop | L | T,R | rightBridge=false | second outer corner |
| LeftBottom | T,R | B,L | leftBridge=false | first bottom corner |
| RightBottom | T,L | B,R | rightBridge=false | second bottom corner |
| InnerRightBottom | T,L,R,B | LT | ordinary inner-corner priority 1 |
| InnerLeftBottom | T,L,R,B,LT | RT | ordinary inner-corner priority 2 |
| InnerRightTop | T,L,R,B,LT,RT | LB | ordinary inner-corner priority 3 |
| InnerLeftTop | T,L,R,B,LT,RT,LB | RB | ordinary inner-corner priority 4 |
| LeftTopBridge | R optional | T,L | leftBridge=true | Bridge override |
| RightTopBridge | L | T,R | rightBridge=true | Bridge override |
| LeftBridge | T,R optional,B | L | leftBridge=true | Bridge override |
| RightBridge | T,L,B | R | rightBridge=true | Bridge override |
| LeftBottomBridge | T,R optional | B,L | leftBridge=true | Bridge override |
| RightBottomBridge | T,L | B,R | rightBridge=true | Bridge override |

`optional`은 static resolver가 실제로 반대편 cardinal을 요구하지 않는다는 뜻이다.
일반적인 strip endpoint에서는 반대편이 연결돼 있지만, 분기 자체의 필수값은 아니다.

### 5.1 정확한 outer 분기 순서

```text
if !T:
    if !L: LeftTopBridge if leftBridge else LeftTop
    if !R: RightTopBridge if rightBridge else RightTop
    Top
elif !B:
    if !L: LeftBottomBridge if leftBridge else LeftBottom
    if !R: RightBottomBridge if rightBridge else RightBottom
    Bottom
elif !L:
    LeftBridge if leftBridge else Left
elif !R:
    RightBridge if rightBridge else Right
else:
    inner diagonal rules
```

왼쪽 분기가 오른쪽보다 먼저이므로 비정상적으로 양쪽 bridge bit가 동시에 true인
합성 state에서는 Left 계열이 먼저 선택된다.

## 6. Bridge Deep Dive

Legend:

```text
C = 현재 Solid anchor
P = 같은/호환 Terrain cell이지만 linked Platform으로 렌더되는 cell
# = connected Terrain
. = empty
? = don't care
```

### 6.1 LeftTopBridge

```text
. . ?
P C ?
. ? ?
```

- current top empty
- left neighbor가 Platform mode
- left neighbor의 top/bottom이 비어 있음
- 일반 `LeftTop`보다 Bridge variant가 즉시 우선
- Chapter1: 32×32
- Chapter2: 64×32, `P C`, anchor C, Platform offset `(-1,0)`

### 6.2 RightTopBridge

```text
? . .
? C P
? ? .
```

- current top empty
- right neighbor가 Platform mode
- Chapter1: 32×32
- Chapter2: 64×32, `C P`, Platform offset `(+1,0)`

### 6.3 LeftBridge

```text
. # ?
P C ?
. # ?
```

- current top/bottom connected
- left neighbor가 Platform mode
- Chapter1: 32×32
- Chapter2: 64×32, `P C`

### 6.4 RightBridge

```text
? # .
? C P
? # .
```

- current top/bottom connected
- right neighbor가 Platform mode
- Chapter1: 32×32
- Chapter2: 64×32, `C P`

### 6.5 LeftBottomBridge

```text
. # ?
P C ?
. . ?
```

- current top connected, bottom empty
- left neighbor가 Platform mode
- Chapter1: 32×32
- Chapter2: 64×32, `P C`

### 6.6 RightBottomBridge

```text
? # .
? C P
? . .
```

- current top connected, bottom empty
- right neighbor가 Platform mode
- Chapter1: 32×32
- Chapter2: 64×32, `C P`

### 6.7 3×3인가 extended pattern인가

정확한 답은 두 단계로 나뉜다.

- Role 판정: 3×3 이웃 + 좌우 semantic bridge bit로 충분하다.
- Bridge bit: 인접 Terrain의 top/bottom, Auto Tile compatibility, `platformGuid`를 본다.
- 2×1 candidate: pattern footprint 전체의 cell type과 overlap winner를 추가 검사한다.

따라서 “cavity width를 세는 5×3 Bridge role matcher”는 없다. 그러나 순수한 8-bit
occupancy lookup도 아니다.

## 7. Bridge Multi-cell / Candidate 관계

샘플에서 확인된 모든 Bridge candidate는 `_00` 하나뿐이다.

| Sample | 6개 Bridge PNG 크기 | 의미 |
|---|---:|---|
| Chapter1 | 모두 32×32 | Bridge role의 single-cell candidate |
| Chapter2 | 모두 64×32 | Solid anchor + Platform cell 2×1 pattern |

Chapter2 Unity `.meta` sprite layout:

- Left 계열: 첫 32px cell은 Platform collider, 둘째 cell은 Solid Bridge collider (`P C`).
- Right 계열: 첫 cell은 Solid Bridge collider, 둘째 cell은 Platform collider (`C P`).

같은 role 안에서 candidate별 크기가 다른 사례는 제공된 샘플에는 없다. 엔진의
`TileSet<T>`는 single-cell과 여러 multi-cell pattern weight를 같은 role pool에서
선택할 수 있으므로 구조상 혼합은 지원하지만, 실제 `_00`/`_01` 크기 혼합은 Unknown이다.

candidate 선택 전에 role이 먼저 결정된다. 그 role pool 안에서 single candidate와
valid multi-cell patterns의 weight를 합쳐 좌표 hash로 선택한다. multi-cell pattern이
선택되면 모든 offset의 role/Platform-cell 적합성과 overlap winner를 검사한다.

## 8. Resolver Priority

### 8.1 Bridge와 일반 role

Bridge bit가 true인 방향은 ordinary cardinal이 false로 마스킹되고, 같은 outer branch에서
Bridge enum을 먼저 반환한다. 따라서 Bridge가 일반 `Top/Left/corner` 뒤에 fallback으로
검사되는 구조가 아니다. Bridge가 local role override다.

### 8.2 Pattern winner

`ResolvePatternTile`은 outer pattern을 먼저 찾고 inner pattern을 다음에 찾는다.
겹치는 outer pattern의 `GetOuterPriority` 값:

| Pattern anchor role | Priority |
|---|---:|
| LeftTopBridge, RightTopBridge, LeftBottomBridge, RightBottomBridge | 3 |
| LeftTop, RightTop, LeftBottom, RightBottom | 2 |
| LeftBridge, RightBridge | 1 |
| 기타 | 0 |

동률이면 다음 순서로 winner를 비교한다.

1. 더 많은 cell을 덮는 pattern
2. deterministic candidate hash
3. TileType enum 값
4. anchor y
5. anchor x

inner pattern은 winning outer와 겹치면 탈락한다.

## 9. Solid 종합 Sample의 실제 Bridge 구조

Reference와 TileNamer가 사용하는 논리 map:

```text
###################
##...##############
###########.#######
##...##############
###################
```

`x=2..4`를 보면 다음 세 strip이 있다.

- y=0: 위는 map 밖, 아래 y=1은 empty → Platform mode
- y=2: 위 y=1과 아래 y=3이 empty → Platform mode
- y=4: 위 y=3은 empty, 아래는 map 밖 → Platform mode

각 strip의 양끝 x=1,5가 Bridge anchor가 된다.

```text
y=0: ... RightTopBridge | Platform ×3 | LeftTopBridge ...
y=2: ... RightBridge    | Platform ×3 | LeftBridge    ...
y=4: ... RightBottomBridge | Platform ×3 | LeftBottomBridge ...
```

즉 이 sample은 Bridge 6종을 한 번에 검증하도록 만들어졌다.

## 10. TileNamer와 Reference 좌표 비교

| Coord | Current TileNamer | Reference expected |
|---|---|---|
| (1,0) | Solid_Top | Solid_RightTopBridge |
| (2,0) | Solid_Top | Platform_Center |
| (3,0) | Solid_Top | Platform_Center |
| (4,0) | Solid_Top | Platform_Center |
| (5,0) | Solid_Top | Solid_LeftTopBridge |
| (1,2) | Solid_InnerLeftBottom | Solid_RightBridge |
| (2,2) | Solid_Top | Platform_Center |
| (3,2) | Solid_Top | Platform_Center |
| (4,2) | Solid_Top | Platform_Center |
| (5,2) | Solid_InnerRightBottom | Solid_LeftBridge |
| (1,4) | Solid_Bottom | Solid_RightBottomBridge |
| (2,4) | Solid_Top | Platform_Center |
| (3,4) | Solid_Top | Platform_Center |
| (4,4) | Solid_Top | Platform_Center |
| (5,4) | Solid_Bottom | Solid_LeftBottomBridge |

Bridge 의심 구간에서 총 15개 cell이 다르다.

## 11. Thin Strip / Narrow Cavity

### 11.1 완전히 독립된 1-cell horizontal strip

```text
.........
#########
.........
```

전 cell이 위·아래 연결이 없으므로 linked Platform으로 위임된다. 결과는 일반적인
Platform sequence `LeftEnd, Center…, RightEnd`다. 양끝에 non-platform Solid anchor가
없으므로 Solid Bridge role은 생기지 않는다.

### 11.2 두 hole 사이의 1-cell strip

```text
##########
##......##
##########
##......##
##########
```

가운데 row의 hole 사이 구간은 Platform mode가 되고 양 끝의 두 Solid anchor는
`RightBridge`와 `LeftBridge`가 된다. 위·아래 outer row도 map 밖과 hole 사이에 놓여
각각 TopBridge/BottomBridge pair가 된다.

### 11.3 두꺼운 Solid 내부의 cavity

```text
############
############
##........##
##........##
############
############
```

cavity 바로 위 row는 위쪽 Solid가 연결되고, 바로 아래 row는 아래쪽 Solid가 연결된다.
`top=false && bottom=false`를 만족하지 않으므로 Platform mode가 아니며 Bridge도 아니다.
일반 Top/Bottom/side/corner role을 사용한다.

따라서 hole의 길이나 높이 자체가 Bridge trigger가 아니다.

### 11.4 Vertical Bridge

ConnectionState에는 `leftBridge/rightBridge`만 있고 top/bottom Bridge bit가 없다.
Platform resolver도 수평 endpoint만 판정한다. Reference Bridge는 horizontal-only다.

## 12. Platform Rules

static `PlatformAutoTile.ResolveTileType(L,R,LBridge,RBridge)` 16개 조합을 직접 호출했다.

- `!L && R && !LBridge && !RBridge` → LeftEnd
- `L && !R && !LBridge && !RBridge` → RightEnd
- 나머지 모든 조합 → Center

따라서:

| 길이 | 결과 |
|---|---|
| 1 | Center |
| 2 | LeftEnd, RightEnd |
| 3+ | LeftEnd, Center…, RightEnd |

Bridge 연결이 하나라도 있으면 endpoint가 아니라 Center다.

## 13. Wall Rules

Wall은 cardinal/inner 기본 resolver를 Solid와 공유하지만 Wall끼리만 연결되고
bridge bit는 계산하지 않는다.

모든 T,L,R,B가 connected일 때 대각선 순서:

1. LT=1, RT=0, LB=0, RB=1 → InnerBackslash (`╲` 빈 대각선)
2. LT=0, RT=1, LB=1, RB=0 → InnerSlash (`╱` 빈 대각선)
3. LT=0 → InnerRightBottom
4. RT=0 → InnerLeftBottom
5. LB=0 → InnerRightTop
6. RB=0 → InnerLeftTop
7. 모두 connected → Inner

Slash/Backslash pool이 비면 일반 Bridge fallback과 달리 빨간 `Inner` diagnostic을 쓴다.

## 14. Naming Direction

- Outer `Top/Left/Right/Bottom`: 노출된 empty 방향.
- `LeftTop` 등 convex corner: 노출된 두 방향.
- Bridge의 Left/Right: Platform strip이 붙는 방향.
  - `RightBridge`는 Solid anchor 오른쪽에 Platform이 있다.
  - `LeftBridge`는 Solid anchor 왼쪽에 Platform이 있다.
- Bridge의 Top/Bottom:
  - TopBridge: anchor top이 empty.
  - BottomBridge: anchor bottom이 empty이고 top은 connected.
  - plain Bridge: anchor top/bottom이 모두 connected.
- Inner names는 비어 있는 diagonal 자체와 반대쪽 artwork-facing corner 이름이다.
  - LT empty → InnerRightBottom
  - RT empty → InnerLeftBottom
  - LB empty → InnerRightTop
  - RB empty → InnerLeftTop

좌표는 screen-space로 y가 아래로 증가한다.

## 15. Reference Evidence

### Confirmed by code

- 10-bit `ConnectionState`
- Solid에서만 bridge bit 계산
- bridge 방향의 ordinary cardinal suppression
- 정확한 6개 Bridge role 분기
- `ShouldUsePlatformAutoTile = !top && !bottom`
- Platform mode의 Bridge pattern → Platform fallback 순서
- multi-cell outer/inner search와 winner priority
- Bridge fallback mapping
- Wall Slash/Backslash mask
- Platform 16개 state 결과

### Confirmed by serialized data

- Chapter1/2 Solid Auto Tile 모두 실제 `platformGuid` 보유
- Bridge 6종 모두 selection에 weight 100으로 포함
- Wall에는 platform reference가 없음
- Chapter2 `.meta`에 64×32 Bridge PNG가 두 개 32×32 sprite로 분할됨

### Confirmed by sample asset

- Chapter1 Bridge 6종: 모두 32×32
- Chapter2 Bridge 6종: 모두 64×32
- Left 계열 `P C`, Right 계열 `C P` collider/layout

### Strong inference

- Solid 종합 sample의 15개 mismatch 및 6개 Bridge sequence. static method와 IL로
  결과가 결정적이지만 실제 Reference GUI screenshot capture는 이번 분석에서 생략했다.

### Unknown

- 한 role pool에서 서로 다른 크기의 `_00`, `_01`을 실제 제품 데이터가 사용하는 사례
- 사용자 정의 Auto Tile 관계에서 양쪽 bridge bit가 동시에 true인 비정상 topology의 시각 결과

## 16. Current TileNamer Resolver Audit

현재 `src/tilenamer/placement.py`는 다음 구조다.

- Solid/Wall을 동일 occupancy set의 8-neighbor로 판정
- Platform은 별도 family sample에서 좌우 occupancy만 판정
- Auto Tile entity 또는 Solid→Platform reference 없음
- `ShouldUsePlatformAutoTile` 없음
- `leftBridge/rightBridge` 없음
- Bridge role을 반환하는 분기 없음
- multi-cell을 cell별 expected role/platform-cell pattern이 아니라 단순 footprint로 처리

현재 Solid 종합 Pattern 데이터 자체는 Reference sample과 일치한다. 문제는 Pattern이 아니라
resolver에 Platform 위임과 Bridge connection 단계가 없는 것이다.

정확한 버그를 한 문장으로 표현하면:

> TileNamer는 모든 `#`를 끝까지 Solid occupancy로만 해석하므로, 위·아래가 모두 빈
> Terrain cell을 linked Platform으로 위임하지 못하고 그 옆 Solid cell에
> leftBridge/rightBridge bit도 만들지 못해 Bridge 6종이 절대로 선택되지 않는다.

## 17. 다음 구현에 필요한 최소 변경

Resolver 변경은 별도 구현 작업에서 수행해야 한다.

1. Preview-only Solid→Platform 연결 정책을 명시한다.
2. 각 Solid logical cell에 `ShouldUsePlatform = !top && !bottom`을 계산한다.
3. Platform-mode cell은 Platform resolver로 보낸다.
4. 인접 호환 Terrain의 Platform mode로 `leftBridge/rightBridge`를 만든다.
5. Bridge 방향 ordinary cardinal을 suppress한 10-bit role resolver를 구현한다.
6. Bridge pool이 없을 때 6개 공식 fallback mapping을 적용한다.
7. 2×1 Bridge candidate를 anchor-relative Platform/Solid cell pattern으로 해석한다.
8. outer pattern priority 3/2/1/0과 overlap winner를 단계적으로 구현한다.
9. 현재 Solid 종합 sample의 위 15개 좌표를 regression fixture로 고정한다.
10. Chapter1 1×1 Bridge와 Chapter2 2×1 Bridge를 별도 fixture로 검증한다.

현재 TileNamer project schema를 즉시 바꾸지 않고 Preview 전용 연결 정책으로 시작할 수 있으나,
Reference와 완전히 같게 하려면 Auto Tile identity와 Solid→Platform reference가 필요하다.

## 18. Suggested Preview Patterns

현재 `종합`은 이미 Bridge 6종을 모두 발생시키므로 제거하거나 바꿀 필요가 없다.
검수 가독성을 위해 다음 전용 Pattern을 후속으로 추가할 수 있다.

### Bridge 6종

```text
##########
##......##
##########
##......##
##########
```

### 독립 Platform 위임 strip

```text
.........
.#######.
.........
```

### Bridge가 아니어야 하는 두꺼운 cavity

```text
############
############
##........##
##........##
############
############
```

## 19. 별도 UX 후속: Opaque Logical Field

이 항목은 Auto Tile resolver와 별개의 Preview 표시 문제다.

다음 구현 단계에서 Placement Preview는 Pattern bounds 전체를 Theme-aware opaque neutral
field로 먼저 채우고 그 위에 Tile, Missing, Grid, Hover를 같은 transform으로 그려야 한다.

필수 정책:

1. logical empty/cavity는 alpha 255의 Preview background.
2. Pattern 밖 workspace와 Pattern field는 미세하게 구분.
3. Tile RGBA는 field 위에 정상 alpha blend.
4. irregular assignment hole은 field background가 보이되 hit target은 아님.
5. Missing placeholder는 neutral empty와 다른 warning 표현 유지.
6. Grid ON이면 empty cell 위에도 logical grid 표시.
7. Main Alpha preference, source PNG, thumbnail, export alpha는 변경하지 않음.

후속 테스트:

- empty cell center alpha=255
- 반투명 tile의 background composite 색상
- irregular hole pixel=field background
- Missing pixel/outline이 empty와 다름
- empty click/hover locate 없음
- Fit/Zoom/Pan에서 field/Tile/Grid transform 일치

## 20. 다섯 핵심 질문에 대한 답

### Q1. 긴 hole 주변이 왜 Bridge인가?

hole 길이 때문이 아니다. 두 hole 사이 또는 map 외곽과 hole 사이의 1-cell strip이
위·아래 Terrain 연결을 모두 잃어 linked Platform으로 위임되고, 그 strip 옆의 Solid
anchor가 bridge connection을 받기 때문이다. 두꺼운 Solid 내부 cavity는 Bridge가 아닐 수 있다.

### Q2. Bridge 6종 topology는?

좌/우 linked-Platform neighbor + anchor의 vertical state 조합이다.

- top empty → Left/RightTopBridge
- top/bottom connected → Left/RightBridge
- top connected, bottom empty → Left/RightBottomBridge

### Q3. 일반 edge보다 먼저인가?

그렇다. bridge bit가 ordinary cardinal을 false로 만들고 같은 outer branch에서 Bridge
variant를 즉시 반환한다. multi-cell overlap에서도 Bridge corner priority는 3으로 가장 높다.

### Q4. 3×3인가 extended인가?

role은 3×3 + semantic bridge bit다. cavity 폭을 보는 extended role matcher는 없다.
2×1 PNG candidate를 사용할 때만 별도의 multi-cell pattern validation이 추가된다.

### Q5. TileNamer의 정확한 차이는?

linked Platform 위임과 bridge bit 생성 단계가 전혀 없고, 현재 8-neighbor 함수는 Bridge
enum을 반환할 수 없다. Pattern 우선순위 문제가 생기기 전 단계에서 Bridge가 누락된다.

## 21. Read-only 무결성 확인

분석 전후 동일한 방식으로 각 tree의 `relative path|length|file SHA256` 목록을 만들고
그 UTF-8 문자열의 SHA256을 계산했다.

| Tree | Files | Bytes | Fingerprint |
|---|---:|---:|---|
| Platformer.Tile.Editor.v1.0.2 | 171 | 95,224,068 | `2D667F56CE062A55D7B49DCCDB685A207B97E2ED395E1BDF70F7E9C2EB19A54D` |
| 타일샘플 | 204 | 471,566 | `691D52DFAB5FE42990EDFBC6C9B05AF7969E8D852FE7AE5A11E1F74C083FE8A1` |

두 fingerprint는 분석 전후 동일하다. Reference 프로그램은 실행하지 않았고,
Reference/샘플의 수정·저장·이름 변경·이동·삭제는 없었다. TileNamer source, test,
version, project schema도 이번 분석에서 수정하지 않았다.
