import importlib
import os
import sys

sys.path.insert(0, os.path.abspath('.'))

def test_pipeline_import():
    assert importlib.import_module('pipeline.pipeline')
