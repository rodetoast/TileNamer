# Platformer Tile Editor v1.0.2 오토 타일·시험 배치 심층 분석

분석일: 2026-08-21  
분석 방식: 로컬 문서, 샘플 manifest/PNG, Unity managed assembly metadata 및 순수 정적 resolver 메서드의 읽기 전용 조사  
비분석 범위: TileNamer 구현 변경, 원본 프로그램 실행에 따른 설정 생성, 원본 데이터 저장

## 1. Reference 위치 / 기술 스택

- Reference 프로그램: `C:\Users\SOUTHPAW GAMES\Desktop\TileNamer\Platformer.Tile.Editor.v1.0.2`
- 샘플 데이터: `C:\Users\SOUTHPAW GAMES\Desktop\TileNamer\타일샘플`
- 실제 샘플 세트:
  - `C:\Users\SOUTHPAW GAMES\Desktop\TileNamer\타일샘플\타일샘플\Chapter1\Chapter1.platformertileset`
  - `C:\Users\SOUTHPAW GAMES\Desktop\TileNamer\타일샘플\타일샘플\Chapter2\Chapter2.platformertileset`

프로그램은 WPF/WinForms/Qt가 아니라 Unity Mono 데스크톱 빌드다. 근거는 `UnityPlayer.dll`, `UnityCrashHandler64.exe`, `MonoBleedingEdge`, `Platformer Tile Editor_Data`, Unity UIElements/Tilemap assembly와 `data.unity3d`다. 제품 정보는 `SouthpawGames / Platformer Tile Editor`, build GUID는 `bc5f6dfd36244ef6833830d5a164b85e`다.

핵심 제품 assembly는 다음 두 개다.

- `SP.PlatformerTiles.dll`: runtime resolver, importer, manifest, layout, physics
- `SP.PlatformerTileEditor.dll`: editor UI, Sample Preview, 시험 배치, 문서 상태

원본 실행은 하지 않았다. Unity 프로그램 실행은 `Player.log`나 사용자 설정을 생성할 수 있어 “원본·설치 상태에 쓰기 금지”와 충돌할 가능성이 있기 때문이다. 필요한 동작은 side effect가 없는 정적 메서드 호출과 metadata/IL 호출 관계로 확인했다.

## 2. 파일 구조

Reference 폴더는 171개 파일, 95,224,068 bytes다. 주요 구조는 다음과 같다.

```text
Platformer.Tile.Editor.v1.0.2/
├─ Platformer Tile Editor.exe
├─ UnityPlayer.dll
├─ UnityCrashHandler64.exe
├─ D3D12/
├─ MonoBleedingEdge/
├─ Docs/
│  ├─ User guide.md
│  ├─ AI guide.md
│  └─ CLI guide.md
└─ Platformer Tile Editor_Data/
   ├─ data.unity3d
   └─ Managed/
      ├─ SP.PlatformerTiles.dll
      ├─ SP.PlatformerTileEditor.dll
      ├─ UnityEngine.TilemapModule.dll
      ├─ UnityEngine.UIElementsModule.dll
      └─ 기타 Unity/시스템 assembly
```

확장자 기준으로 DLL 142개, config 7개, exe 2개, json 2개, Unity data 1개 등이 있다. 별도 SQLite/CSV 기반의 숨은 타일 DB는 발견되지 않았다. 영속 Auto Tile Set의 SSOT는 샘플에 있는 JSON 형식의 `.platformertileset`이며, PNG는 같은 세트의 `TileImages` 아래에 놓인다.

샘플 폴더는 204개 파일, 471,566 bytes이고 PNG 99개, `.meta` 103개, `.platformertileset` 2개다. Unity importer 결과인 `.meta`도 있으나 editor가 직접 다루는 원본 논리 데이터는 `.platformertileset` + PNG 조합이다.

정적 조사에서 확인한 주요 내부 형식은 다음과 같다.

- `PlatformAutoTile`, `TerrainAutoTile`, `TopSequenceAutoTile`
- `TileResolver`, `TileVariants`, `TileSet<T>`, `TilePattern<T>`
- `TileImageLayout`, `TileImageCell`, `TilePhysics`, `TileDefinition`
- `TileSetManifest`, `AutoTileManifest`, `AutoTileSelectionManifest`
- `AutoTileSamplePreview`, `TrialPlacementView`, `TrialPlacementState`
- `PreviewTileSet`, `PreviewTileSetFactory`, `TilemapPreviewSurface`

## 3. Auto Tile 데이터 모델

구조는 “PNG category 자체가 Auto Tile”이 아니라 다음 두 층이다.

1. 타일 이미지 층: 파일명과 PNG 크기로 role, candidate 번호, 논리 셀 layout, pivot, collider를 만든다.
2. Auto Tile 층: 여러 타일 이미지를 선택해 `Platform`, `Solid`, `Wall`, `TopSequence` 중 하나의 resolver 세트를 만든다.

