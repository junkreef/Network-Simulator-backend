> 🇬🇧 English version available → [topology.md](./topology.md)

# トポロジエンドポイント

これらのエンドポイントはネットワークトポロジのライフサイクルを管理します。Containerlab 経由での Docker コンテナのデプロイと破棄、セッション間での UI 状態の永続化を行います。

---

## `POST /api/v1/topology/deploy`

Containerlab ネットワークトポロジをデプロイします。このエンドポイントは：

1. ホスト上にルーターごとの設定ディレクトリを作成（`data/{topology_name}/{node_name}/`）
2. FRR デーモン設定ファイルを書き込む（`daemons`、`vtysh.conf`、初期 `frr.conf`）
3. Jinja2 テンプレートから `topology.clab.yml` をレンダリング
4. レンダリングされた YAML を前回のデプロイと比較 — 同一の場合はスキップ
5. 新しい YAML を `data/topology.clab.yml` に書き込む
6. `containerlab deploy -t topology.clab.yml --reconfigure` を実行

### リクエストボディ

`Content-Type: application/json`  
スキーマ: [`TopologyDeployRequest`](./schemas.ja.md#topologydeployrequest)

```json
{
  "name": "sim-network",
  "nodes": [
    {
      "name": "r1",
      "type": "router",
      "interfaces": ["eth1", "eth2", "eth3", "eth4"]
    },
    {
      "name": "sw1",
      "type": "switch",
      "interfaces": ["eth1", "eth2", "eth3"]
    },
    {
      "name": "pc1",
      "type": "terminal",
      "interfaces": ["eth1"]
    }
  ],
  "links": [
    { "endpoints": ["r1:eth1", "sw1:eth1"] },
    { "endpoints": ["sw1:eth2", "pc1:eth1"] }
  ]
}
```

#### フィールドの説明

| フィールド | 型 | デフォルト | 説明 |
|---|---|---|---|
| `name` | string | `"sim-network"` | トポロジ名。Containerlab のトポロジ識別子と設定ディレクトリ名として使用される。コンテナ名は `clab-{name}-{node_name}` になる。 |
| `nodes` | array | required | トポロジ内の全ノードのリスト。各ノードは `name`、`type`、`interfaces` を持つ。 |
| `nodes[].name` | string | required | ノードの一意の識別子（例: `"r1"`、`"sw1"`、`"pc1"`）。 |
| `nodes[].type` | string | required | Docker イメージを決定する: `"router"` → `alpine-frr:latest`、`"switch"` → `alpine-switch:latest`、それ以外 → `alpine-terminal:latest`。 |
| `nodes[].interfaces` | string の array | `[]` | このノードに割り当てられたインターフェース名（例: `["eth1", "eth2"]`）。コンテナ起動時に `ip link set dev {iface} up` で有効化される。 |
| `links` | array | required | ノードインターフェース間のケーブル接続。 |
| `links[].endpoints` | string の array | required | `"nodename:interface"` 形式の 2 つの文字列（例: `["r1:eth1", "sw1:eth1"]`）。どの仮想ポートが接続されるかを定義する。 |

### 成功レスポンス — トポロジをデプロイした場合

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Topology deployed successfully",
  "details": {
    "name": "sim-network",
    "container_count": 3
  }
}
```

`container_count` はリクエスト内のノード数です（実際の実行中コンテナ数とは異なる場合があります）。

### 成功レスポンス — 変更なし（スキップ）

HTTP `200 OK`

```json
{
  "status": "skipped",
  "message": "Topology is identical, skipping deploy",
  "details": {
    "name": "sim-network",
    "container_count": 3
  }
}
```

レンダリングされた `topology.clab.yml` が前回のデプロイファイルとバイト単位で同一の場合に返されます。コンテナの不要な再起動を避ける最適化です。

### エラーレスポンス

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to deploy topology: <エラー詳細>"
}
```

よくある原因:
- Docker デーモンが起動していない
- 必要な Docker イメージ（`alpine-frr:latest` など）が見つからない
- `containerlab` がインストールされていないまたは PATH にない
- `sudo containerlab` の権限不足

### 動作の注意事項

- containerlab に渡される `--reconfigure` フラグは、同名の既存コンテナを強制再作成します。
- YAML ファイルの書き込み後、ファイルシステムの同期のために `containerlab deploy` 前に 1 秒のスリープがあります。
- ルーター設定ディレクトリは初回デプロイを含め、デプロイ前に常に（再）作成されます。

