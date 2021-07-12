FROM debian:buster-slim AS base
ARG DEBIAN_FRONTEND=noninteractive
RUN apt-get update -qq

FROM debian:buster-slim AS k8s_utils
ARG DEBIAN_FRONTEND=noninteractive
ARG KUBECTL_VERSION=1.21.2
ARG HELM_VERSION=3.6.2-1
# install kubectl
ADD https://dl.k8s.io/release/v$KUBECTL_VERSION/bin/linux/amd64/kubectl /usr/local/bin/kubectl
ADD https://dl.k8s.io/release/v$KUBECTL_VERSION/bin/linux/amd64/kubectl.sha256 /var/tmp/kubectl.sha256
RUN echo "$(cat /var/tmp/kubectl.sha256)  /usr/local/bin/kubectl" | sha256sum --check
RUN chmod +x /usr/local/bin/kubectl
COPY --from=base /var/lib/apt/lists/ /var/lib/apt/lists/
RUN apt-get install --no-install-recommends -qqq -y \
        apt-utils \
        ca-certificates \
        gnupg2
# install helm repo
ADD https://baltocdn.com/helm/signing.asc /var/tmp/helm_signing.asc
RUN apt-key add /var/tmp/helm_signing.asc
RUN echo "deb https://baltocdn.com/helm/stable/debian/ all main" | tee /etc/apt/sources.list.d/helm-stable-debian.list
RUN apt-get update -qq
RUN apt-get install --no-install-recommends -qqq -y helm=$HELM_VERSION

FROM debian:buster-slim AS lolcat_builder
ARG DEBIAN_FRONTEND=noninteractive
COPY --from=base /var/lib/apt/lists/ /var/lib/apt/lists/
RUN apt-get install --no-install-recommends -qqq -y ca-certificates cargo
RUN cargo install --quiet --root /usr/local lolcat

