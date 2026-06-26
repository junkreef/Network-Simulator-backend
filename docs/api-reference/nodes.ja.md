> 🇬🇧 English version available → [nodes.md](./nodes.md)

# ノードエンドポイント

これらのエンドポイントは個々のネットワークノード（ルーター・スイッチ・ターミナル）の設定、コンテナ内部からの実行時診断情報の取得、インターフェースの管理状態の制御を行います。

---

## `POST /api/v1/nodes/{node_name}/configure`

特定のノードに完全な設定を適用します。動作はノードの種類によって異なります：

- **ルーター**（`alpine-frr`）: Jinja2 テンプレートから `frr.conf` をレンダリングし、コンテナ内の `frr-reload.py` でゼロダウンタイムに適用します。
- **L2 スイッチ**（`alpine-switch`）: VLAN フィルタリング対応の Linux ブリッジ（`br0`）を作成し、ポートをアクセスまたはトランクモードに設定します。
- **ターミナル**（`alpine-terminal`）: `ip` コマンドで直接 IP アドレスとデフォルトゲートウェイを適用します。

### パスパラメータ

| パラメータ | 型 | 説明 |
|---|---|---|
| `node_name` | string | トポロジで定義されたノード名（例: `"r1"`、`"sw1"`、`"pc1"`） |

### リクエストボディ

