import sys
import os

# Add src to PYTHONPATH for source checkout
src_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'src'))
sys.path.insert(0, src_path)

# Import and run the main module
from lumi_maze.main import main

if __name__ == '__main__':
    sys.exit(main())