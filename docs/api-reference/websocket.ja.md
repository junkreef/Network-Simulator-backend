> 🇬🇧 English version available → [websocket.md](./websocket.md)

# WebSocket ターミナルプロキシ

WebSocket ターミナルエンドポイントは、ブラウザベースのターミナル（Xterm.js）と実行中の Docker コンテナ内のシェルを双方向にパイプ接続します。これにより、ユーザーはブラウザ UI からトポロジ内の任意のノードと直接インタラクションできます。

---

## エンドポイント

```
ws://localhost:8000/api/v1/ws/terminal/{node_name}
```

> **注意**: WebSocket ルーターは REST エンドポイントと同じ `/api/v1` プレフィックスにマウントされています。フルパスは `/api/v1/ws/terminal/{node_name}` です。

### パスパラメータ

| パラメータ | 型 | 説明 |
|---|---|---|
| `node_name` | string | トポロジで定義されたノード名（例: `"r1"`、`"pc1"`）。Docker コンテナの特定に使用。 |

---

## プロトコル

| プロパティ | 値 |
|---|---|
| **プロトコル** | ネイティブ WebSocket（RFC 6455） |
| **メッセージ形式** | テキストフレーム（UTF-8 エンコード文字列） |
| **サブプロトコル** | なし |
| **認証** | なし |

メッセージは**テキストフレーム**です。フロントエンドは以下を送信します：
- **JSON コントロールメッセージ**（ターミナルのリサイズと入力イベント用）、または
- **生のテキスト文字列**（JSON にラップされないターミナルのキーストローク）

バイナリフレームも受け付けられ、コンテナに直接転送されます。

---

## 接続ライフサイクル

```
1. クライアントが ws://localhost:8000/api/v1/ws/terminal/{node_name} に WebSocket を開く
2. サーバーが接続を受け入れる（await websocket.accept()）
3. サーバーが Docker の可用性を確認 — 利用不可の場合はコード 4001 でクローズ
4. サーバーが node_name のコンテナを特定 — 見つからない場合はコード 4004 でクローズ
5. サーバーが Docker exec セッションを作成：
     exec_create(container.id, cmd=["/bin/bash"], stdin=True, stdout=True, stderr=True, tty=True)
6. socket=True で exec セッションを開始してソケットを取得
7. サーバーが anyio.create_task_group() で 2 つの並行 async タスクを起動：
     - docker_to_ws: Docker ソケットから読み取り → WebSocket クライアントに送信
     - ws_to_docker: WebSocket クライアントから受信 → Docker ソケットに書き込み
8. どちらかのタスクが終了するまで両タスクが実行される（切断・コンテナ終了・エラー）
9. サーバーが Docker ソケットを閉じ、クリーンアップをログに記録
```

---

## メッセージ形式

### サーバー → クライアント（コンテナ出力）

Docker exec API は `tty=True` の場合、生のバイトストリーム（フレームなし）を使用します。ただし、実装は Docker 多重化ストリームプロトコルを読み取ります：

- **ヘッダー**: 8 バイト。バイト 4〜7（ビッグエンディアン uint32）がペイロードサイズを示す。
- **ペイロード**: UTF-8 エンコードのターミナル出力。

ペイロードは UTF-8 文字列にデコードされ、**WebSocket テキストフレーム**として送信されます。

### クライアント → サーバー（キーストローク / コマンド）

クライアントは 3 種類の形式で**テキストフレーム**を送信します：

#### 1. リサイズイベント（JSON）

```json
{
  "event": "resize",
  "cols": 220,
  "rows": 50
}
```

サーバーは `client.api.exec_resize(exec_id, height=rows, width=cols)` を呼び出して TTY のサイズを更新します。ブラウザウィンドウのリサイズ時の出力折り返し問題を防ぎます。

#### 2. 入力イベント（JSON）

```json
{
  "event": "input",
  "data": "ls -la\r"
}
```

`data` フィールドが UTF-8 にエンコードされ、Docker ソケットに書き込まれます（`real_sock.sendall(data.encode("utf-8"))`）。

#### 3. 生テキスト（非 JSON）

有効な JSON でないテキストは生のターミナル入力として扱われ、直接転送されます：

```
ls\r
```

Xterm.js がキーストロークを JSON にラップせず直接文字列として送信する場合に対応します。

#### 4. バイナリフレーム

バイナリ WebSocket フレームはバイト単位で Docker ソケットに転送されます（`real_sock.sendall(bytes_data)`）。

---

## WebSocket クローズコード

| コード | 意味 | 送信タイミング |
|---|---|---|
| `4001` | Docker デーモン利用不可 | 接続時に `orchestrator.docker_client` が `None` |
| `4004` | コンテナが見つからない | `_get_container_by_name(node_name)` が `None` を返す |
| `4005` | ターミナル exec の起動失敗 | `exec_create` または `exec_start` で例外が発生 |

---

## コンテナ名の解決

サーバーは `_get_container_by_name(node_name)` を使って Docker コンテナを特定します。3 つの戦略を順に試みます：

1. 完全一致: `container.name == node_name`
2. Containerlab 命名規則: `container.name == f"clab-{topology_name}-{node_name}"`（`data/topology.clab.yml` からトポロジ名を読み込む）
3. サフィックス一致（トポロジファイルなし）: `container.name.endswith(f"-{node_name}")`