`Content-Type: application/json`  
スキーマ: [`RouterConfigureRequest`](./schemas.ja.md#routerconfigurerequest)

#### 完全なリクエストボディの例（ルーター）

```json
{
  "interfaces": [
    {
      "name": "eth1",
      "ip_address": "192.168.1.1/24",
      "vlan_mode": null,
      "vlan_id": null,
      "vlan_ids": null
    },
    {
      "name": "eth2",
      "ip_address": "10.0.0.1/30",
      "vlan_mode": null,
      "vlan_id": null,
      "vlan_ids": null
    }
  ],
  "vlan_interfaces": [
    {
      "name": "eth1.10",
      "parent": "eth1",
      "vlan_id": 10,
      "ip_address": "10.10.10.1/24"
    }
  ],
  "routing": {
    "ospf": {
      "enabled": true,
      "router_id": "1.1.1.1",
      "areas": [
        {
          "area_id": "0.0.0.0",
          "networks": ["192.168.1.0/24", "10.0.0.0/30"],
          "interfaces": [],
          "ranges": ["10.0.0.0/8"],
          "area_type": "normal"
        },
        {
          "area_id": "0.0.0.1",
          "networks": ["10.10.10.0/24"],
          "interfaces": [],
          "ranges": [],
          "area_type": "stub"
        }
      ],
      "redistribute": {
        "connected": false,
        "static": true,
        "ospf": false,
        "rip": false,
        "bgp": false
      },
      "default_information_originate": {
        "enabled": true,
        "always": false,
        "metric": null
      }
    },
    "rip": {
      "enabled": false,
      "networks": [],
      "redistribute": {
        "connected": false,
        "static": false,
        "ospf": false,
        "bgp": false
      }
    },
    "bgp": {
      "enabled": false,
      "as_number": 65001,
      "router_id": "1.1.1.1",
      "neighbors": [
        {
          "ip_address": "192.168.1.2",
          "remote_as": 65002
        }
      ],
      "redistribute": {
        "connected": false,
        "static": false,
        "ospf": false,
        "rip": false
      }
    }
  },
  "gateway": "192.168.1.254",
  "static_routes": [
    {
      "destination": "172.16.0.0/16",
      "next_hop": "192.168.1.254"
    }
  ]
}
```

#### トップレベルフィールドの説明

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `interfaces` | List[InterfaceConfig] | `[]` | 物理インターフェースの設定。ルーターでは `frr.conf` の `interface` スタンザを生成。ターミナルでは `ip addr add` で直接適用。 |
| `vlan_interfaces` | List[VlanInterfaceConfig] | `[]` | VLAN サブインターフェースの設定（例: `eth1.10`）。`ip link add link {parent} name {name} type vlan id {id}` で作成し、有効化される。 |
| `routing` | RoutingConfig \| null | `null` | 動的ルーティングプロトコルの設定。ルーターノードのみに使用。 |
| `gateway` | string \| null | `null` | デフォルトゲートウェイの IP アドレス。**ルーターの場合**: `static_routes` に `0.0.0.0/0` エントリが存在しなければ静的ルートとして追加。**ターミナルの場合**: `ip route add default via {gateway}` で適用。 |
| `static_routes` | List[StaticRouteConfig] | `[]` | `frr.conf` に `ip route {destination} {next_hop}` として追加される静的ルートエントリ。 |

#### `interfaces[].vlan_mode`、`vlan_id`、`vlan_ids`（スイッチ専用）

スイッチノードでは、各インターフェースの `vlan_mode`、`vlan_id`、`vlan_ids` フィールドが Linux ブリッジの VLAN フィルタリングを制御します：

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `vlan_mode` | string \| null | `null`（`"access"` として扱われる） | ポートモード: `"access"` または `"trunk"` |
| `vlan_id` | int \| null | `null` | `"access"` モード用: 単一の VLAN ID（`pvid` と `untagged` フラグで設定） |
| `vlan_ids` | List[int] \| null | `null` | `"trunk"` モード用: 許可する VLAN ID のリスト（`untagged` なしで追加） |

#### `routing.ospf` フィールドの説明

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | bool | `false` | `frr.conf` の `router ospf` ブロックを有効化 |
| `router_id` | string \| null | `null` | OSPF ルーター ID（ドット区切り10進数、例: `"1.1.1.1"`）。null の場合は省略。 |
| `areas` | List[OspfAreaConfig] | `[]` | OSPF エリアのリスト。各エリアは広告するネットワークとエリアタイプを設定。 |
| `areas[].area_id` | string | required | ドット区切り10進数のエリア識別子（例: バックボーンエリア 0 は `"0.0.0.0"`）。 |
| `areas[].networks` | List[str] | `[]` | このエリアで広告するネットワーク（`network {net} area {area_id}`）。 |
| `areas[].ranges` | List[str] | `[]` | ルート集約範囲（`area {area_id} range {range}`）。 |
| `areas[].area_type` | string | `"normal"` | エリアタイプ: `"normal"`、`"stub"`、`"totally-stub"`、`"nssa"`、`"totally-nssa"`。FRR のエリアコマンドにマッピングされる。 |
| `redistribute.connected` | bool | `false` | OSPF での `redistribute connected` |
| `redistribute.static` | bool | `false` | OSPF での `redistribute static` |
| `redistribute.rip` | bool | `false` | `redistribute rip`（RIP が有効な場合のみ出力） |
| `redistribute.bgp` | bool | `false` | `redistribute bgp`（BGP が有効な場合のみ出力） |
| `default_information_originate.enabled` | bool | `false` | `default-information originate` |
| `default_information_originate.always` | bool | `false` | `always` を付加 — ローカルにデフォルトルートがなくても広告 |
| `default_information_originate.metric` | int \| null | `null` | `metric {N}` を付加してデフォルトメトリックを上書き |

#### `routing.rip` フィールドの説明

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | bool | `false` | `frr.conf` の `router rip` ブロックを有効化 |
| `networks` | List[str] | `[]` | RIP に参加するネットワーク（`network {net}`） |
| `redistribute.connected` | bool | `false` | RIP での `redistribute connected` |
| `redistribute.static` | bool | `false` | RIP での `redistribute static` |
| `redistribute.ospf` | bool | `false` | `redistribute ospf`（OSPF が有効な場合のみ出力） |
| `redistribute.bgp` | bool | `false` | `redistribute bgp`（BGP が有効な場合のみ出力） |

#### `routing.bgp` フィールドの説明

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `enabled` | bool | `false` | `frr.conf` の `router bgp {as_number}` ブロックを有効化 |
| `as_number` | int \| null | `null` | このルーターの AS 番号 |
| `router_id` | string \| null | `null` | BGP ルーター ID（ドット区切り10進数） |
| `neighbors` | List[BgpNeighborConfig] | `[]` | BGP ピアのリスト。各ピアは `neighbor {ip} remote-as {as}` と `address-family ipv4 unicast` ブロック内の `neighbor {ip} activate` を生成。 |
| `redistribute.connected` | bool | `false` | BGP の `address-family ipv4 unicast` での `redistribute connected`。**注意**: `redistribute` が全く指定されない場合はデフォルトで `redistribute connected` が追加される。 |
| `redistribute.static` | bool | `false` | BGP での `redistribute static` |
| `redistribute.ospf` | bool | `false` | `redistribute ospf`（OSPF が有効な場合のみ出力） |
| `redistribute.rip` | bool | `false` | `redistribute rip`（RIP が有効な場合のみ出力） |

`no bgp ebgp-requires-policy` は常に含まれ、ルートポリシーなしで eBGP セッションを許可します。

### スイッチ専用リクエストボディの例

スイッチノードでは、`vlan_mode`/`vlan_id`/`vlan_ids` を持つ `interfaces` のみが有効です。`routing` と `vlan_interfaces` は無視されます。

```json
{
  "interfaces": [
    {
      "name": "eth1",
      "vlan_mode": "access",
      "vlan_id": 10
    },
    {
      "name": "eth2",
      "vlan_mode": "trunk",
      "vlan_ids": [10, 20, 30]
    },
    {
      "name": "eth3",
      "vlan_mode": "access",
      "vlan_id": 20
    }
  ]
}
```

**スイッチの設定プロセス：**

1. VLAN フィルタリング有効・STP なし・フォワード遅延 0 の Linux ブリッジ `br0` を作成：  
   `ip link add name br0 type bridge vlan_filtering 1 forward_delay 0 stp_state 0`
2. `br0` を有効化。
3. 各インターフェースに対して：
   - ブリッジメンバーとして追加: `ip link set dev {iface} master br0`
   - インターフェースを有効化: `ip link set dev {iface} up`
   - デフォルト VLAN 1 を削除: `bridge vlan del dev {iface} vid 1`
   - **アクセスモード**: `bridge vlan add dev {iface} vid {vlan_id} pvid untagged`
   - **トランクモード**: 各 VLAN ID に対して: `bridge vlan add dev {iface} vid {vid}`

### ターミナル専用リクエストボディの例

ターミナルノードでは、`ip_address` を持つ `interfaces` と `gateway` のみが使用されます。

```json
{
  "interfaces": [
    {
      "name": "eth1",
      "ip_address": "192.168.1.10/24"
    }
  ],
  "gateway": "192.168.1.1"
}
```

**ターミナルの設定プロセス：**

1. IP を持つ各インターフェースに対して: 既存アドレスをフラッシュ、`ip addr add {ip} dev {iface}` を実行し、`ip link set dev {iface} up` で有効化。
2. ゲートウェイが指定されている場合: `ip route del default` の後 `ip route add default via {gateway}` を実行。

### 成功レスポンス

HTTP `200 OK`

**ルーター：**
```json
{
  "status": "success",
  "output": "Configuration applied successfully via frr-reload.py"
}
```

`output` フィールドには `frr-reload.py` の実際の出力が含まれます（出力がない場合は上記のデフォルトメッセージ）。

**スイッチ：**
```json
{
  "status": "success",
  "output": "L2 Switch configured successfully with VLAN filtering"
}
```

**ターミナル：**
```json
{
  "status": "success",
  "output": "Terminal interfaces and routing configured successfully"
}
```

### エラーレスポンス

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to configure node r1: <エラー詳細>"
}
```

よくある原因:
- コンテナが見つからない（トポロジが未デプロイ、またはノード名の不一致）
- `frr-reload.py` がゼロ以外の終了コードを返した（FRR 設定の構文エラー）
- 30 秒以内に vtysh が応答しなかった

### 動作の注意事項 — ルーター設定の詳細

1. まず `_sync_vlan_interfaces()` が呼ばれ、Linux カーネル側の VLAN サブインターフェースを追加/削除します。
2. VLAN インターフェースの IP は FRR 設定に関係なく直接カーネルに適用されます（FRR と並行してカーネルルーティングが機能するために必要）。
3. バックエンドは `vtysh -c "write"` が終了コード 0 を返すまで最大 30 回（1 秒間隔）待ちます。
4. 新しい設定はコンテナ内の `/etc/frr/frr.conf.new` に書き込まれ、`frr-reload.py --reload` で差分のみ適用されます。
5. リロード後、一時ファイル `/etc/frr/frr.conf.new` は削除されます。
6. 成功時、レンダリングされた `frr.conf` はホストのファイル（`data/{topo_name}/{node_name}/frr.conf`）にも書き込まれ、コンテナ再起動後も設定が保持されます。

---

## `GET /api/v1/nodes/{node_name}/runtime-info`

CLI コマンドを実行して、ノードのコンテナ内部から実行時診断情報を取得します。

### パスパラメータ

| パラメータ | 型 | 説明 |
|---|---|---|
| `node_name` | string | トポロジで定義されたノード名 |

### クエリパラメータ

| パラメータ | 型 | 必須 | 説明 |
|---|---|---|---|
| `type` | string | はい | 取得する実行時情報の種類。以下のリストのいずれかの値でなければならない。 |

#### 有効な `type` の値

| `type` | ルーターコマンド | ターミナル/スイッチコマンド |
|---|---|---|
| `routing_table` | `vtysh -c "show ip route"` | `ip route show` |
| `arp_table` | `ip neighbor show` | `ip neighbor show` |
| `ospf_neighbors` | `vtysh -c "show ip ospf neighbor"` | ❌ エラー: ルーターのみ |
| `bgp_neighbors` | `vtysh -c "show ip bgp summary"` | ❌ エラー: ルーターのみ |
| `rip_status` | `vtysh -c "show ip rip"` | ❌ エラー: ルーターのみ |

コンテナイメージ名に `"frr"` が含まれるかどうかでノードタイプを判定します（`alpine-frr:latest` はルーターとして扱われます）。

### リクエストボディ

なし。

### 成功レスポンス

HTTP `200 OK`

```json
{
  "node_name": "r1",
  "info_type": "routing_table",
  "raw_output": "Codes: K - kernel route, C - connected, S - static, R - RIP,\n       O - OSPF, I - IS-IS, B - BGP...\n\nO   10.0.0.0/30 [110/10] is directly connected, eth2, 00:05:10\nC>* 10.0.0.0/30 is directly connected, eth2, 00:05:10\nC>* 192.168.1.0/24 is directly connected, eth1, 00:05:10\nS>* 0.0.0.0/0 [1/0] via 192.168.1.254, eth1, 00:05:10"
}
```

#### レスポンスフィールドの説明

| フィールド | 型 | 説明 |
|---|---|---|
| `node_name` | string | パスパラメータのノード名 |
| `info_type` | string | `type` クエリパラメータの値 |
| `raw_output` | string | コンテナ内で実行されたコマンドの stdout の生出力 |

### エラーレスポンス — 無効な type

HTTP `400 Bad Request`

```json
{
  "detail": "Invalid type. Must be one of routing_table, arp_table, ospf_neighbors, bgp_neighbors, rip_status"
}
```

### エラーレスポンス — ターミナルでプロトコル情報を要求した場合

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to get runtime info for pc1: OSPF neighbors only available on routers"
}
```