manifest의 최상위 구조는 다음과 같다.

```json
{
  "formatVersion": 1,
  "displayName": "Chapter2",
  "tiles": [
    {"source": "Solid_Inner_00.png", "type": "SolidInner"}
  ],
  "autoTiles": [
    {
      "guid": "...",
      "name": "Terrain Auto Tile",
      "type": "Solid",
      "platformGuid": "...",
      "selections": [
        {"tile": "Solid_Inner_00", "weight": 100}
      ]
    }
  ]
}
```

Auto Tile별 의미는 다음과 같다.

| type | runtime | 관계 필드 | 역할 |
|---|---|---|---|
| Platform | `PlatformAutoTile` | 없음 | 좌·우 연속성에 따라 LeftEnd/Center/RightEnd 결정 |
| Solid | `TerrainAutoTile(kind=Solid)` | `platformGuid` 선택 가능 | 8방향 지형, Bridge 및 multi-cell pattern 처리 |
| Wall | `TerrainAutoTile(kind=Wall)` | 실사용 platform 연결 없음 | Solid와 기본 지형표를 공유하되 독립 연결 및 대각선 전용 role 사용 |
| TopSequence | `TopSequenceAutoTile` | `terrainGuid`, `requireRepeat` | 가로 구간을 Start + Repeat×N + End로 채움 |

각 selection은 특정 PNG candidate를 pool에 포함시키고 weight를 준다. runtime에서는 role별로 `TileSet<T>` 또는 `TileVariants`가 구성된다. 1×1은 단일 후보 pool, multi-cell은 `TilePattern<T>`로 분리된다.

`TilePattern<T>`의 실제 필드는 `variantIndex`, `weight`, `offsets[]`, `tileTypes[]`, `platformCells[]`, `tiles[]`다. 즉 multi-cell 이미지는 큰 sprite 하나가 아니라, 여러 논리 셀의 sprite와 요구 role을 묶은 패턴이다.

## 4. Neighbor / Rule Resolver

### 4.1 표현 방식

`TerrainAutoTile.ConnectionState`는 다음 10개 boolean을 가진다.

```text
LT T RT
 L   R
LB B RB

leftBridge, rightBridge
```

따라서 기본 terrain 판정은 8-neighbor explicit resolver이고, 좌·우 Platform Bridge 접속 2비트가 추가된다. 단순 4-bit lookup 하나가 아니다. 정적 `ResolveTileType(ConnectionState, Kind)`를 모든 대표 mask에 직접 호출해 아래 표를 복원했다.

표에서 cardinal 순서는 `T L R B`다. 대각선이 role에 영향을 주는 것은 네 cardinal이 모두 연결된 내부 셀일 때다.

| T | L | R | B | 기본 role |
|---:|---:|---:|---:|---|
| 0 | 0 | 0 | 0/1 | LeftTop |
| 0 | 0 | 1 | 0/1 | LeftTop |
| 0 | 1 | 0 | 0/1 | RightTop |
| 0 | 1 | 1 | 0/1 | Top |
| 1 | 0 | 0 | 0 | LeftBottom |
| 1 | 0 | 1 | 0 | LeftBottom |
| 1 | 0 | 0 | 1 | Left |
| 1 | 0 | 1 | 1 | Left |
| 1 | 1 | 0 | 0 | RightBottom |
| 1 | 1 | 0 | 1 | Right |
| 1 | 1 | 1 | 0 | Bottom |
| 1 | 1 | 1 | 1 | 아래 corner 표로 판정 |

고립 셀을 `LeftTop`으로 반환하는 것은 오류가 아니라 이 resolver에 별도 `Isolated` role이 없기 때문이다. 외곽 우선순위에 따라 한 role이 대표가 된다.

네 cardinal이 모두 연결된 경우의 정확한 corner 판정은 다음과 같다.

| LT | RT | LB | RB | Solid | Wall |
|---:|---:|---:|---:|---|---|
| 0 | 0 | 0 | 0 | InnerRightBottom | InnerRightBottom |
| 0 | 0 | 0 | 1 | InnerRightBottom | InnerRightBottom |
| 0 | 0 | 1 | 0 | InnerRightBottom | InnerRightBottom |
| 0 | 0 | 1 | 1 | InnerRightBottom | InnerRightBottom |
| 0 | 1 | 0 | 0 | InnerRightBottom | InnerRightBottom |
| 0 | 1 | 0 | 1 | InnerRightBottom | InnerRightBottom |
| 0 | 1 | 1 | 0 | InnerRightBottom | **InnerSlash** |
| 0 | 1 | 1 | 1 | InnerRightBottom | InnerRightBottom |
| 1 | 0 | 0 | 0 | InnerLeftBottom | InnerLeftBottom |
| 1 | 0 | 0 | 1 | InnerLeftBottom | **InnerBackslash** |
| 1 | 0 | 1 | 0 | InnerLeftBottom | InnerLeftBottom |
| 1 | 0 | 1 | 1 | InnerLeftBottom | InnerLeftBottom |
| 1 | 1 | 0 | 0 | InnerRightTop | InnerRightTop |
| 1 | 1 | 0 | 1 | InnerRightTop | InnerRightTop |
| 1 | 1 | 1 | 0 | InnerLeftTop | InnerLeftTop |
| 1 | 1 | 1 | 1 | Inner | Inner |

