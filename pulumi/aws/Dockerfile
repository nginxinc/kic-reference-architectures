ARG ARCH=amd64

FROM $ARCH/docker:latest AS docker

FROM $ARCH/debian:bullseye-slim
ARG DEBIAN_FRONTEND=noninteractive
ARG UID
ARG GID
ARG DOCKER_GID=999
COPY --from=docker /usr/local/bin/docker /usr/local/bin/docker
RUN set -eux; \
    apt-get update -qq; \
    apt-get install --no-install-recommends -qqq -y \
        build-essential \
        ca-certificates \
        nano \
        python3-venv \
        wget \
        git \
        vim; \
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false; \
    groupadd --gid $DOCKER_GID docker; \
    groupadd --gid $GID runner; \
    mkdir -p /pulumi/projects; \
    useradd --home-dir /pulumi/projects/kic-reference-architectures --groups docker --uid $UID --gid $GID --shell /bin/bash --create-home runner; \
    rm -rf /var/lib/apt/lists/* /var/tmp/* /tmp/* /usr/share/man/* /root/.cache

COPY --chown=runner:runner . /pulumi/projects/kic-reference-architectures

USER runner
WORKDIR /pulumi/projects/kic-reference-architectures

RUN set -eux; \
    /pulumi/projects/kic-reference-architectures/setup_venv.sh; \
    rm -rf /pulumi/projects/kic-reference-architectures/.cache; \
    echo 'source /pulumi/projects/kic-reference-architectures/venv/bin/activate' >> /pulumi/projects/kic-reference-architectures/.bashrc

ENTRYPOINT ["/bin/bash"]
