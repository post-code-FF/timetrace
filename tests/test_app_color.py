from timetrace.app_color import PALETTE, color_for_resource_class


def test_same_resource_class_always_gets_same_color():
    assert color_for_resource_class("firefox") == color_for_resource_class("firefox")


def test_color_comes_from_palette():
    assert color_for_resource_class("firefox") in PALETTE


def test_different_classes_can_get_different_colors():
    colors = {color_for_resource_class(name) for name in ["firefox", "code", "kate", "konsole", "gimp"]}
    assert len(colors) > 1