FROM debian:buster-slim AS aws_cli
ARG DEBIAN_FRONTEND=noninteractive
ARG AWS_CLI_V2_VERSION=2.2.18
COPY --from=base /var/lib/apt/lists/ /var/lib/apt/lists/
RUN apt-get install --no-install-recommends -qqq -y apt-utils unzip gnupg2
ADD https://awscli.amazonaws.com/awscli-exe-linux-x86_64-$AWS_CLI_V2_VERSION.zip /var/tmp/awscliv2.zip
ADD https://awscli.amazonaws.com/awscli-exe-linux-x86_64-$AWS_CLI_V2_VERSION.zip.sig /var/tmp/awscliv2.sig
RUN echo "-----BEGIN PGP PUBLIC KEY BLOCK-----\n\
\n\
mQINBF2Cr7UBEADJZHcgusOJl7ENSyumXh85z0TRV0xJorM2B/JL0kHOyigQluUG\n\
ZMLhENaG0bYatdrKP+3H91lvK050pXwnO/R7fB/FSTouki4ciIx5OuLlnJZIxSzx\n\
PqGl0mkxImLNbGWoi6Lto0LYxqHN2iQtzlwTVmq9733zd3XfcXrZ3+LblHAgEt5G\n\
TfNxEKJ8soPLyWmwDH6HWCnjZ/aIQRBTIQ05uVeEoYxSh6wOai7ss/KveoSNBbYz\n\
gbdzoqI2Y8cgH2nbfgp3DSasaLZEdCSsIsK1u05CinE7k2qZ7KgKAUIcT/cR/grk\n\
C6VwsnDU0OUCideXcQ8WeHutqvgZH1JgKDbznoIzeQHJD238GEu+eKhRHcz8/jeG\n\
94zkcgJOz3KbZGYMiTh277Fvj9zzvZsbMBCedV1BTg3TqgvdX4bdkhf5cH+7NtWO\n\
lrFj6UwAsGukBTAOxC0l/dnSmZhJ7Z1KmEWilro/gOrjtOxqRQutlIqG22TaqoPG\n\
fYVN+en3Zwbt97kcgZDwqbuykNt64oZWc4XKCa3mprEGC3IbJTBFqglXmZ7l9ywG\n\
EEUJYOlb2XrSuPWml39beWdKM8kzr1OjnlOm6+lpTRCBfo0wa9F8YZRhHPAkwKkX\n\
XDeOGpWRj4ohOx0d2GWkyV5xyN14p2tQOCdOODmz80yUTgRpPVQUtOEhXQARAQAB\n\
tCFBV1MgQ0xJIFRlYW0gPGF3cy1jbGlAYW1hem9uLmNvbT6JAlQEEwEIAD4WIQT7\n\
Xbd/1cEYuAURraimMQrMRnJHXAUCXYKvtQIbAwUJB4TOAAULCQgHAgYVCgkICwIE\n\
FgIDAQIeAQIXgAAKCRCmMQrMRnJHXJIXEAChLUIkg80uPUkGjE3jejvQSA1aWuAM\n\
yzy6fdpdlRUz6M6nmsUhOExjVIvibEJpzK5mhuSZ4lb0vJ2ZUPgCv4zs2nBd7BGJ\n\
MxKiWgBReGvTdqZ0SzyYH4PYCJSE732x/Fw9hfnh1dMTXNcrQXzwOmmFNNegG0Ox\n\
au+VnpcR5Kz3smiTrIwZbRudo1ijhCYPQ7t5CMp9kjC6bObvy1hSIg2xNbMAN/Do\n\
ikebAl36uA6Y/Uczjj3GxZW4ZWeFirMidKbtqvUz2y0UFszobjiBSqZZHCreC34B\n\
hw9bFNpuWC/0SrXgohdsc6vK50pDGdV5kM2qo9tMQ/izsAwTh/d/GzZv8H4lV9eO\n\
tEis+EpR497PaxKKh9tJf0N6Q1YLRHof5xePZtOIlS3gfvsH5hXA3HJ9yIxb8T0H\n\
QYmVr3aIUes20i6meI3fuV36VFupwfrTKaL7VXnsrK2fq5cRvyJLNzXucg0WAjPF\n\
RrAGLzY7nP1xeg1a0aeP+pdsqjqlPJom8OCWc1+6DWbg0jsC74WoesAqgBItODMB\n\
rsal1y/q+bPzpsnWjzHV8+1/EtZmSc8ZUGSJOPkfC7hObnfkl18h+1QtKTjZme4d\n\
H17gsBJr+opwJw/Zio2LMjQBOqlm3K1A4zFTh7wBC7He6KPQea1p2XAMgtvATtNe\n\
YLZATHZKTJyiqA==\n\
=vYOk\n\
-----END PGP PUBLIC KEY BLOCK-----" > /var/tmp/aws-cli.key
RUN gpg --import /var/tmp/aws-cli.key
RUN gpg --verify /var/tmp/awscliv2.sig /var/tmp/awscliv2.zip
RUN unzip -q -d /tmp /var/tmp/awscliv2.zip
RUN mkdir /aws-cli-bin
RUN /tmp/aws/install --bin-dir /aws-cli-bin/

FROM pulumi/pulumi-python
ARG DEBIAN_FRONTEND=noninteractive
COPY --from=lolcat_builder /usr/local/bin/lolcat /usr/local/bin/
COPY --from=k8s_utils /usr/bin/helm /usr/local/bin/
COPY --from=k8s_utils /usr/local/bin/kubectl /usr/local/bin/
COPY --from=aws_cli /usr/local/aws-cli/ /usr/local/aws-cli/
COPY --from=aws_cli /aws-cli-bin/ /usr/local/bin/
RUN set -eux; \
    apt-get update -qq; \
    apt-get install --no-install-recommends -qqq -y \
        ca-certificates \
        docker.io \
        figlet \
        groff-base \
        less \
        nodejs \
        python3-wheel; \
    mkdir -p /pulumi/projects/kic-reference-architectures; \
    apt-get purge -y --auto-remove -o APT::AutoRemove::RecommendsImportant=false; \
    rm -rf /var/lib/apt/lists/* /var/tmp/* /tmp/* /usr/share/man/*
WORKDIR /pulumi/projects/kic-reference-architectures