import subprocess
import os

def run_all_portfolios():
    scripts = [
        'portfolios/mean_variance.py',
        'portfolios/hrp_portfolio.py',
        'portfolios/min_variance.py',
        'portfolios/sentiment_portfolio.py'
    ]
    
    python_bin = 'python'
    
    for script in scripts:
        print(f"\n{'='*40}")
        print(f"Running {script}...")
        print(f"{'='*40}")
        result = subprocess.run([python_bin, script], capture_output=True, text=True)
        print(result.stdout)
        if result.stderr:
            print("Errors:")
            print(result.stderr)

if __name__ == "__main__":
    run_all_portfolios()
