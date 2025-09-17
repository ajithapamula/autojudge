import os

def test_env_template_exists():
    # Ensure contributors know required env vars
    assert os.path.exists(".env.example")

def test_basic_import():
    # Change to your main package/module
    try:
        import app  # or src.package
    except Exception as e:
        raise AssertionError(f"Import failed: {e}")
