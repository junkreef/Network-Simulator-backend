> 🇬🇧 English version available → [schemas.md](./schemas.md)

# Pydantic スキーマリファレンス

Network Simulator バックエンドで使用されるすべての Pydantic モデルは `src/app/api/endpoints.py` で定義されています。これらのモデルはリクエストボディの検証とシリアライズの正式なスキーマとして機能します。

このドキュメントでは、すべてのモデルをフィールドの型・デフォルト値・動作の注意事項を含めて詳しく説明します。

---

## トポロジモデル

### `NodeSchema`

**用途**: トポロジ内の単一ネットワークノードを表す。

**使用箇所**: [`TopologyDeployRequest`](#topologydeployrequest)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `name` | `str` | required | トポロジ内の一意のノード識別子（例: `"r1"`、`"sw1"`、`"pc1"`）。Containerlab のノード名とコンテナ名のサフィックスとして使用される。 |
| `type` | `str` | required | ノードタイプ文字列。使用する Docker イメージを決定: `"router"` → `alpine-frr:latest`、`"switch"` → `alpine-switch:latest`、それ以外 → `alpine-terminal:latest`。`configure_node()` での設定動作にも使用される。 |
| `interfaces` | `List[str]` | `[]` | インターフェース名のリスト（例: `["eth1", "eth2"]`）。コンテナ起動時に Containerlab の `exec` 機能で各インターフェースに `ip link set dev {iface} up` が実行される。 |

---

### `LinkSchema`

**用途**: 2 つのノードインターフェース間の物理ケーブル接続を表す。

**使用箇所**: [`TopologyDeployRequest`](#topologydeployrequest)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `endpoints` | `List[str]` | required | `"nodename:interface"` 形式の 2 つの文字列（例: `["r1:eth1", "sw1:eth1"]`）。順序によってどちら側のインターフェースが接続されるかが決まる。Containerlab は両エンドポイント間に仮想イーサネットペアを作成する。 |

---

### `TopologyDeployRequest`

**用途**: 完全なトポロジデプロイのリクエストボディ。

**使用箇所**: `POST /api/v1/topology/deploy`

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `name` | `str` | `"sim-network"` | トポロジ識別子。Containerlab トポロジ名（`topology.clab.yml` の `name:` フィールド）、コンテナ名プレフィックス（`clab-{name}-{node_name}`）、設定ディレクトリ名（`data/{name}/{node_name}/`）として使用される。 |
| `nodes` | `List[NodeSchema]` | required | トポロジ内の全ノード。 |
| `links` | `List[LinkSchema]` | required | ノードインターフェース間の全リンク（ケーブル）。 |

---

## ノード設定モデル

### `InterfaceConfig`

**用途**: 単一の物理ネットワークインターフェースの設定。ルーター（FRR の `interface` スタンザを生成）とスイッチ（VLAN ブリッジメンバーシップを制御）の両方で使用される。

**使用箇所**: [`RouterConfigureRequest`](#routerconfigurerequest)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `name` | `str` | required | Linux コンテナ内でのインターフェース名（例: `"eth1"`、`"eth2"`）。 |
| `ip_address` | `Optional[str]` | `None` | CIDR 表記の IP アドレス（例: `"192.168.1.1/24"`）。ルーターでは `frr.conf` の `interface` ブロックに `ip address {value}` を生成。ターミナルでは `ip addr add` で直接適用。スイッチノードでは無視される。 |
| `vlan_mode` | `Optional[str]` | `None` | **スイッチノード専用。** ポートの VLAN モード: `"access"`（単一タグなし VLAN）または `"trunk"`（複数タグ付き VLAN）。`None` の場合は `"access"` 動作になる。 |
| `vlan_id` | `Optional[int]` | `None` | **スイッチのアクセスモード専用。** このポートの単一 VLAN ID（例: `10`）。Linux ブリッジで `pvid` と `untagged` フラグ付きで設定される。 |
| `vlan_ids` | `Optional[List[int]]` | `None` | **スイッチのトランクモード専用。** このトランクポートで許可する VLAN ID のリスト（例: `[10, 20, 30]`）。各 ID は `untagged` フラグなしで追加される。 |

---

### `VlanInterfaceConfig`

**用途**: VLAN サブインターフェース（802.1Q タグ付きサブインターフェース）の設定。`ip link add ... type vlan` で作成される Linux カーネルの VLAN インターフェース。

**使用箇所**: [`RouterConfigureRequest`](#routerconfigurerequest)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `name` | `str` | required | サブインターフェース名（例: `"eth1.10"`）。命名規則は `{親インターフェース}.{vlan_id}`。 |
| `parent` | `str` | required | 親の物理インターフェース（例: `"eth1"`）。サブインターフェースはこの物理リンク上で指定 VLAN のタグ付きトラフィックを伝送する。 |
| `vlan_id` | `int` | required | VLAN ID（1〜4094）。`ip link add ... type vlan id {vlan_id}` で使用される。トラフィックフローの VLAN タグと一致する必要がある。 |
| `ip_address` | `Optional[str]` | `None` | サブインターフェースの CIDR 表記 IP アドレス。`ip addr add`（カーネル）と `frr.conf` の `interface` ブロック（FRR ルーティング用）の両方で適用される。 |

---

## OSPF モデル

### `OspfAreaConfig`

**用途**: OSPF エリア設定 — どのネットワークがエリアに属するか、エリアの動作（normal・stub・NSSA など）を定義する。

**使用箇所**: [`OspfConfig`](#ospfconfig)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `area_id` | `str` | required | ドット区切り10進数のエリア識別子。`"0.0.0.0"` はバックボーンエリア（Area 0）。非バックボーンエリアは Area 0 に直接または仮想リンク経由で接続する必要がある。 |
| `networks` | `List[str]` | `[]` | このエリアで広告するネットワーク。各エントリは `router ospf` ブロックに `network {net} area {area_id}` を生成。形式は CIDR（例: `"192.168.1.0/24"`）。 |
| `interfaces` | `Optional[List[str]]` | `[]` | インターフェース名（情報提供のみ — テンプレートレンダリングでは直接使用されない）。 |
| `ranges` | `Optional[List[str]]` | `[]` | ルート集約範囲。各エントリは `area {area_id} range {range}` を生成。エリア境界で複数の特定ルートを 1 つの集約広告にまとめるために使用。 |
| `area_type` | `Optional[str]` | `"normal"` | エリアタイプ: `"normal"`（特別処理なし）、`"stub"` → `area {id} stub`、`"totally-stub"` → `area {id} stub no-summary`、`"nssa"` → `area {id} nssa`、`"totally-nssa"` → `area {id} nssa no-summary`。 |

**エリアタイプの注意事項**:
- **Stub**: Type 5 LSA（外部ルート）を受け付けない。エッジでのルーティングテーブルサイズ削減に有効。
- **Totally-stub**: Stub + Type 3 LSA（サマリールート）も受け付けない。デフォルトルートのみがエリアに入る。
- **NSSA**: Type 7 LSA を通じた限定的な外部ルートのインポートを許可する。
- **Totally-NSSA**: NSSA と totally-stub の動作を組み合わせる。

---

### `RedistributionConfig`

**用途**: 他のソースからルーティングプロトコルにどのルートをインポートするかを制御する。OSPF・RIP・BGP の再配送設定で同じモデルが使い回されるが、すべてのフィールドがすべてのコンテキストで適用されるわけではない。

**使用箇所**: [`OspfConfig`](#ospfconfig)、[`RipConfig`](#ripconfig)、[`BgpConfig`](#bgpconfig)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `connected` | `Optional[bool]` | `False` | 直接接続ルート（設定済みインターフェースのサブネット）を再配送する。 |
| `static` | `Optional[bool]` | `False` | `frr.conf` の `ip route` で設定されたスタティックルートを再配送する。 |
| `ospf` | `Optional[bool]` | `False` | OSPF で学習したルートを再配送する。**条件付き**: OSPF が有効な場合のみ出力される。RIP と BGP の設定で使用。 |
| `rip` | `Optional[bool]` | `False` | RIP で学習したルートを再配送する。**条件付き**: RIP が有効な場合のみ出力される。OSPF と BGP の設定で使用。 |
| `bgp` | `Optional[bool]` | `False` | BGP で学習したルートを再配送する。**条件付き**: BGP が有効な場合のみ出力される。OSPF と RIP の設定で使用。 |

> **条件付き再配送**: テンプレートはクロスプロトコル再配送の `redistribute {protocol}` を、ソースプロトコルが有効な場合のみ出力します。例えば、OSPF の `redistribute rip` は `routing.rip.enabled` が `false` の場合はスキップされます。

---

### `OspfDefaultInformationOriginate`

**用途**: OSPF デフォルトルート広告を制御する — このルーターが OSPF ドメインに `0.0.0.0/0` デフォルトルートを広告するかどうか。

**使用箇所**: [`OspfConfig`](#ospfconfig)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | `bool` | `False` | `true` の場合、`router ospf` ブロックに `default-information originate` を追加する。 |
| `always` | `Optional[bool]` | `False` | `true` の場合、`always` を付加 — このルーター自身のルーティングテーブルにデフォルトルートがなくても広告する。`always` なしでは、ルーター自身がデフォルトルートを持つ場合のみ広告する。 |
| `metric` | `Optional[int]` | `None` | 設定した場合、`metric {N}` を付加してデフォルトルートの OSPF メトリックを上書きする。 |

**生成される FRR 構文**:
```
default-information originate
default-information originate always
default-information originate always metric 100
```

---

### `OspfConfig`

**用途**: ルーターノードの完全な OSPF ルーティング設定。

**使用箇所**: [`RoutingConfig`](#routingconfig)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | `bool` | `False` | マスタースイッチ。`false` の場合、`frr.conf` から `router ospf` ブロック全体が省略される。 |
| `router_id` | `Optional[str]` | `None` | OSPF ルーター ID（ドット区切り10進数、例: `"1.1.1.1"`）。強く推奨 — 明示的なルーター ID がないと、FRR は最高ループバック/インターフェース IP から自動選択し、予測不可能に変わる可能性がある。 |
| `areas` | `List[OspfAreaConfig]` | `[]` | OSPF エリア設定。 |
| `redistribute` | `Optional[RedistributionConfig]` | `None` | OSPF に他のソースからインポートするルート。 |
| `default_information_originate` | `Optional[OspfDefaultInformationOriginate]` | `None` | OSPF へのデフォルトルート広告。 |

---

## RIP モデル

### `RipConfig`

**用途**: RIP（Routing Information Protocol）設定。RIP は OSPF より単純なディスタンスベクタープロトコルだが、スケーラビリティは低い。FRR はデフォルトで RIPv2 を使用する。

**使用箇所**: [`RoutingConfig`](#routingconfig)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | `bool` | `False` | マスタースイッチ。`false` の場合、`router rip` ブロックが省略される。 |
| `networks` | `List[str]` | `[]` | RIP を有効化するネットワーク。各エントリは `network {net}` を生成。これらのネットワークのアドレスを持つインターフェースで RIP の送受信が行われる。 |
| `redistribute` | `Optional[RedistributionConfig]` | `None` | RIP にインポートするルート。注意: `RedistributionConfig` の `rip` フィールドはここでは適用されない（RIP 自身への再配送は不可）。 |

---

## BGP モデル

### `BgpNeighborConfig`

**用途**: 単一の BGP ピア（ネイバー）設定。

**使用箇所**: [`BgpConfig`](#bgpconfig)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `ip_address` | `str` | required | ネイバーの IP アドレス。BGP 設定で `neighbor {ip_address} remote-as {remote_as}` と、`address-family ipv4 unicast` ブロックで `neighbor {ip_address} activate` を生成する。 |
| `remote_as` | `int` | required | ネイバーの AS 番号。`as_number` と異なる場合は eBGP（外部 BGP）セッション。同じ場合は iBGP（内部 BGP）セッション。 |

---

### `BgpConfig`

**用途**: BGP（Border Gateway Protocol）設定。BGP はインターネットで使用されるドメイン間ルーティングプロトコル。このシミュレータでは、異なる自律システムのルーターを接続するために使用できる。

**使用箇所**: [`RoutingConfig`](#routingconfig)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | `bool` | `False` | マスタースイッチ。`false` の場合、`router bgp` ブロックが省略される。 |
| `as_number` | `Optional[int]` | `None` | このルーターの自律システム番号。`enabled=true` の場合は必須。`router bgp {as_number}` に使用される。 |
| `router_id` | `Optional[str]` | `None` | BGP ルーター ID（ドット区切り10進数）。設定しない場合は FRR が自動選択する。 |
| `neighbors` | `List[BgpNeighborConfig]` | `[]` | BGP ピアのリスト。 |
| `redistribute` | `Optional[RedistributionConfig]` | `None` | BGP の `address-family ipv4 unicast` にインポートするルート。**特別な動作**: `redistribute` が `None` またはすべてのフラグが `false` の場合、テンプレートはデフォルトで `redistribute connected` を出力し、ルーター自身のインターフェースが常に BGP 経由で到達可能になる。 |

**常に含まれる FRR ディレクティブ**: `no bgp ebgp-requires-policy` — FRR のデフォルトである eBGP セッションへの明示的なルートマップポリシー要件を無効化する。これがないと、ルートポリシーが設定されていない限り eBGP ネイバーはルートを交換しない。

---

## 複合モデル

### `RoutingConfig`

**用途**: 3 つの動的ルーティングプロトコル設定をグループ化するコンテナ。すべてのフィールドはオプションであり、プロトコルを省略することは `enabled: false` と同等。

**使用箇所**: [`RouterConfigureRequest`](#routerconfigurerequest)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `ospf` | `Optional[OspfConfig]` | `None` | OSPF 設定。`None` の場合、OSPF は無効。 |
| `rip` | `Optional[RipConfig]` | `None` | RIP 設定。`None` の場合、RIP は無効。 |
| `bgp` | `Optional[BgpConfig]` | `None` | BGP 設定。`None` の場合、BGP は無効。 |

---

### `StaticRouteConfig`

**用途**: 単一のスタティックルートエントリ。スタティックルートは `frr.conf` の `ip route` ディレクティブで FRR ルーティングテーブルに直接追加される。

**使用箇所**: [`RouterConfigureRequest`](#routerconfigurerequest)

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `destination` | `str` | required | CIDR 表記の宛先ネットワーク（例: `"172.16.0.0/16"`、`"0.0.0.0/0"`）。 |
| `next_hop` | `str` | required | ネクストホップの IP アドレス（例: `"192.168.1.254"`）。一致する宛先のパケットはこの IP アドレスに転送される。 |

---

### `RouterConfigureRequest`

**用途**: ノード設定エンドポイントのメインリクエストボディ。すべてのノードタイプ（ルーター・スイッチ・ターミナル）で使用されるが、適用されるフィールドはタイプによって異なる。

**使用箇所**: `POST /api/v1/nodes/{node_name}/configure`

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `interfaces` | `List[InterfaceConfig]` | `[]` | 物理インターフェースの設定。 |
| `vlan_interfaces` | `List[VlanInterfaceConfig]` | `[]` | VLAN サブインターフェースの設定。`frr.conf` レンダリング前に処理される。Linux カーネル側でサブインターフェースが同期（追加/削除）される。 |
| `routing` | `Optional[RoutingConfig]` | `None` | 動的ルーティングプロトコルの設定。ルーターノードのみに使用。 |
| `gateway` | `Optional[str]` | `None` | デフォルトゲートウェイの IP アドレス。**ルーターの型変換**: `gateway` が指定され、`static_routes` に `0.0.0.0/0` エントリが存在しない場合、自動的に `{"destination": "0.0.0.0/0", "next_hop": gateway}` が追加される。 |
| `static_routes` | `List[StaticRouteConfig]` | `[]` | スタティックルート。 |

---

## 型変換と特別な動作

### ゲートウェイ → スタティックルートの型変換（ルーター）

ルーター設定で `gateway` が指定された場合、オーケストレーターは自動的にスタティックデフォルトルートに変換します：

```python
if gateway:
    if not any(r.get("destination") in ("0.0.0.0/0", "0.0.0.0") for r in static_routes):
        static_routes.append({"destination": "0.0.0.0/0", "next_hop": gateway})
```

これにより `frr.conf` に以下が生成されます：

```
ip route 0.0.0.0/0 192.168.1.254
```

`static_routes` に `0.0.0.0/0` エントリが既に存在する場合、ゲートウェイは追加されません（デフォルトルートの重複なし）。

ターミナルノードの場合、`gateway` は `ip route add default via {gateway}` で直接適用されます — `static_routes` への型変換は行われません。

### BGP のデフォルト再配送

`routing.bgp.redistribute` が `None` またはすべての再配送フラグが `false` の場合、`frr.conf.j2` テンプレートはデフォルトで BGP の `address-family ipv4 unicast` ブロックに `redistribute connected` を出力します。これにより、明示的な再配送設定がなくてもルーター自身の直接接続プレフィックスが常に BGP ネイバーに広告されます。

### VLAN サブインターフェースの同期

`_sync_vlan_interfaces()` メソッドは、既存のカーネル VLAN インターフェース（`ip link show` から解析）と `vlan_interfaces` のターゲットリストの差分を計算します：
- 既存セットに存在するが**ターゲットにない**インターフェース → 削除: `ip link delete {name}`
- ターゲットに存在するが**既存にない**インターフェース → 作成: `ip link add link {parent} name {name} type vlan id {id}` して有効化

---

## ナビゲーション

- [← API リファレンス概要](./index.ja.md)
- [← トポロジエンドポイント](./topology.ja.md)
- [← ノードエンドポイント](./nodes.ja.md)
- [← WebSocket ターミナル](./websocket.ja.md)
- [バックエンド開発者ガイド](../development.ja.md)
