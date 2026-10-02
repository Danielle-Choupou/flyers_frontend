import pytest

from editeur_visuel import _next_zone_number, _normalize_zone_labels


@pytest.mark.parametrize(
    "objects, expected",
    [
        ([{"label": "Zone 1"}, {"label": "Zone 2"}], 3),
        ([{"label": "Zone 1"}, {"label": "Zone 3"}], 3),
        ([{"label": "Zone 1"}, {"label": "Zone 1"}, {"label": "Zone 2"}], 4),
        ([{"label": "Titre"}, {"label": "Prix"}], 3),
        ([], 1),
    ],
)
def test_next_zone_number_uses_existing_labels(objects, expected):
    assert _next_zone_number(objects) == expected


def test_normalize_zone_labels_are_sequential():
    objects = [{"label": "Zone 7"}, {"label": "Zone 1"}, {"label": "Titre"}]
    normalized = _normalize_zone_labels(objects)
    assert [obj["label"] for obj in normalized] == ["Zone 1", "Zone 2", "Zone 3"]


def test_normalize_zone_labels_can_preserve_saved_names():
    objects = [{"label": "Titre"}, {"label": "Prix"}, {"label": "  "}]
    normalized = _normalize_zone_labels(objects, preserve_labels=True)
    assert [obj["label"] for obj in normalized] == ["Titre", "Prix", "Zone 3"]