이 표에는 명시적 우선순위가 있다. 여러 대각선이 동시에 비어도 모든 inner corner를 한 셀에 합성하지 않고 하나의 role을 고른다. multi-cell 후보가 있으면 별도의 pattern search가 먼저/함께 유효 coverage를 계산한다.

multi-cell 선택과 관련한 runtime cache/검색 구조는 다음과 같다.

- `patternSearchResults`, `selectedPatterns`, `validPatterns`, `winningPatterns`
- outer/inner `PatternCoverage`
- `TryFindWinningPattern`, `IsValid`, `IsWinner`, `OverlapsWinningOuter`
- `HasHigherPriority`, 좌표 기반 `Hash`

외곽 패턴 priority 값도 확인했다.

- 일반 corner: 2
- 좌·우 수직 Bridge: 1
- Bridge corner: 3
- 나머지: 0

따라서 pattern 충돌 시 단순 목록 첫 항목만 쓰지 않고, coverage 유효성·외곽 우선순위·결정적 hash로 winner를 고른다.

## 5. Platform

`PlatformAutoTile.ResolveTileType(hasLeft, hasRight, hasLeftBridge, hasRightBridge)`의 결과는 다음 규칙으로 축약된다.

- 왼쪽이 없고 오른쪽만 연결되며 Bridge 연결도 없으면 `LeftEnd`.
- 오른쪽이 없고 왼쪽만 연결되며 Bridge 연결도 없으면 `RightEnd`.
- 그 외는 `Center`.

따라서 길이에 따른 결과는 다음과 같다.

| 배치 | 결과 |
|---|---|
| 길이 1 | Center |
| 길이 2 | LeftEnd, RightEnd |
| 길이 3+ | LeftEnd, Center…, RightEnd |
| 끊어진 각 단독 셀 | 각각 Center |

Platform 자체 resolver는 위/아래를 보지 않는다. 다만 Solid가 연결된 Platform을 대신 표시하는 조건은 별도다. `TerrainAutoTile.ShouldUsePlatformAutoTile(hasTop, hasBottom)`은 `top=false && bottom=false`일 때만 true다. 즉 Solid/Platform 연결 관계에서 수직 terrain이 없는 가로 통로 셀이 Platform 표현으로 위임될 수 있다.

Bridge boolean이 하나라도 개입하면 단순 endpoint 조건을 깨고 `Center`가 된다. 이는 Platform endpoint sprite 대신 terrain Bridge pattern의 Platform cell과 자연스럽게 연결하기 위한 처리다.

## 6. Solid

Solid role은 점유 셀의 외곽 면과 내부 concave corner를 표현한다.

- `Top/Bottom/Left/Right`: 해당 방향만 노출된 변.
- `LeftTop`, `RightTop`, `LeftBottom`, `RightBottom`: 두 방향이 노출된 convex corner.
- `Inner`: 8방향이 모두 채워진 완전 내부.
- `InnerLeftTop`, `InnerRightTop`, `InnerLeftBottom`, `InnerRightBottom`: cardinal은 모두 차 있지만 해당 대각선이 비어 있는 concave corner.
- Bridge 6종: 노출된 좌/우 변이 연결된 Platform과 만나는 특수 override.

중요한 방향 해석은 role 이름이 “비어 있는 면/corner가 있는 쪽”을 나타낸다는 점이다. 예를 들어 T/L/R/B가 모두 있고 RB만 없으면 `InnerLeftTop`이 아니라 구현상 `InnerLeftTop`이 선택된다. sprite가 메우는 시각적 corner 방향과 빈 이웃 이름을 동일시하면 혼동되므로 위의 실제 mask 표를 SSOT로 사용해야 한다.

Solid는 multi-cell pattern을 지원한다. 확인된 예:

- `Solid_Top` 32×64: `(0,-1)=SolidInner`, anchor `(0,0)=SolidTop`
- `Solid_Top` 64×64: 위쪽 두 셀 `SolidInner`, anchor 행 두 셀 `SolidTop`
- `Solid_Left` 64×64: 왼쪽 열 `SolidLeft`, 오른쪽 열 `SolidInner`

즉 candidate 이미지의 각 32px 조각마다 기대 terrain role이 생성되고, 현재 occupancy가 그 패턴 전체와 맞을 때만 후보가 유효하다.

## 7. Wall / Bridge

### Wall

