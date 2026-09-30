from pathlib import Path


def test_no_use_container_width_deprecation_in_frontend_app():
    source = Path(__file__).with_name('app.py').read_text(encoding='utf-8')
    assert 'use_container_width' not in source


def test_save_model_request_has_adequate_timeout():
    source = Path(__file__).with_name('app.py').read_text(encoding='utf-8')
    assert "timeout=30" not in source or "timeout=(10, 180)" in source
