# Собирает бинарник timetrace на указанной базе (BASE_IMAGE) вместо
# машины разработчика, чтобы не требовать более новую glibc, чем есть
# у пользователей (см. packaging/docker/README.md). Варианты базы
# задаёт build_in_docker.sh. Python 3.14 в старых Ubuntu нет,
# поэтому берём standalone-сборку через uv.
ARG BASE_IMAGE=ubuntu:22.04
FROM ${BASE_IMAGE}

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    curl \
    build-essential \
    pkg-config \
    libffi-dev \
    libwayland-dev \
    wayland-protocols \
    libgl1 \
    libegl1 \
    libxkbcommon0 \
    libxkbcommon-x11-0 \
    libfontconfig1 \
    libfreetype6 \
    libdbus-1-3 \
    libglib2.0-0 \
    libsm6 \
    libxcb-cursor0 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxcomposite1 \
    libxi6 \
    libxrender1 \
    libxrandr2 \
    libxtst6 \
    libnss3 \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR=/usr/local/bin sh
ENV UV_PYTHON_INSTALL_DIR=/opt/python
RUN uv venv --python 3.14 /opt/venv
ENV PATH="/opt/venv/bin:$PATH" VIRTUAL_ENV=/opt/venv

ENV QT_QPA_PLATFORM=offscreen

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
COPY packaging/entry_point.py packaging/pyinstaller.spec ./packaging/

# pywayland: колесо на PyPI требует glibc >= 2.34, собираем из исходников.
RUN uv pip install --no-cache --no-binary pywayland "." pyinstaller

RUN cd packaging && pyinstaller --noconfirm pyinstaller.spec

CMD ["true"]