Wall은 기본 8-neighbor role 표를 Solid와 공유하지만 연결 집합은 별도다. 로컬 `AI guide.md`도 “Wall connects only to Wall”을 명시한다. 따라서 인접 Solid/Platform을 같은 점유로 취급하지 않는다.

두 전용 대각선 role은 정적 resolver에서 정확히 두 mask에서만 나온다. 모든 cardinal은 연결된 상태다.

- `Wall_InnerSlash`: LT와 RB가 비고 RT와 LB가 참. 시각적 빈 대각선은 `╱`.
- `Wall_InnerBackslash`: RT와 LB가 비고 LT와 RB가 참. 시각적 빈 대각선은 `╲`.

해당 pool이 없거나 weight 합이 0이면 Sample Preview에서 빨간 `Inner` fallback으로 오류 상태를 표시한다는 동작이 로컬 가이드에 명시돼 있다. 일반 `TryGetFallbackTileType`은 Bridge 6종만 비-Bridge role로 fallback한다. Slash/Backslash는 일반 fallback 대상이 아니므로 Wall 검증에서 필수 pool이다.

### Bridge

Bridge는 별도 Auto Tile family가 아니라 Solid `TerrainAutoTile` 내부의 선택적 role override다. Solid manifest의 `platformGuid`가 연결할 Platform Auto Tile을 지정한다.

- `LeftTopBridge → LeftTop`
- `RightTopBridge → RightTop`
- `LeftBridge → Left`
- `RightBridge → Right`
- `LeftBottomBridge → LeftBottom`
- `RightBottomBridge → RightBottom`

Bridge pool이 없으면 위 표의 일반 role로 fallback할 수 있다. 대표 64×32 layout에서 `Solid_LeftBridge`는 `(-1,0)=PlatformCenter`, `(0,0)=SolidLeftBridge`이고, `Solid_RightBridge`는 `(0,0)=SolidRightBridge`, `(1,0)=PlatformCenter`다. 즉 Bridge PNG 자체가 Solid anchor와 인접 Platform 논리 셀을 함께 점유하는 2-cell pattern이다.

순수 공용 resolver에 Wall kind와 bridge flag를 인위적으로 넣으면 Bridge enum이 반환되지만, 실제 Wall Auto Tile에는 `platformGuid` 연결을 구성하지 않으므로 정상 runtime 경로에서 Wall Bridge family가 생기는 구조는 아니다.

## 8. Top Sequence

파일명 구조는 다음과 같다.

```text
Solid_TopSequence_<Start|Repeat|End>_<type index>_<candidate index>.png
```

예를 들어 `Solid_TopSequence_Repeat_00_00.png`는 sequence type 00의 Repeat part, candidate 00이다. type 00과 01은 서로 다른 완성 sequence 세트다. 각 Auto Tile manifest는 같은 type index의 Start/Repeat/End를 selection으로 묶고 `terrainGuid`로 호환 Solid Auto Tile을 참조한다.

`TopSequence` runtime 데이터는 `startWidth`, `repeatWidth`, `endWidth`, `height`, 그리고 part별 `TileSet<TerrainTileType>`를 가진다. 가로 연속 구간 폭 W가 다음을 만족할 때만 채울 수 있다.

```text
W = startWidth + repeatWidth × N + endWidth
N >= 0
requireRepeat=true이면 N >= 1
```

정적 호출 예로 start=1, repeat=2, end=1이면 `requireRepeat=false`에서 2,4,6… 셀이 가능하고 최소 2다. true이면 4,6,8…만 가능하고 최소 4다.

Chapter2의 실제 PNG는 type 00 기준 Start 32×100, Repeat 64×103, End 32×100이다. layout은 이를 1×3, 2×3, 1×3 논리 패턴으로 해석한다. Repeat 64×103의 셀은 위 두 행이 `SolidInner`, anchor 행이 `SolidTop`이다. 마지막 행이 39px 높이라 pivot은 `(0.5, 16/39≈0.410)`으로 조정된다. 즉 32의 배수가 아닌 여분 픽셀은 잘라 버리는 것이 아니라 anchor sprite의 시각적 돌출 영역으로 포함한다.

## 9. Candidate / Ratio

`_00`, `_01`은 role의 후보 번호이자 기본 palette/export 순서다. 같은 role pool에 check된 후보가 여러 개 있으면 `weight` 합으로 정규화한다.

```text
확률(candidate i) = weight_i / 같은 pool의 선택된 후보 weight 합
```

UI의 `비율 100 / 100%`는 발생 횟수 제한이나 export 비율이 아니라 이 weight와 정규화 확률이다. 예:

- 후보 1개, weight 100: 총합 100, 확률 100%.
- 후보 2개, 각각 100: 각 50%.
- Chapter2 `Solid_Inner`: 00이 100, 01~08이 각각 5, 총합 140. 00은 약 71.43%, 나머지는 각각 약 3.57%.
- Chapter2 `Platform_Center`: 00~04가 모두 100이므로 각각 20%.

