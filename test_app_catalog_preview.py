from unittest.mock import patch
from urllib.parse import urlparse

import requests
from streamlit.testing.v1 import AppTest


class JsonResponse:
    status_code = 200
    ok = True
    text = ""

    def __init__(self, payload):
        self.payload = payload

    def json(self):
        return self.payload

    def raise_for_status(self):
        return None


def fake_get(url, **kwargs):
    path = urlparse(url).path
    if path == "/entreprises":
        return JsonResponse({
            "AFRICA TECHNOLOGIE TEST": ["flyer-africa"],
            "CAMCI": ["flyer-camci"],
        })
    if path == "/fonts":
        return JsonResponse({})
    if path.endswith("/catalogue"):
        company = path.split("/")[-2]
        model = "flyer-camci" if company == "CAMCI" else "flyer-africa"
        return JsonResponse({
            "modeles": {model: {"objectif_publication": "Publication", "zones_modifiables": {}}},
            "objectifs": ["Publication"],
        })
    raise AssertionError(f"Unexpected GET: {path}")


def test_changing_company_uses_its_catalogue_and_requires_an_image_for_preview():
    request_ids = []

    def timeout_preview(url, **kwargs):
        assert url.endswith("/preview")
        request_id = kwargs["headers"]["X-Request-ID"]
        request_ids.append(request_id)
        raise requests.Timeout("simulated preview timeout")

    with (
        patch("requests.get", side_effect=fake_get),
        patch("requests.post", side_effect=timeout_preview),
    ):
        st = __import__("streamlit")
        st.cache_data.clear()
        app = AppTest.from_file("app.py", default_timeout=30).run()
        app.selectbox(key="flyer_ent").set_value("CAMCI").run()

    assert app.selectbox(key="flyer_ent").value == "CAMCI"
    assert app.selectbox(key="flyer_model").options == ["flyer-camci"]
    assert not request_ids
    assert any('Choisis une image' in info.value for info in app.info)
    assert not app.exception
