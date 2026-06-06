import logging

logger = logging.getLogger("zzz_scanner.coordinate_scaling")
GAME_ASPECT_RATIO = 16 / 9
WINDOWED_BORDER_WIDTH = 8
WINDOWED_TITLEBAR_HEIGHT = 31


def get_config_base_size(config: dict) -> tuple[int, int] | None:
    base_size = config.get("base_window_size")

    if not isinstance(base_size, dict):
        return None

    width = base_size.get("width")
    height = base_size.get("height")

    if not isinstance(width, int) or not isinstance(height, int):
        return None

    if width <= 0 or height <= 0:
        return None

    return width, height


def get_window_size(window) -> tuple[int, int]:
    return int(window.width), int(window.height)


def scale_value(value: int | float, from_size: int, to_size: int) -> int:
    return int(round(value * to_size / from_size))


def get_game_viewport(size: tuple[int, int]) -> tuple[int, int, int, int]:
    width, height = size
    framed_width = width - WINDOWED_BORDER_WIDTH * 2
    framed_height = height - WINDOWED_TITLEBAR_HEIGHT - WINDOWED_BORDER_WIDTH

    if framed_width > 0 and framed_height > 0:
        framed_ratio = framed_width / framed_height

        if abs(framed_ratio - GAME_ASPECT_RATIO) < 0.01:
            return (
                WINDOWED_BORDER_WIDTH,
                WINDOWED_TITLEBAR_HEIGHT,
                framed_width,
                framed_height,
            )

    viewport_height = int(round(width / GAME_ASPECT_RATIO))

    if viewport_height <= height:
        return 0, height - viewport_height, width, viewport_height

    viewport_width = int(round(height * GAME_ASPECT_RATIO))
    return (width - viewport_width) // 2, 0, viewport_width, height


def scale_axis_value(
    value: int | float,
    from_offset: int,
    from_size: int,
    to_offset: int,
    to_size: int,
) -> int:
    return int(round(to_offset + (value - from_offset) * to_size / from_size))


def scale_roi(roi: dict, from_size: tuple[int, int], to_size: tuple[int, int]) -> dict:
    from_left, from_top, from_width, from_height = get_game_viewport(from_size)
    to_left, to_top, to_width, to_height = get_game_viewport(to_size)

    return {
        "x": scale_axis_value(roi["x"], from_left, from_width, to_left, to_width),
        "y": scale_axis_value(roi["y"], from_top, from_height, to_top, to_height),
        "w": max(1, scale_value(roi["w"], from_width, to_width)),
        "h": max(1, scale_value(roi["h"], from_height, to_height)),
    }


def scale_rois(rois: dict, from_size: tuple[int, int], to_size: tuple[int, int]) -> dict:
    return {
        field_name: scale_roi(roi, from_size, to_size)
        for field_name, roi in rois.items()
    }


def scale_grid_config(config: dict, from_size: tuple[int, int], to_size: tuple[int, int]) -> dict:
    from_left, from_top, from_width, from_height = get_game_viewport(from_size)
    to_left, to_top, to_width, to_height = get_game_viewport(to_size)
    scaled_config = dict(config)

    if "first_x" in scaled_config:
        scaled_config["first_x"] = scale_axis_value(
            scaled_config["first_x"],
            from_left,
            from_width,
            to_left,
            to_width,
        )

    if "first_y" in scaled_config:
        scaled_config["first_y"] = scale_axis_value(
            scaled_config["first_y"],
            from_top,
            from_height,
            to_top,
            to_height,
        )

    if "x_step" in scaled_config:
        scaled_config["x_step"] = scale_value(scaled_config["x_step"], from_width, to_width)

    if "y_step" in scaled_config:
        scaled_config["y_step"] = scale_value(scaled_config["y_step"], from_height, to_height)

    if "inventory_count_roi" in scaled_config:
        scaled_config["inventory_count_roi"] = scale_roi(
            scaled_config["inventory_count_roi"],
            from_size,
            to_size,
        )

    return scaled_config


def maybe_scale_config_for_window(config: dict, window) -> dict:
    base_size = get_config_base_size(config)

    if base_size is None:
        logger.info("No base_window_size configured; using absolute coordinates.")
        return config

    window_size = get_window_size(window)

    if window_size == base_size:
        logger.info("Window size matches base_window_size=%sx%s.", *base_size)
        return config

    logger.info(
        "Scaling grid coordinates from base_window_size=%sx%s to current window=%sx%s.",
        base_size[0],
        base_size[1],
        window_size[0],
        window_size[1],
    )
    return scale_grid_config(config, base_size, window_size)