선택은 프레임마다 새 난수를 뽑는 방식이 아니다. `TileVariants.Pick(position)`과 `TileSet.PickSingleCell/PickPattern(position)`은 `TileUtility.GetDistributedValue(Vector3Int, totalWeight)`를 호출한다. 같은 좌표와 같은 pool/weight면 항상 같은 분배값이 나왔다. 예를 들어 max=100에서 `(5,7,0)`은 반복 호출 모두 90이었다. 따라서 결과는 좌표 기반 deterministic weighted selection이다.

checkbox는 candidate의 random pool 참여 여부다. manifest에는 별도 `enabled` boolean이 없고, check된 항목만 `selections[]`에 `{tile, weight}`로 존재한다. 해제는 preview만 숨기는 것도, PNG export를 막는 것도 아니라 해당 Auto Tile 구성에서 selection record를 제거하는 의미다. PNG 자체와 최상위 `tiles[]`는 남을 수 있다.

목록 위/아래 순서는 문서상 Unity Tile Palette 배치 순서에도 영향을 주지만, 실제 runtime variation 선택은 weight와 좌표 hash에 의해 이루어진다.

## 10. 시험 배치

### 최우선 질문에 대한 답

`시험 배치`는 방식 B, 즉 실제 Auto Tile resolver를 호출하는 편집 가능한 논리 occupancy workspace다. 고정 sample bitmap에 sprite를 끼워 넣는 방식이 아니다.

구체적 파이프라인은 다음과 같다.

```text
사용자 좌/우 클릭·드래그
  → TrialPlacementState.cells[Vector3Int] = autoTileGuid
  → PreviewTileSetFactory.TryCreate(Document)
  → 현재 .platformertileset selection + 현재 PNG로 runtime TileBase 생성
  → GUID를 PlatformAutoTile / TerrainAutoTile / TopSequenceAutoTile로 매핑
  → Unity Tilemap.SetTile(position, tileBase)
  → Tilemap.Refresh / RefreshArea
  → 각 runtime AutoTile이 이웃 TileBase를 질의
  → role 및 multi-cell winner 계산
  → 해당 role pool에서 좌표 hash + weight로 candidate 선택
  → 선택된 cell sprite/collider가 Tilemap에 표시
```

`TrialPlacementState`의 실제 데이터는 `Dictionary<Vector3Int,string> cells`, 즉 위치→Auto Tile GUID다. sprite 번호나 최종 role은 저장하지 않는다. workspace 상수는 32×18, 부분 refresh padding은 4다. 사각형 적용은 영역의 각 셀에 `ApplyAt`을 호출하고 해당 범위만 refresh/render한다. 전체 rebuild는 state의 모든 GUID를 현재 `PreviewTileSet`의 TileBase로 다시 놓는다.

이 때문에 한 셀의 추가/삭제만으로 주변 sprite가 즉시 바뀐다. 후보 weight/enable/type/platform reference/PNG가 바뀌면 PreviewTileSet을 다시 만들고 같은 논리 배치를 재평가할 수 있다. 같은 좌표의 variation은 deterministic이므로 단순 refresh가 random reroll은 아니다. pool 순서나 weight가 바뀌면 누적 구간이 달라져 candidate가 바뀔 수 있다.

시험 배치 state는 `Document` 안에 있으나 `.platformertileset` manifest 필드에는 없다. 따라서 편집 세션용 임시 상태이며 Auto Tile Set 저장 데이터의 일부가 아니다.

### 고정 Sample Preview와의 구분

Auto Tiles 화면의 별도 `AutoTileSamplePreview`는 방식 A와 B를 결합한다. 고정된 논리 sample map에 실제 resolver TileBase를 놓는다.

- Platform: `#####`
- Solid:

```text
###################
##...##############
###########.#######
##...##############
###################
```

- Wall:

```text
###########.
############
##.######.##
############
###########.
```

`#` 위치에 동일한 runtime Auto Tile TileBase를 `SetTile`하고 Unity resolver가 최종 sprite를 만든다. 따라서 layout은 고정이지만 결과 선택은 실제 resolver다. Top Sequence sample은 현재 Start/Repeat/End pattern 크기와 `requireRepeat`를 읽어 동적으로 `#` 행을 만든다.

두 preview를 혼동하면 안 된다.

- 상단/Auto Tile Sample Preview: 미리 정의된 검증 topology + 실제 resolver.
- 하단 `시험 배치`: 사용자가 그린 32×18 Auto Tile GUID map + 실제 resolver.

## 11. Multi-cell

Reference의 multi-cell은 “한 logical cell에 큰 sprite 하나”가 아니다.

