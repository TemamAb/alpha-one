# Analyze results
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

def analyze_results(results, output_dir="./results"):
    """
    Production-grade backtest analyzer.
    Generates stats, charts, PnL report.
    results: list of sim_result dicts from simulate_trades
    """
    if not results:
        logger.warning("No results to analyze")
        return {}
    
    df = pd.DataFrame(results)
    
    # Key metrics
    stats = {
        'total_trades': len(df),
        'win_rate': (df['success'].sum() / len(df)) * 100 if len(df) > 0 else 0,
        'avg_pnl': df['net_pnl'].mean(),
        'total_pnl': df['net_pnl'].sum(),
        'max_pnl': df['net_pnl'].max(),
        'max_loss': df['net_pnl'].min(),
        'sharpe_ratio': df['net_pnl'].mean() / df['net_pnl'].std() if df['net_pnl'].std() > 0 else 0,
        'avg_gas': df['gas_used'].mean(),
        'risk_frequency': df['risks'].apply(lambda x: len(x) if isinstance(x, list) else 0).mean()
    }
    
    logger.info(f"Analysis complete: Win {stats['win_rate']:.1f}%, Total PnL {stats['total_pnl']:.2f}")
    
    # Save JSON report
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = f"{output_dir}/analysis_{timestamp}.json"
    with open(report_path, 'w') as f:
        json.dump(stats, f, indent=2)
    
    # Charts
    plt.figure(figsize=(12, 8))
    
    plt.subplot(2,2,1)
    df['net_pnl'].hist(bins=20)
    plt.title('PnL Distribution')
    
    plt.subplot(2,2,2)
    df['success'].value_counts().plot(kind='bar')
    plt.title('Win/Loss')
    
    plt.subplot(2,2,3)
    plt.plot(np.cumsum(df['net_pnl']))
    plt.title('Cumulative PnL')
    
    plt.subplot(2,2,4)
    df.boxplot(column='net_pnl', by='risks')
    plt.title('PnL by Risk')
    
    plt.tight_layout()
    plt.savefig(f"{output_dir}/backtest_charts_{timestamp}.png")
    plt.close()
    
    # Risk breakdown
    risk_counts = pd.Series([r for risks in df['risks'] for r in risks if isinstance(risks, list)]).value_counts()
    stats['risk_breakdown'] = risk_counts.to_dict()
    
    return stats

def analyze_results(chain, results):
    """
    Legacy entrypoint.
    """
    return analyze_results(results)
