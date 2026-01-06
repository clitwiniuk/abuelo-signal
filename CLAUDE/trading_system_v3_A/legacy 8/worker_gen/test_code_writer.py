from core.code_writer import CodeWriter
from core.strategy_dna import StrategyGenome, Condition

# 1. Create Mock Strategy
cond1 = Condition('rsi_14', '<', 30)
cond2 = Condition('close', '>', 'vwap')
genome = StrategyGenome([cond1, cond2], stop_loss_pct=2.5, take_profit_pct=5.0, time_limit_bars=60)
genome.fitness = 123.45

# 2. Generate
print("Generating code...")
writer = CodeWriter()
code = writer.generate(genome, "TestWorkerLogic")

print("\n--- GENERATED CODE PREVIEW ---")
print(code[:500] + "...")
print("..." + code[-500:])

# 3. Save
writer.save(code, "worker_gen/output/test_worker.py")