- PNG를 `TileImageLayout`이 32px logical cell들로 분해한다.
- 각 cell은 `rect`, `pivot`, `offset`, `type`을 가진다.
- pattern은 전체 `offsets[]`, `tileTypes[]`, `platformCells[]`, `tiles[]`를 가진다.
- resolver는 anchor 후보를 기준으로 모든 offset의 occupancy/role 호환성을 검사한다.
- 유효 pattern끼리 겹치면 coverage와 priority/hash로 winner를 고른다.
- winner의 각 logical cell에는 해당 cell sprite가 표시된다.

anchor는 role 방향에 따라 달라진다.

| 예 | 논리 구성 |
|---|---|
| 64×32 SolidTop | `(0,0) Top`, `(1,0) Top` |
| 32×64 SolidTop | `(0,-1) Inner`, `(0,0) Top` |
| 64×64 SolidLeft | `(0,0)/(0,1) Left`, `(1,0)/(1,1) Inner` |
| 64×32 LeftBridge | `(-1,0) PlatformCenter`, `(0,0) LeftBridge` |
| 64×32 RightBridge | `(0,0) RightBridge`, `(1,0) PlatformCenter` |

neighbor 계산은 anchor 하나만 보고 끝나지 않는다. pattern의 모든 cell이 기대 `TileType` 또는 Platform cell 조건과 맞는지 확인한다. 선택된 pattern은 여러 occupancy cell을 덮지만 논리 점유 자체는 시험 배치의 원래 GUID map에 남는다.

collision도 큰 PNG 하나에 하나의 거대 사각형을 붙이는 방식이 아니다. 분할된 각 `TileAsset` cell이 자기 role과 pivot에 따른 collider outline을 가진다.

## 12. Pivot / Collision / Grid

`TileImageLayout` 기본 상수는 tileSize=32, pivotPixels=16이다. 정상 32×32 셀은 pivot `(0.5,0.5)`다. PNG 크기에서 `columnCount=floor(width/32)`, `rowCount=floor(height/32)`를 만들되 마지막 sprite rect에는 남는 pixel을 포함할 수 있다. 39px 높이 anchor의 pivot y가 16/39가 되는 것이 그 예다.

Preview의 toggle은 서로 다른 데이터 층을 표시한다.

- 격자: `TileImageLayout`의 logical 32px cell 경계.
- 기준점: 각 `TileImageCell.pivot`.
- 충돌 영역: 각 role에서 `TilePhysics.CreateOutlines`로 만든 polygon.

physics 상수는 다음과 같다.

| 상수 | 값 |
|---|---:|
| groundMargin | 7 |
| bottomMargin | 5 |
| solidSideMargin | 8 |
| platformSideMargin | 4 |
| platformHeight | 1 |
| tileExtent | 16 |

32×32, pivot pixel `(16,16)`의 대표 outline은 다음과 같다.

- PlatformCenter: `(0,25)-(32,25)-(32,24)-(0,24)`, 1px one-way ground strip.
- PlatformLeftEnd: x=4부터 시작하는 1px strip.
- SolidInner/WallInner: `(0,0)-(32,32)` 전체 사각형.
- SolidTop: y=0~25의 solid rectangle, 상단 7px margin.
- SolidLeftTop: x=8~32, y=0~25 rectangle.

collider filter는 Platform 3종이 `PlatformGround`, Solid Top 및 top corner/bridge가 `SolidGround`, 나머지 Solid/Wall이 `Solid`다. pivot/collision은 manifest에 좌표 배열로 저장하지 않고 파일 role·이미지 크기에서 결정적으로 파생된다.

## 13. 저장 Format

`.platformertileset`은 JSON이며 current `formatVersion`은 1이다.

실제 영속 필드는 다음과 같다.

| 요구 정보 | 저장 여부 / 필드 |
|---|---|
| tile set/display name | `displayName` |
| tile image path | `tiles[].source`, 세트 기준 상대 경로 |
| role | `tiles[].type` |
| candidate number | 별도 숫자 필드가 아니라 파일명에서 파싱; runtime에는 `variantIndex` |
| Auto Tile name/type | `autoTiles[].name`, `type` |
| stable identity | `autoTiles[].guid` |
| connected Platform | Solid의 `platformGuid` |
| connected terrain | TopSequence의 `terrainGuid` |
| repeat 필수 | `requireRepeat` |
| candidate weight | `selections[].weight` |
| candidate enabled | 별도 필드 없음; `selections[]` 존재 여부 |
| pivot | 저장 안 함; layout에서 파생 |
| collision | 저장 안 함; role/pivot에서 파생 |
| 시험 배치 map | 저장 안 함 |

`Document.SetSelection(autoTile, tile, isSelected, weight)`와 `SetSelectionWeight`가 manifest selection을 편집한다. 저장 시 manifest만 serialize한다. `TrialPlacementState`는 Document runtime field지만 serialization schema에 포함되지 않는다.

로컬 CLI 문서에는 `validate`가 읽기 전용 검사, `create`가 새 manifest 생성이라고 명시돼 있다. 이번 분석에서는 쓰기를 일으키는 `create`를 호출하지 않았다.

