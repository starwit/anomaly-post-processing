import pytest

def test_anomalypostprocessing_import():
    try:
        from anomalypostprocessing.anomalypostprocessing import AnomalyPostProcessing
    except ImportError as e:
        pytest.fail(f"AnomalyPostProcessing import failed: {e}")
    
    assert AnomalyPostProcessing is not None, "AnomalyPostProcessing import failed"
    
    print("AnomalyPostProcessing import is successful.")
    
def test_import_main():
    try:
        import main
    except ImportError as e:
        pytest.fail(f"Main module import failed: {e}")
    
    assert main is not None, "Main module import failed"
    
    print("Main module import is successful.")