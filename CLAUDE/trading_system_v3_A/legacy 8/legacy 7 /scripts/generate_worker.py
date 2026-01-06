import argparse
import sys
import os

# Add cleaned path to find modules
sys.path.insert(0, os.getcwd())

from worker_gen.core.data_manager import DataManager
from worker_gen.core.optimizer import Optimizer
from worker_gen.core.code_writer import CodeWriter

def main():
    parser = argparse.ArgumentParser(description='Worker Generator AI: Evolution of Trading Strategies')
    parser.add_argument('--name', required=True, help='Name of the worker (e.g., BullFlagWorker)')
    parser.add_argument('--input', required=True, help='Directory containing training CSV files')
    parser.add_argument('--iterations', type=int, default=1000, help='Number of strategies to test')
    parser.add_argument('--output_dir', default='strategies/workers', help='Where to save the generated file')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print(f"🤖 WORKER GENERATOR AI starting...")
    print(f"   Target Worker: {args.name}")
    print(f"   Input Data:    {args.input}")
    print(f"   Iterations:    {args.iterations}")
    print("=" * 60)
    
    # 1. Data Loading
    if not os.path.exists(args.input):
        print(f"❌ Input directory not found: {args.input}")
        return
        
    dm = DataManager(args.input)
    dm.load_all()
    
    if not dm.get_data():
        print("❌ No valid data loaded. Exiting.")
        return

    # 2. Optimization
    opt = Optimizer(dm)
    best_genome, stats = opt.optimize(iterations=args.iterations)
    
    if not best_genome:
        print("\n❌ Optimization failed to find a valid strategy.")
        return
        
    # 3. Code Generation
    print("\n📝 Generating Python Code...")
    writer = CodeWriter()
    
    # Format class name (Snake case to Camel Case)
    class_name = args.name.replace('_', ' ').title().replace(' ', '') + "Logic"
    
    # Generate content
    code = writer.generate(best_genome, class_name)
    
    # Save file
    filename = f"{args.name.lower()}_worker_logic.py"
    output_path = os.path.join(args.output_dir, filename)
    
    # Create directory if needed
    os.makedirs(args.output_dir, exist_ok=True)
    
    writer.save(code, output_path)
    
    print("\n" + "=" * 60)
    print(f"✅ SUCCESS! Worker generated at:")
    print(f"   {output_path}")
    print(f"   Class Name: {class_name}")
    print(f"   Score: {best_genome.fitness:.2f}")
    print("=" * 60)

if __name__ == "__main__":
    main()