## 14. 타일샘플과 연결 관계

Chapter1은 45 tiles/6 Auto Tiles, Chapter2는 54 tiles/6 Auto Tiles다. Chapter2 구성은 다음과 같다.

- Terrain Auto Tile: Solid selection 41개, Platform Auto Tile GUID 연결.
- Vanilla Terrain: 각 role의 기본 `_00` 중심 19개.
- Platform Auto Tile: LeftEnd/RightEnd 각 1개, Center 5개.
- Vanilla Platform: 각 role `_00` 3개.
- Top Sequence 00/01: 각각 Start/Repeat/End 3개, 같은 Vanilla Terrain GUID 참조, `requireRepeat=true`.

파일과 candidate 연결은 확정적이다.

```text
TileImages/Solid_Inner_00.png
  → tiles[].source = Solid_Inner_00.png
  → type = SolidInner
  → selection.tile = Solid_Inner_00
  → runtime role Solid.Inner의 variantIndex 0
```

PNG stem이 selection key이고 `.png` 확장자는 selection에서 빠진다. `_00`, `_01`은 같은 role pool의 candidate 번호다. 같은 candidate가 여러 Auto Tile의 selection에 들어갈 수 있다. 예를 들어 “Terrain Auto Tile”과 “Vanilla Terrain Auto Tile”은 같은 PNG를 서로 다른 weight/포함 집합으로 재사용한다.

샘플 PNG dimension 분포는 32×32 75개 외에 64×32 9개, 32×64 4개, 64×64 5개와 Top Sequence용 32×100, 64×103, 32×65, 64×66 등이 있다. 이것이 filename role뿐 아니라 실제 image dimension이 multi-cell pattern 생성에 사용된다는 근거다.

## 15. TileNamer 재사용 가능 구조

현재 기준은 dirty working tree의 TileNamer v0.1.5, HEAD `2fac4c79a7171532d0d2f59325f1bf8acab68c2d`다. 소스는 수정하지 않고 읽기만 했다.

| TileNamer 기존 구조 | 재사용 가능성 | Reference 기능에서의 용도 |
|---|---|---|
| category prefix | 높음 | role pool key (`Solid_Top` 등) |
| category별 ordered assignments | 높음 | `_00`, `_01` candidate 순서 |
| `AssetAssignment.selected_cells` | 높음 | multi-cell shape/offset 원천 |
| rectangular/irregular shape | 부분적 | pattern footprint 표현 가능. 각 cell role 의미는 추가 필요 |
| 32px `GridReference` | 높음 | logical occupancy 좌표계 |
| thumbnail/canvas overlay | 높음 | candidate·pattern inspector |
| PNG export plan | 높음 | Reference filename layout 공급 |
| Aseprite layer/grid alignment | 높음 | 입력 sprite extraction 안정화 |
| project save/load migration | 높음 | 새 Auto Tile 모델을 추가할 경우 migration 기반 |
| Temporary Tags | 낮음 | Auto Tile resolver role이 아니므로 별도 custom pool 정책 필요 |
| QUndoCommand history | 높음 | weight, enable, 시험 배치 편집 undo |

TileNamer의 `AssetAssignment`는 여러 셀의 bounding box와 selected cell set을 이미 표현한다. 하지만 Reference의 `TilePattern`처럼 cell별 expected role, Platform cell 표시, anchor 상대 offset은 아직 없다. 현재 candidate/order는 export 파일 번호이며 weighted runtime pool은 아니다.

## 16. TileNamer에 부족한 데이터

Reference와 동등한 resolver/시험 배치를 만들려면 최소 다음이 추가돼야 한다.

1. Auto Tile Set entity
   - GUID, 이름, type(Platform/Solid/Wall/TopSequence)
   - Solid→Platform reference, TopSequence→Terrain reference
   - `requireRepeat`
2. Candidate membership
   - candidate enabled/selection 여부
   - role pool별 weight
   - stable candidate identity와 export prefix 연결
3. Runtime pattern metadata
   - anchor
   - anchor-relative cell offsets
   - cell별 expected terrain role
   - cell별 Platform 여부
4. Resolver
   - 8-neighbor + bridge connection state
   - Platform endpoint rule
   - Wall 독립 연결과 slash/backslash rule
   - multi-cell coverage validation/overlap winner
   - 좌표 기반 deterministic weighted picker
5. 시험 배치 상태
   - cell→Auto Tile ID map
   - paint/erase/rectangle tools
   - dirty region refresh
6. Top Sequence dimensions와 part grouping
7. Preview용 pivot/collider model

반대로 Reference에 없는 것을 임의로 schema에 넣을 필요는 없다. Reference는 explicit neighbor-mask JSON, 사용자 편집 pivot 배열, collider polygon, 영속 preview map, `enabled` boolean을 저장하지 않는다. 이들은 rule/code 파생 또는 selection 존재 여부다.