---

## `POST /api/v1/topology/destroy`

現在実行中の Containerlab トポロジを破棄し、関連ファイルをすべてクリーンアップします。

### リクエストボディ

なし。

### 成功レスポンス

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Topology destroyed successfully"
}
```

### 成功レスポンス — トポロジファイルが見つからない場合

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "No topology configuration found to destroy, performed fallback name-based destroy"
}
```

`data/topology.clab.yml` が存在しない場合に返されます。この場合、バックエンドはフォールバックとして  
`containerlab destroy --name sim-network --cleanup`  
を試みます。これも失敗した場合は失敗がログに記録されますが、成功レスポンスが返されます。

### エラーレスポンス

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to destroy topology: <エラー詳細>"
}
```

### 動作の注意事項

- `containerlab destroy -t topology.clab.yml --cleanup` を実行します。`--cleanup` フラグは管理ネットワークとコンテナ状態をすべて削除します。
- Containerlab の destroy 後、ホスト上で以下のクリーンアップが実行されます：
  - `data/` 以下のすべてのサブディレクトリを削除（例: `data/sim-network/`）
  - `data/topology.clab.yml` を削除
  - `data/topology_deployed_data.json` を削除（存在する場合）
- `data/topology_state.json` と `data/topology_deployed_state.json` は destroy では**削除されません** — これらは `DELETE /api/v1/topology/state` で削除します。
- FastAPI アプリケーションのシャットダウンライフサイクルハンドラも `destroy_topology()` を呼び出すため、サーバー停止時に自動的にトポロジが破棄されます。

---

## `GET /api/v1/topology/status`

`containerlab inspect` を実行して、デプロイ済みトポロジの全ノードの実行時ステータスを返します。

### クエリパラメータ

なし。

### リクエストボディ

なし。

### 成功レスポンス — トポロジ実行中

HTTP `200 OK`

```json
{
  "topology_name": "sim-network",
  "status": "running",
  "nodes": [
    {
      "name": "r1",
      "kind": "linux",
      "state": "running",
      "ipv4_address": "172.20.20.2/24"
    },
    {
      "name": "sw1",
      "kind": "linux",
      "state": "running",
      "ipv4_address": "172.20.20.3/24"
    },
    {
      "name": "pc1",
      "kind": "linux",
      "state": "running",
      "ipv4_address": "172.20.20.4/24"
    }
  ]
}
```

#### レスポンスフィールドの説明

| フィールド | 型 | 説明 |
|---|---|---|
| `topology_name` | string | `topology.clab.yml` から読み取った Containerlab トポロジ名。見つからない場合は空文字列。 |
| `status` | string | inspect 出力にノードが存在すれば `"running"`、ノードがなければ `"stopped"`、inspect が失敗すれば `"error"`。 |
| `nodes` | array | `containerlab inspect` のノードステータスオブジェクトのリスト。 |
| `nodes[].name` | string | トポロジで定義されたノード名。 |
| `nodes[].kind` | string | Containerlab ノードの種類（このプロジェクトでは常に `"linux"`）。 |
| `nodes[].state` | string | Docker コンテナの状態: `"running"`、`"stopped"`、`"exited"` など。 |
| `nodes[].ipv4_address` | string | Containerlab の管理ネットワークが割り当てた管理 IPv4 アドレス（プレフィックス長付き）。 |

### 成功レスポンス — トポロジなし

HTTP `200 OK`

```json
{
  "topology_name": "",
  "status": "stopped",
  "nodes": []
}
```

`data/topology.clab.yml` が存在しない場合に返されます。

### エラーレスポンス — inspect 失敗

HTTP `200 OK`（注意: フロントエンドのポーリングループを壊さないよう、ステータスのエラーは 200 で返されます）

```json
{
  "topology_name": "",
  "status": "error",
  "message": "Command 'sudo containerlab inspect ...' returned non-zero exit status 1",
  "nodes": []
}
```

### 動作の注意事項

- `containerlab inspect -t topology.clab.yml --format json` を実行します。
- inspect 出力は、トポロジ名をトップレベルキーとする JSON です（例: `{"sim-network": [{...}, {...}]}`）。
- **リトライロジック**: コマンドは最大 **5 回**、各試行間に **2 秒**の待機を挟んでリトライされます。これはコンテナ起動時に `containerlab inspect` が古いまたは空のデータを返す場合のタイミング問題に対処するためです。
- トポロジ名はまずファイルから読み取られ、JSON 出力のどのキーを使用するかの検証に使われます。

---

## `GET /api/v1/topology/state`

保存済みの UI トポロジ状態（React Flow の `nodes` と `edges` 配列）を返します。

### クエリパラメータ

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `deployed` | boolean | `false` | `false` → `topology_state.json` を読み込む（現在の編集状態）；`true` → `topology_deployed_state.json` を読み込む（最後のデプロイ時の状態） |

### リクエストボディ

なし。

### 成功レスポンス

HTTP `200 OK`

```json
{
  "nodes": [
    {
      "id": "r1",
      "type": "routerNode",
      "position": { "x": 100, "y": 200 },
      "data": { "..." : "..." }
    }
  ],
  "edges": [
    {
      "id": "e1",
      "source": "r1",
      "target": "sw1"
    }
  ]
}
```

`nodes` と `edges` の正確な構造はフロントエンドが保存する React Flow の状態形式に一致します。バックエンドはこれを不透明な JSON オブジェクトとして扱います。

### 動作の注意事項

- **`deployed=false` のフォールバック**: `topology_state.json` が存在しない場合、バックエンドは `src/app/core/default_topology.json`（組み込みのスターターノポロジ）を読み込み、`data/topology_state.json` にコピーして返します。これにより初回ロード時に常に使用可能なトポロジが返されます。
- **`deployed=true` — フォールバックなし**: `topology_deployed_state.json` が存在しない場合は `{"nodes": [], "edges": []}` を返します。
- 読み取りエラー時も `{"nodes": [], "edges": []}` を返します。

---

## `POST /api/v1/topology/state`

ページリロード間の永続化のために UI トポロジ状態を JSON ファイルに保存します。

### クエリパラメータ

| パラメータ | 型 | デフォルト | 説明 |
|---|---|---|---|
| `deployed` | boolean | `false` | `false` → `topology_state.json` に保存；`true` → `topology_deployed_state.json` に保存 |

### リクエストボディ

任意の JSON オブジェクト（React Flow トポロジ状態）。バックエンドはこれを不透明なデータとして扱います。

```json
{
  "nodes": ["..."],
  "edges": ["..."]
}
```

### 成功レスポンス

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Topology state saved successfully"
}
```

