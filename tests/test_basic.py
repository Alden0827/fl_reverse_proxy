def test_basic():
    assert True


def test_import():
    from app import app
    assert app is not None
