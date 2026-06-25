FROM alpine:3.18

# SSL証明書エラーを回避するため、リポジトリをHTTPに変更
RUN sed -i 's/https/http/g' /etc/apk/repositories

# ネットワークテスト用パッケージのインストール
RUN apk add --no-cache \
    bash \
    iproute2 \
    net-tools \
    iputils \
    curl \
    tcpdump \
    iperf3 \
    mtr

# コンテナが即座に終了するのを防ぐためのデフォルトコマンド
CMD ["sleep", "infinity"]
