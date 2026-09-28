# Собирает бинарник timetrace на Debian 12 (bookworm, glibc 2.36) вместо
# машины разработчика, чтобы не требовать более новую glibc, чем есть
# у пользователей (см. packaging/docker/README.md).
FROM python:3.14-slim-bookworm

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    pkg-config \
    libffi-dev \
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

ENV QT_QPA_PLATFORM=offscreen

WORKDIR /build
COPY pyproject.toml ./
COPY src ./src
COPY packaging/entry_point.py packaging/pyinstaller.spec ./packaging/

RUN pip install --no-cache-dir "." pyinstaller

RUN cd packaging && pyinstaller --noconfirm pyinstaller.spec

CMD ["true"]
