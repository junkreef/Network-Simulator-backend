FROM alpine:3.18

# SSLエラー対策としてHTTPミラーを使用
RUN sed -i 's/https/http/g' /etc/apk/repositories

# L2スイッチ用パッケージのインストール
RUN apk add --no-cache \
    bash \
    iproute2 \
    net-tools \
    iputils \
    tcpdump

# コンテナが即座に終了するのを防ぐためのデフォルトコマンド
CMD ["sleep", "infinity"]
