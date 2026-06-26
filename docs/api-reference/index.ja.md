> 🇬🇧 English version available → [index.md](./index.md)

# API リファレンス — Network Simulator バックエンド

このドキュメントは、Network Simulator バックエンド（FastAPI）が公開するすべての API エンドポイントの概要を提供します。各エンドポイントグループの詳細なドキュメントは、以下のエンドポイント一覧のリンクからご覧ください。

---

## 接続情報

| プロパティ | 値 |
|---|---|
| **ベース URL** | `http://localhost:8000` |
| **API バージョンプレフィックス** | `/api/v1`（全 REST エンドポイント） |
| **WebSocket ベース** | `ws://localhost:8000` |
| **認証** | なし — ローカル開発ツールのため不要 |
| **Content-Type** | リクエストボディは `application/json` |

---

## 認証

認証は不要です。バックエンドはローカルツールとして設計されており、認証機構は実装されていません。CORS はすべてのオリジン（`*`）を許可するよう設定されています。

---

## 標準エラーレスポンス形式

すべてのエラーレスポンスは FastAPI のデフォルト形式に従います：

```json
{
  "detail": "エラーの説明文字列"
}
```

HTTP 422（Unprocessable Entity — Pydantic バリデーション失敗）の場合：

```json
{
  "detail": [
    {
      "loc": ["body", "field_name"],
      "msg": "field required",
      "type": "value_error.missing"
    }
  ]
}
```

---

## HTTP ステータスコード

| コード | 意味 |
|---|---|
| `200` | 成功 — リクエストが正常に処理された |
| `400` | 不正なリクエスト — クエリパラメータの値が無効 |
| `422` | 処理不可能なエンティティ — Pydantic スキーマ検証失敗 |
| `500` | 内部サーバーエラー — Docker/Containerlab/コンテナ実行の失敗 |

---

## エンドポイント一覧

| メソッド | エンドポイント | 説明 | リファレンス |
|---|---|---|---|
| `GET` | `/` | ヘルスチェック | — |
| `POST` | `/api/v1/topology/deploy` | Containerlab トポロジをデプロイ | [topology.ja.md](./topology.ja.md#post-apiv1topologydeploy) |
| `POST` | `/api/v1/topology/destroy` | 実行中のトポロジを破棄 | [topology.ja.md](./topology.ja.md#post-apiv1topologydestroy) |
| `GET` | `/api/v1/topology/status` | 全ノードの実行時ステータスを取得 | [topology.ja.md](./topology.ja.md#get-apiv1topologystatus) |
| `GET` | `/api/v1/topology/state` | 保存済み UI トポロジ状態を取得 | [topology.ja.md](./topology.ja.md#get-apiv1topologystate) |
| `POST` | `/api/v1/topology/state` | UI トポロジ状態を保存 | [topology.ja.md](./topology.ja.md#post-apiv1topologystate) |
| `DELETE` | `/api/v1/topology/state` | トポロジ状態をリセット/削除 | [topology.ja.md](./topology.ja.md#delete-apiv1topologystate) |
| `POST` | `/api/v1/nodes/{node_name}/configure` | ノードのインターフェースとルーティングを設定 | [nodes.ja.md](./nodes.ja.md#post-apiv1nodesnodenameconfigure) |
| `GET` | `/api/v1/nodes/{node_name}/runtime-info` | 実行時の診断情報を取得 | [nodes.ja.md](./nodes.ja.md#get-apiv1nodesnodenameruntime-info) |
| `POST` | `/api/v1/nodes/{node_name}/interfaces/{interface_name}/state` | インターフェースを up/down に設定 | [nodes.ja.md](./nodes.ja.md#post-apiv1nodesnodenamedinterfacesinterface_namestate) |
| `WS` | `/api/v1/ws/terminal/{node_name}` | WebSocket ターミナルプロキシ | [websocket.ja.md](./websocket.ja.md) |

---

## ヘルスチェック

### `GET /`

サーバーのヘルス状態を返します。プレフィックスなし — このエンドポイントはルートにあります。

**レスポンス：**

```json
{
  "status": "healthy",
  "project": "Network Simulator",
  "version": "1.0.0"
}
```

---

## エンドポイントグループ別ドキュメント

| ドキュメント | 内容 |
|---|---|
| [topology.ja.md](./topology.ja.md) | トポロジ管理のデプロイ・破棄・ステータス・状態エンドポイント |
| [nodes.ja.md](./nodes.ja.md) | ノード設定・実行時情報・インターフェース状態エンドポイント |
| [websocket.ja.md](./websocket.ja.md) | WebSocket ターミナルプロキシ — プロトコル・メッセージ形式・ライフサイクル |
| [schemas.ja.md](./schemas.ja.md) | フィールドレベルのドキュメントを含む完全な Pydantic スキーマリファレンス |

---

## 関連ドキュメント

- [バックエンド開発者ガイド](../development.ja.md)