Temporary Tags를 자동 terrain role로 취급하면 안 된다. resolver 의미가 없는 export prefix이므로 고정 preview에서는 보여줄 수 있어도 Level 2 resolver에는 명시적 custom-role 정책 없이는 참여시키지 않는 편이 안전하다.

## 17. 구현 Level 1 / 2 / 3 비교

| 수준 | 범위 | 데이터 모델 변경 | UI 복잡도 | 난이도 | regression risk |
|---|---|---|---|---|---|
| Level 1 | 현재 category assignment를 고정 Solid/Wall/Platform sample topology에 표시 | 거의 없음. preview 임시 매핑 정도 | 낮음 | 낮음 | 낮음~중간 |
| Level 2 | 실제 8-neighbor resolver, deterministic weight, Platform/Solid/Wall 관계, editable 시험 배치 | Auto Tile entity, selection weight/enabled, preview grid, 최소 pattern metadata | 중간~높음 | 높음 | 중간~높음 |
| Level 3 | Reference 수준의 Auto Tile Set 편집기, TopSequence, multi-cell winner, pivot/collider/validation | project schema의 큰 확장 및 migration 필요 | 매우 높음 | 매우 높음 | 높음 |

### Level 1

현재 export candidate `_00`, `_01`을 고정 sample map에 시각화한다. resolver를 흉내 내지 않고 prefix→미리 정한 위치 매핑을 사용한다. 빠른 completeness 확인에는 유용하지만 “시험 배치”라고 부르면 실제 동작과 오해될 수 있다. “Role Sample”처럼 명확히 이름을 구분해야 한다.

### Level 2

Reference의 핵심 가치인 논리 배치→실제 role/candidate 변환을 구현한다. 먼저 1×1 candidate로 Platform/Solid/Wall을 완성하고, 좌표 hash와 weight를 넣는다. 그 다음 현재 `selected_cells`를 확장해 rectangular multi-cell pattern을 지원한다. TopSequence와 collider 편집은 제외할 수 있다.

### Level 3

manifest 수준의 세트 생성/복제/삭제, cross-reference, TopSequence, multi-cell coverage priority, pivot/collider overlays, validator, palette order까지 포함한다. 이는 TileNamer의 “이름 지정·export” 목적을 넘어 별도 Auto Tile authoring product에 가깝다.

## 18. 최종 권장안

권장안은 **Level 1을 독립 기능으로 먼저 제공하고, 내부 모델은 Level 2로 확장 가능한 경계를 두는 것**이다. Reference 전체를 그대로 복제하는 Level 3는 현재 TileNamer의 목적과 비용에 맞지 않는다.

구체적으로는 다음 순서가 적절하다.

1. 현재 v0.1.5의 assignment/export schema는 당장 바꾸지 않는다.
2. 읽기 전용 `Role Sample Preview`를 별도 모델 없이 만들어 prefix 누락과 multi-cell 시각 상태를 확인한다.
3. 사용자 가치가 확인되면 `AutoTileSet`, `CandidateSelection(weight)`, `TrialGrid`를 별도 schema version으로 추가한다.
4. Level 2 첫 resolver는 Platform + 1×1 Solid/Wall부터 시작한다.
5. 결과 재현성을 위해 random API가 아니라 좌표 기반 deterministic weighted picker를 사용한다.
6. multi-cell은 현재 `selected_cells`를 그대로 runtime pattern으로 간주하지 말고, anchor·상대 offset·cell별 expected role을 명시적으로 파생/저장하는 설계를 먼저 확정한다.
7. Top Sequence와 collision authoring은 별도 후속 milestone로 둔다.

최우선 질문의 최종 답은 다음 한 문장으로 요약된다.

> Platformer Tile Editor v1.0.2의 `시험 배치`는 32×18 셀에 저장된 Auto Tile GUID map을 현재 manifest와 PNG로 만든 실제 Unity TileBase에 배치하고, 각 셀의 8방향/Bridge 연결, multi-cell pattern coverage, role별 pool, 좌표 기반 deterministic weight를 순서대로 적용해 최종 sprite를 생성한다.

마지막으로 분석 후 무결성을 같은 방식으로 재검증했다. 기준 inventory hash는 다음과 같다.

- Reference: 171 files / 95,224,068 bytes / `355EE313F5D7173A777927AA7C0A31972CEBECD585B320BA0CA7A818138F0900`
- 타일샘플: 204 files / 471,566 bytes / `9BAC8D9E7A04D4BA67D3D355141BD416FC3E4281F0E9705DECF684EA65A45724`

분석 과정에서 Reference와 타일샘플의 파일을 수정·이름 변경·삭제·저장하지 않았다. TileNamer에서는 이 분석 보고서 외에 소스, version, project schema, test를 수정하지 않았고 stage/commit/push도 수행하지 않았다.