### エラーレスポンス — コマンド失敗

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to get runtime info for r1: Failed to execute command vtysh -c show ip route: ..."
}
```

---

## `POST /api/v1/nodes/{node_name}/interfaces/{interface_name}/state`

コンテナ内で `ip link set dev {interface_name} {up|down}` を実行して、特定のネットワークインターフェースの管理状態を設定します。

物理ネットワークでのケーブルの接続・切断に相当します。インターフェースは設定が保持されたまま `down` の状態ではトラフィックを送受信しません。

### パスパラメータ

| パラメータ | 型 | 説明 |
|---|---|---|
| `node_name` | string | トポロジで定義されたノード名（例: `"r1"`） |
| `interface_name` | string | ノード上のインターフェース名（例: `"eth1"`） |

### クエリパラメータ

| パラメータ | 型 | 必須 | バリデーション | 説明 |
|---|---|---|---|---|
| `state` | string | はい | `^(up\|down)$` に一致する必要あり | 目標インターフェース状態 |

### リクエストボディ

なし。

### 成功レスポンス

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Interface eth1 set to down successfully",
  "details": {
    "node_name": "r1",
    "interface_name": "eth1",
    "state": "down"
  }
}
```

### エラーレスポンス — 無効な state パラメータ

HTTP `422 Unprocessable Entity`（Pydantic/FastAPI クエリバリデーション）

```json
{
  "detail": [
    {
      "loc": ["query", "state"],
      "msg": "string does not match regex \"^(up|down)$\"",
      "type": "value_error.str.regex"
    }
  ]
}
```

### エラーレスポンス — コンテナが見つからない場合

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to configure interface state for r1 eth1: Container for node r1 not found"
}
```

### 動作の注意事項

- コンテナ内で `ip link set dev {interface_name} {state}` を直接実行します。
- FRR を実行しているルーターでは: `zebra` デーモンがリンク状態の変化を検知し、ルーティングテーブルを更新します。`down` にしたインターフェースの直接接続ルートは削除されます。
- そのインターフェース上の OSPF/BGP セッションも切断され、ネイバー喪失イベントとルートの再収束がトリガーされます。

---

## ナビゲーション

- [← API リファレンス概要](./index.ja.md)
- [← トポロジエンドポイント](./topology.ja.md)
- [WebSocket ターミナル →](./websocket.ja.md)
- [Pydantic スキーマ →](./schemas.ja.md)
- [バックエンド開発者ガイド](../development.ja.md)