`deployed=true` の場合、メッセージは `"Topology state deployed successfully"` になります。

### エラーレスポンス

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to save topology state: <エラー詳細>"
}
```

### 動作の注意事項

- ファイルは `json.dump(..., indent=2, ensure_ascii=False)` で書き込まれ、`f.flush()` と `os.fsync()` で耐久性が確保されます。
- デプロイエンドポイント（`POST /api/v1/topology/deploy`）は自動的にこれを呼び出しません — デプロイ成功後に `POST /api/v1/topology/state?deployed=true` を明示的に呼び出してデプロイ済み状態を記録する必要があります。

---

## `DELETE /api/v1/topology/state`

両方のトポロジ状態ファイルを削除し、次回ロード時に UI をデフォルトトポロジにリセットします。

### リクエストボディ

なし。

### 成功レスポンス

HTTP `200 OK`

```json
{
  "status": "success",
  "message": "Topology state reset successfully"
}
```

### エラーレスポンス

HTTP `500 Internal Server Error`

```json
{
  "detail": "Failed to reset topology state: <エラー詳細>"
}
```

### 動作の注意事項

- 存在する場合に `data/topology_state.json` と `data/topology_deployed_state.json` を削除します。
- `topology.clab.yml` やルーター設定ディレクトリは削除しません — 実行中のコンテナを停止するには `POST /api/v1/topology/destroy` を使用してください。
- 削除後、次の `GET /api/v1/topology/state` 呼び出しは `default_topology.json` にフォールバックします。

---

## ナビゲーション

- [← API リファレンス概要](./index.ja.md)
- [ノードエンドポイント →](./nodes.ja.md)
- [WebSocket ターミナル →](./websocket.ja.md)
- [Pydantic スキーマ →](./schemas.ja.md)
- [バックエンド開発者ガイド](../development.ja.md)
