# No início do ficheiro
try:
    from mock import files as mock_files
    print("Usando dados mock")
except ImportError:
    mock_files = []