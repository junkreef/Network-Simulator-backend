> 🇬🇧 English version available → [development.md](./development.md)

# バックエンド開発者ガイド

このガイドでは、Network Simulator バックエンドのセットアップ・実行・テスト・アーキテクチャ理解に必要な情報を網羅しています。バックエンドは FastAPI アプリケーションであり、Containerlab を通じて Docker コンテナを管理し、FRR ルーティングを設定します。

---

## 前提条件

| ツール | バージョン | 用途 |
|---|---|---|
| Python | ≥ 3.10 | バックエンド実行環境 |
| Docker | 最新版 | ネットワークノード用コンテナランタイム |
| Containerlab | 最新版 | ネットワークトポロジの管理 |

Containerlab はシステム全体にインストールされ、`sudo containerlab`（またはroot権限）で実行できる必要があります。詳細は [Containerlab インストールガイド](https://containerlab.dev/install/) を参照してください。

バックエンドには、以下のカスタム Docker イメージのビルドも必要です：

| イメージ | パス | 用途 |
|---|---|---|
| `alpine-frr:latest` | `backend/docker/router/` | ルーターノード（FRR） |
| `alpine-terminal:latest` | `backend/docker/terminal/` | ターミナル/PC ノード |
| `alpine-switch:latest` | `backend/docker/switch/` | L2 スイッチノード |

---

## セットアップ

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Linux/macOS
# Windowsの場合: .venv\Scripts\activate
pip install -r requirements.txt
```

### 依存パッケージ（`requirements.txt`）

| パッケージ | 用途 |
|---|---|
| `fastapi` | Web フレームワーク |
| `uvicorn` | ASGI サーバー |
| `jinja2` | frr.conf・トポロジ YAML のテンプレート処理 |
| `docker` | Docker SDK for Python（コンテナ管理） |
| `pydantic` | リクエスト/レスポンスのスキーマ検証 |
| `pydantic-settings` | 環境変数による設定管理 |
| `pytest` | テストランナー |
| `httpx` | API テスト用 HTTP クライアント |
| `websockets` | インテグレーションテスト用 WebSocket クライアント |

`anyio`（非同期ターミナル I/O に使用）は `fastapi`/`uvicorn` の依存として自動的にインストールされます。

---

## サーバーの起動

```bash
.venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

| フラグ | 説明 |
|---|---|
| `--host 0.0.0.0` | 全インターフェースでリッスン（Docker からのアクセスに必要） |
| `--port 8000` | バックエンドのデフォルトポート |
| `--reload` | ファイル変更時に自動再起動（開発モードのみ推奨） |

**API ドキュメント**（Swagger UI）: http://localhost:8000/docs  
**OpenAPI スキーマ**: http://localhost:8000/api/v1/openapi.json  
**ヘルスチェック**: http://localhost:8000/

---

## テストの実行

```bash
# 全テストを実行
.venv/bin/pytest

# 特定のテストディレクトリを実行
.venv/bin/pytest tests/unit/
.venv/bin/pytest tests/integration/

# 詳細出力
.venv/bin/pytest -v

# 特定のテストファイルを実行
.venv/bin/pytest tests/unit/test_api.py -v
```

> **注意**: インテグレーションテスト（`tests/integration/`）は Docker が起動済みであり、カスタム Docker イメージがビルド済みであることが必要です。`conftest.py` のフィクスチャが自動的にイメージビルドを試みます。

---

## プロジェクト構成

```
backend/
├── src/
│   └── app/
│       ├── main.py                     # FastAPI アプリ初期化、CORS、ルーター登録、ライフサイクル
│       ├── api/
│       │   ├── endpoints.py            # REST API ルートと Pydantic スキーマ
│       │   └── websocket.py            # WebSocket ターミナルプロキシエンドポイント
│       ├── core/
│       │   ├── config.py               # アプリ設定（BASE_DIR、CONFIG_DIR、TEMPLATE_DIR）
│       │   ├── orchestrator.py         # コアオーケストレーションロジック
│       │   └── default_topology.json   # 保存済み状態がない場合に読み込むデフォルトトポロジ
│       └── templates/
│           ├── frr.conf.j2             # FRR ルーティング設定の Jinja2 テンプレート
│           └── topology.clab.yml.j2    # Containerlab トポロジの Jinja2 テンプレート
├── tests/
│   ├── conftest.py                     # pytest フィクスチャと Docker イメージビルド
│   ├── unit/
│   │   ├── test_api.py                 # REST エンドポイントのユニットテスト
│   │   └── test_orchestrator.py        # Orchestrator クラスのユニットテスト
│   └── integration/
│       └── test_integration.py         # インテグレーションテスト（Docker 必須）
├── docker/
│   ├── router/                         # alpine-frr イメージの Dockerfile
│   ├── terminal/                       # alpine-terminal イメージの Dockerfile
│   └── switch/                         # alpine-switch イメージの Dockerfile
├── data/                               # 実行時生成の設定ファイル（gitignore 対象）
├── requirements.txt
└── .venv/                              # Python 仮想環境
```

---

## 設定（`config.py`）

設定は `pydantic-settings` によって `src/app/core/config.py` で管理されます。すべての設定にはデフォルト値があり、環境変数でオーバーライドできます。

| 設定 | デフォルト値 | 説明 |
|---|---|---|
| `PROJECT_NAME` | `"Network Simulator"` | アプリケーションの表示名 |
| `API_V1_STR` | `"/api/v1"` | 全 REST API ルートの URL プレフィックス |
| `BASE_DIR` | `src/app/`（絶対パス） | インポート時に `__file__` から解決 |
| `PROJECT_ROOT` | `backend/`（絶対パス） | `BASE_DIR` の 2 階層上 |
| `CONFIG_DIR` | `{PROJECT_ROOT}/data/` | トポロジ YAML と実行時設定の保存先 |
| `TEMPLATE_DIR` | `{BASE_DIR}/templates/` | Jinja2 テンプレートディレクトリ |

`CONFIG_DIR` と `TEMPLATE_DIR` はインポート時に自動生成（`os.makedirs(..., exist_ok=True)`）されるため、手動での作成は不要です。

`data/` ディレクトリは gitignore 対象であり、実行時の全状態を保持します：

```
data/
├── topology.clab.yml               # 最後にレンダリングされた Containerlab トポロジ
├── topology_state.json             # 現在の UI 編集状態（React Flow）
├── topology_deployed_state.json    # 最後のデプロイ時の状態
├── topology_deployed_data.json     # 内部デプロイメタデータ（destroy 時に削除）
└── {topology_name}/                # トポロジごとのルーター設定ディレクトリ
    └── {node_name}/
        ├── daemons                 # FRR デーモンの有効/無効リスト
        ├── frr.conf                # 適用済みの FRR ルーティング設定
        └── vtysh.conf              # vtysh 統合設定フラグ
```

---

## Orchestrator クラス（`orchestrator.py`）

`Orchestrator` はコンテナ管理・設定レンダリング・状態永続化を担うコアクラスです。APIリクエストごとに新しいインスタンスが生成されます（ステートレス設計）。

### パブリックメソッド

| メソッド | 説明 |
|---|---|
| `deploy_topology(topology_data)` | `topology.clab.yml` をレンダリングし `containerlab deploy` を実行 |
| `destroy_topology()` | `containerlab destroy` を実行し設定ディレクトリを削除 |
| `get_topology_status()` | `containerlab inspect` を実行してノード状態を返す |
| `configure_node(node_name, config_data)` | コンテナにインターフェース/VLAN/ルーティング設定を適用 |
| `get_runtime_info(node_name, info_type)` | コンテナ内で診断コマンドを実行 |
| `configure_interface_state(node_name, interface_name, state)` | インターフェースを `up`/`down` に切り替える |
| `save_topology_state(state_data, deployed?)` | UI 状態の JSON をファイルに永続化 |
| `get_topology_state(deployed?)` | ファイルから永続化された UI 状態 JSON を読み込む |
| `delete_topology_state()` | 状態 JSON ファイルを削除 |
| `get_topology_filepath()` | レンダリングされた topology.clab.yml ファイルの絶対パスを返す |

### プライベート/内部メソッド

| メソッド | 説明 |
|---|---|
| `_get_container_by_name(node_name)` | コンテナ名または Containerlab の命名規則でコンテナを解決 |
| `_run_cmd(cmd)` | サブプロセスを実行。containerlab コマンドには `sudo` を付与 |
| `_sync_vlan_interfaces(container, target_vlans)` | コンテナ内の VLAN サブインターフェースを同期 |

### コンストラクタ

```python
orchestrator = Orchestrator()
```

- `docker.from_env()` で Docker デーモンへの接続を試みます。Docker が利用できない場合は `self.docker_client = None` となります（例外は発生しません）。
- `TEMPLATE_DIR` を指す Jinja2 `Environment` を設定します。

---

## Jinja2 テンプレート

### `frr.conf.j2` — FRR ルーティング設定

このテンプレートは FRR の設定ファイルを生成します。FRR（Free Range Routing）は Linux 用のルーティングスイートで、OSPF・RIP・BGP をサポートします。

**テンプレート変数：**

| 変数 | 型 | 説明 |
|---|---|---|
| `interfaces` | Listの辞書 | `name` と任意の `ip_address` を持つ物理インターフェース |
| `vlan_interfaces` | Listの辞書 | `name` と任意の `ip_address` を持つ VLAN サブインターフェース |
| `routing` | 辞書 | `ospf`、`rip`、`bgp` サブ辞書を含む |
| `static_routes` | Listの辞書 | `destination`（CIDR）と `next_hop`（IP）を持つエントリ |

**テンプレート構造：**

```
log file /var/log/frr/frr.log
!
# インターフェースブロック（物理 + VLAN）
interface {name}
  ip address {ip_address}
!

# OSPF ブロック（routing.ospf.enabled が true の場合）
router ospf
  ospf router-id {router_id}
  network {net} area {area_id}
  area {area_id} stub|nssa|...
  area {area_id} range {range}
  redistribute connected|static|rip|bgp
  default-information originate [always] [metric N]
!

# RIP ブロック（routing.rip.enabled が true の場合）
router rip
  network {net}
  redistribute connected|static|ospf|bgp
!

# BGP ブロック（routing.bgp.enabled が true の場合）
router bgp {as_number}
  bgp router-id {router_id}
  no bgp ebgp-requires-policy
  neighbor {ip} remote-as {remote_as}
!
  address-family ipv4 unicast
    neighbor {ip} activate
    redistribute connected|static|ospf|rip
  exit-address-family
!

# スタティックルート
ip route {destination} {next_hop}
```

**FRR 設定の注意事項：**

- `!` はコメント/セパレータとして使用されます
- `no bgp ebgp-requires-policy` は常に含まれます — ラボ環境での eBGP セッションに明示的なルートポリシーが不要になります
- プロトコル間の再配送は条件付きです（例：OSPF での `redistribute rip` は RIP が有効な場合のみ出力されます）

### `topology.clab.yml.j2` — Containerlab トポロジ

このテンプレートは `containerlab deploy` が消費する YAML トポロジファイルを生成します。

**テンプレート変数：**

| 変数 | 型 | 説明 |
|---|---|---|
| `topology_name` | str | Containerlab トポロジ名（コンテナ名の名前空間） |
| `nodes` | Listの辞書 | `name`、`type`、`interfaces` を持つノードリスト |
| `links` | Listの辞書 | `"nodename:interface"` 形式の `endpoints` リストを持つリンク |
| `config_dir` | str | バインドマウント用の `data/` への絶対パス |

**ノードタイプ別 Docker イメージ：**

| `node.type` | Docker イメージ |
|---|---|
| `router` | `alpine-frr:latest` |
| `switch` | `alpine-switch:latest` |
| それ以外 | `alpine-terminal:latest` |

**ルーターのバインドマウント：**

ルーターノードには、`{config_dir}/{topology_name}/{node_name}/` 以下の 3 ファイルが `/etc/frr/` に読み取り専用でマウントされます：

| ホストファイル | コンテナパス | 用途 |
|---|---|---|
| `daemons` | `/etc/frr/daemons` | FRR デーモンの有効/無効 |
| `frr.conf` | `/etc/frr/frr.conf.import` | 起動時の初期 FRR 設定 |
| `vtysh.conf` | `/etc/frr/vtysh.conf` | 統合 vtysh 設定を有効化 |

**Exec コマンド：** 各ノードのインターフェースリストに対して `ip link set dev {iface} up` が実行され、コンテナ起動直後にインターフェースが有効化されます。

---

## FRR インテグレーション

### デーモン

すべてのルーターノードで以下の FRR デーモンが有効化されます：

| デーモン | プロトコル |
|---|---|
| `zebra` | コア IP ルーティング（他のデーモンすべてが依存） |
| `bgpd` | BGP（Border Gateway Protocol） |
| `ospfd` | OSPF（Open Shortest Path First） |
| `ripd` | RIP（Routing Information Protocol） |

その他のデーモン（`ospf6d`、`ripngd`、`isisd` など）は無効化されています。

### `frr-reload.py` によるゼロダウンタイム設定変更

ルーターノードに対して `configure_node()` が呼ばれると：

1. Jinja2 テンプレートから新しい `frr.conf` がレンダリングされる
2. レンダリングされた設定がコンテナ内の `/etc/frr/frr.conf.new` に書き込まれる
3. コンテナ内で `/usr/lib/frr/frr-reload.py --reload /etc/frr/frr.conf.new` が実行される

`frr-reload.py` は FRR 組み込みのホットリロードツールです：
- 実行中の設定（`vtysh -c "show running-config"`）と新しいファイルを比較
- 差分を計算し、最小限の `vtysh` コマンドを生成
- デーモン再起動なしに差分のみを適用

バックエンドはリロード前に最大 30 秒間 vtysh の応答を待ちます（1 秒ごとに `vtysh -c "write"` でポーリング）。

### `vtysh`

`vtysh` は FRR の統合 CLI ツールです。以下の用途で使用されます：
- 準備確認：`vtysh -c "write"`
- 実行時クエリ：`vtysh -c "show ip route"`、`vtysh -c "show ip ospf neighbor"` など

---

## コンテナ名の解決

Containerlab はコンテナを `clab-{topology_name}-{node_name}` と命名します。例えば、トポロジ `sim-network` のノード `r1` は `clab-sim-network-r1` というコンテナ名になります。

`_get_container_by_name(node_name)` は次の 3 段階で解決を試みます：

1. **完全一致**：`container.name == node_name`
2. **Containerlab 命名規則**：`container.name == f"clab-{topo_name}-{node_name}"`（`topology.clab.yml` からトポロジ名を読み込む）
3. **サフィックス一致**（トポロジファイルなし）：`container.name.endswith(f"-{node_name}")`

コンテナが見つからない場合は `None` を返します。

---

## sudo 要件

`containerlab` コマンドは root 権限が必要です。`_run_cmd()` は以下の条件で自動的に `sudo` を先頭に付与します：
- コマンドが `"containerlab"` で始まる、かつ
- プロセスが root として実行されていない（`os.getuid() != 0`）

---

## アプリケーションライフサイクル

`main.py` には `lifespan` コンテキストマネージャが登録されており：
- **起動時**：何もしない（yield）
- **シャットダウン時**：`orchestrator.destroy_topology()` を呼び出し、実行中のコンテナをクリーンアップ

CORS はすべてのオリジンを許可（`allow_origins=["*"]`）するよう設定されており、ローカル開発に適しています。

---

## ナビゲーション

- [API リファレンス概要](./api-reference/index.ja.md)
- [トポロジエンドポイント](./api-reference/topology.ja.md)
- [ノードエンドポイント](./api-reference/nodes.ja.md)
- [WebSocket ターミナル](./api-reference/websocket.ja.md)
- [Pydantic スキーマ](./api-reference/schemas.ja.md)
