> 🇬🇧 English version available → [README.md](./README.md)

# Network Simulator — バックエンド

**Network Simulator** のバックエンド — Containerlab 経由で Docker コンテナを管理し、コンテナ内の FRR ルーティングを設定する FastAPI アプリケーション。

フロントエンドからの REST API・WebSocket リクエストを受け取り、ネットワークトポロジーのデプロイ、ルーティングプロトコル（OSPF・RIP・BGP）の設定、稼働中のコンテナへのリアルタイムターミナルアクセスを提供します。

## クイックスタート

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
.venv/bin/uvicorn src.app.main:app --host 0.0.0.0 --port 8000 --reload
```

API サーバーは **http://localhost:8000** で起動します。  
**http://localhost:8000/docs** で Swagger UI による対話型 API ドキュメントを確認できます。

## 技術スタック

| ツール | 用途 |
|---|---|
| **FastAPI** | REST API・WebSocket サーバー |
| **Pydantic** | リクエスト/レスポンスのスキーマ検証 |
| **Docker SDK** | コンテナライフサイクル管理 |
| **Containerlab** | 宣言的なコンテナネットワーキング |
| **FRR** | OSPF・RIP・BGP ルーティングデーモン |
| **Jinja2** | 設定ファイル生成（frr.conf、topology.clab.yml） |
| **pytest** | ユニット・インテグレーションテスト |

## ドキュメント

- **[開発ガイド](./docs/development.ja.md)** — セットアップ・テスト・Orchestrator 内部・Jinja2 テンプレート
- **[API リファレンス](./docs/api-reference/index.ja.md)** — 全 REST エンドポイント・WebSocket プロトコル・Pydantic スキーマ
