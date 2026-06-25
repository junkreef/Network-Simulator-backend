FROM alpine:3.18

# SSL証明書エラーを回避するため、リポジトリをHTTPに変更
RUN sed -i 's/https/http/g' /etc/apk/repositories

# 必要パッケージのインストール (FRR, Python3, ネットワーク診断ツール)
RUN apk add --no-cache \
    frr \
    frr-pythontools \
    python3 \
    bash \
    iproute2 \
    net-tools \
    iputils \
    tcpdump \
    tini \
    mtr

# ルーティングデーモンの設定 (daemonsファイル)
# デフォルトで zebra, ospfd, bgpd, ripd を有効化するように設定
RUN sed -i 's/zebra=no/zebra=yes/g' /etc/frr/daemons && \
    sed -i 's/bgpd=no/bgpd=yes/g' /etc/frr/daemons && \
    sed -i 's/ospfd=no/ospfd=yes/g' /etc/frr/daemons && \
    sed -i 's/ripd=no/ripd=yes/g' /etc/frr/daemons

# 適切なオーナーシップとパーミッションの設定
RUN chown -R frr:frr /etc/frr

# エントリポイントに tini を指定し、FRR起動スクリプトを実行する
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["/bin/sh", "-c", "if [ -f /etc/frr/frr.conf.import ]; then cp /etc/frr/frr.conf.import /etc/frr/frr.conf; fi && chown -R frr:frr /etc/frr && chmod 644 /etc/frr/frr.conf || true; /usr/lib/frr/frrinit.sh start && exec sleep infinity"]
