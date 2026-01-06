
import sys
import os
sys.path.append(os.getcwd())

from strategies.workers.parabolic_worker_logic import ParabolicWorkerLogic

class MockObj:
    pass

try:
    mock_engine = MockObj()
    mock_engine.broker = MockObj()
    mock_engine.broker.ib = MockObj()
    mock_risk = MockObj()
    
    worker = ParabolicWorkerLogic("parabolic", mock_engine, mock_risk, config={})
    print("SUCCESS: Instantiated ParabolicWorkerLogic")
except Exception as e:
    print(f"FAILED: {e}")
    import traceback
    traceback.print_exc()
