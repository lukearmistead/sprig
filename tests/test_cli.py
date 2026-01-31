"""Tests for sprig CLI functionality."""


def test_cli_module_imports():
    """Test that CLI module imports successfully."""
    from sprig.cli import main
    assert callable(main)


def test_web_module_imports():
    """Test that web module imports and has required components."""
    from sprig.web import start_dashboard, create_app, PORT
    assert callable(start_dashboard)
    assert callable(create_app)
    assert PORT == 8001


def test_flask_app_creates():
    """Test that Flask app can be created."""
    from sprig.web import create_app
    app = create_app()
    assert app is not None
    assert hasattr(app, 'run')
