import hashlib

PALETTE: list[tuple[int, int, int]] = [
    (66, 133, 244),
    (219, 68, 55),
    (244, 180, 0),
    (15, 157, 88),
    (171, 71, 188),
    (0, 172, 193),
    (255, 112, 67),
    (158, 157, 36),
    (92, 107, 192),
    (0, 121, 107),
]


def color_for_resource_class(resource_class: str) -> tuple[int, int, int]:
    digest = hashlib.sha256(resource_class.encode("utf-8")).digest()
    index = digest[0] % len(PALETTE)
    return PALETTE[index]
