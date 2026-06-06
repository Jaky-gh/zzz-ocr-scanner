from src.coordinate_scaling import (
    get_game_viewport,
    scale_grid_config,
    scale_roi,
    scale_rois,
)


def assert_equal(actual, expected):
    if actual != expected:
        raise AssertionError(f"Expected {expected!r}, got {actual!r}")


def main():
    assert_equal(get_game_viewport((1296, 759)), (8, 31, 1280, 720))
    assert_equal(get_game_viewport((1616, 939)), (8, 31, 1600, 900))
    assert_equal(get_game_viewport((1920, 1080)), (0, 0, 1920, 1080))

    assert_equal(
        scale_roi(
            {"x": 100, "y": 50, "w": 20, "h": 10},
            from_size=(1000, 562),
            to_size=(2000, 1125),
        ),
        {"x": 200, "y": 100, "w": 40, "h": 20},
    )

    assert_equal(
        scale_rois(
            {"disc_name": {"x": 100, "y": 50, "w": 20, "h": 10}},
            from_size=(1000, 562),
            to_size=(500, 281),
        ),
        {"disc_name": {"x": 50, "y": 25, "w": 10, "h": 5}},
    )

    assert_equal(
        scale_grid_config(
            {
                "first_x": 100,
                "first_y": 50,
                "x_step": 20,
                "y_step": 10,
                "inventory_count_roi": {"x": 10, "y": 20, "w": 30, "h": 40},
                "click_delay": 0.35,
            },
            from_size=(1000, 562),
            to_size=(2000, 1125),
        ),
        {
            "first_x": 200,
            "first_y": 100,
            "x_step": 40,
            "y_step": 20,
            "inventory_count_roi": {"x": 20, "y": 40, "w": 60, "h": 80},
            "click_delay": 0.35,
        },
    )

    print("coordinate scaling checks passed")


if __name__ == "__main__":
    main()