一致するコンテナが見つからない場合は `None` を返します。

---

## 非同期実装

WebSocket ハンドラーは `anyio` を使って並行 async I/O を実現しています：

```python
async with anyio.create_task_group() as tg:
    tg.start_soon(docker_to_ws)
    tg.start_soon(ws_to_docker)
```

両タスクは並行して実行されます。どちらかが終了すると（切断・エラー・コンテナ終了）、タスクグループがもう一方をキャンセルし、ハンドラーがクリーンアップを行います。

ブロッキングな Docker ソケット操作は `anyio.to_thread.run_sync()` でスレッドプールにオフロードされ、async イベントループのブロッキングを回避します：

```python
header = await anyio.to_thread.run_sync(lambda: _read_exactly(8))
payload = await anyio.to_thread.run_sync(lambda: _read_exactly(size))
await anyio.to_thread.run_sync(real_sock.sendall, input_data.encode("utf-8"))
```

### `_unwrap_socket()`

Docker SDK はソケットを複数の層でラップします。`_unwrap_socket()` は `_sock`、`socket`、`_socket`、`raw` 属性を確認しながらアンラップし、基盤となる OS ソケットに到達します：

```python
def _unwrap_socket(sock):
    real_sock = sock
    for attr in ["_sock", "socket", "_socket", "raw"]:
        if hasattr(real_sock, attr):
            val = getattr(real_sock, attr)
            if val is not None:
                real_sock = val
    return real_sock
```

`sendall()` を直接呼び出してコンテナの stdin に書き込むために生ソケットが必要です。

---

## シーケンス図

```
ブラウザ (Xterm.js)          FastAPI WS ハンドラー          Docker コンテナ (/bin/bash)
       |                            |                                  |
       |-- WS 接続 (GET upgrade) -->|                                  |
       |                            |-- exec_create(/bin/bash) ------->|
       |                            |-- exec_start(socket=True) ------>|
       |<-- WS accept -------------|                                  |
       |                            |                                  |
       |              [docker_to_ws タスク実行中]                      |
       |                            |<-- Docker ストリームヘッダー(8B) -|
       |                            |<-- Docker ストリームペイロード ---|
       |<-- send_text(出力) --------|                                  |
       |                            |                                  |
       |              [ws_to_docker タスク実行中]                      |
       |-- send_text(JSON input) -->|                                  |
       |                            |-- real_sock.sendall(data) ------>|
       |                            |                                  |
       |-- send_text(JSON resize) ->|                                  |
       |                            |-- exec_resize(cols, rows) ------>|
       |                            |                                  |
       |-- WS 切断 --------------->|                                  |
       |                            |-- real_sock.close() ------------>|
       |                            |                                  |
```

---

## フロントエンド統合例

```typescript
import { Terminal } from 'xterm';

const nodeName = 'r1';
const ws = new WebSocket(`ws://localhost:8000/api/v1/ws/terminal/${nodeName}`);
const terminal = new Terminal();

// DOM 要素にターミナルをマウント
terminal.open(document.getElementById('terminal-container'));

// コンテナ出力を Xterm.js ターミナルに書き込む
ws.onmessage = (event) => {
  terminal.write(event.data);
};

// キーストロークを JSON 入力イベントとして送信
terminal.onData((data) => {
  ws.send(JSON.stringify({ event: 'input', data }));
});

// ターミナルリサイズ時にリサイズイベントを送信
terminal.onResize(({ cols, rows }) => {
  ws.send(JSON.stringify({ event: 'resize', cols, rows }));
});

// 切断処理
ws.onclose = () => {
  terminal.write('\r\n[接続が閉じられました]\r\n');
};
```

---

## シェルと実行環境

exec セッションは `/bin/bash` で開始されます：

```python
shell = "/bin/bash"
exec_inst = client.api.exec_create(container.id, cmd=[shell], stdin=True, stdout=True, stderr=True, tty=True)
```

シェルプロセスはコンテナ内で実行され、すべてのコンテナネットワークツールに完全にアクセスできます：
- `ip`、`ping`、`traceroute`、`ss`、`netstat`（ネットワーク診断用）
- `vtysh`（FRR ルーター用 — インタラクティブ FRR CLI）
- `bridge`（スイッチノード用 — VLAN 確認）

---

## 注意事項と制限

| 項目 | 説明 |
|---|---|
| **ターミナルリサイズ** | JSON `{"event": "resize", "cols": N, "rows": N}` メッセージでリサイズをサポート。exec 作成時の初期サイズは明示的に設定されない（Docker のデフォルト: 80×24）。 |
| **複数接続** | 同じノードに複数の WebSocket クライアントが同時接続可能。各接続は独立した exec セッションを作成。 |
| **コンテナ再起動** | WebSocket 接続中にコンテナが再起動すると、exec セッションのパイプが切断される。`docker_to_ws` ループが読み取りエラーで終了し、接続がクローズされる。 |
| **セキュリティ** | 認証なし。バックエンドへのネットワークアクセスがあるクライアントは、実行中の任意のコンテナにターミナルを開くことができる。 |

---

## ナビゲーション

- [← API リファレンス概要](./index.ja.md)
- [← ノードエンドポイント](./nodes.ja.md)
- [Pydantic スキーマ →](./schemas.ja.md)
- [バックエンド開発者ガイド](../development.ja.md)
