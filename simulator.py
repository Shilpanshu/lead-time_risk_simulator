import numpy as np
import pandas as pd

def run_simulation_v2(
    avg_lead_time,
    std_dev,
    sales_velocity,
    current_inventory,
    item_retail_price,
    base_unit_cost,
    order_qty,
    seasonality_factor=1.0,
    iterations=1000
):
    """
    Refined Monte Carlo simulation for Supplier Risk and Freight Optimization.
    Takes raw lead time and volatility parameters for maximum flexibility.
    """
    # 1. Freight Matrix (Internal to the engine as requested)
    freight_options = {
        "Ocean Freight (Default)": {"lt_reduction": 0.0, "added_cost": 0.0},
        "Express Ocean": {"lt_reduction": 0.2, "added_cost": 1.5},
        "Standard Air": {"lt_reduction": 0.6, "added_cost": 4.0},
        "Priority Air": {"lt_reduction": 0.8, "added_cost": 8.0}
    }

    results_matrix = []
    actual_velocity = sales_velocity * seasonality_factor

    for name, opt in freight_options.items():
        # Adjust lead time based on freight mode
        adjusted_avg_lt = avg_lead_time * (1 - opt["lt_reduction"])
        adjusted_std_lt = std_dev * (1 - opt["lt_reduction"]) 
        
        # Simulated Lead Times
        sim_lts = np.random.normal(adjusted_avg_lt, adjusted_std_lt, iterations)
        sim_lts = np.maximum(sim_lts, 0.5) 

        # Calculate stockout deadline based on the accelerated burn rate
        deadline = current_inventory / actual_velocity if actual_velocity > 0 else float('inf')
        
        # Calculate Shortage and Revenue Loss
        shortage_days = np.maximum(sim_lts - deadline, 0)
        lost_units = shortage_days * actual_velocity
        
        # Revenue Loss
        revenue_losses = lost_units * item_retail_price
        avg_revenue_loss = np.mean(revenue_losses)
        
        # Stockout Risk %
        risk_pct = (np.sum(shortage_days > 0) / iterations) * 100
        
        # Financials
        total_freight_premium = opt["added_cost"] * order_qty
        total_paper_margin = (item_retail_price - base_unit_cost) * order_qty
        
        risk_adjusted_total_margin = total_paper_margin - total_freight_premium - avg_revenue_loss
        
        # Net ROI Calculation
        # Savings from preventing stockouts - Freight Premium
        # (Standard Revenue Loss - This Mode's Revenue Loss) - Freight Premium
        # For simplicity, we compare to the "paper" baseline.
        net_roi = (total_paper_margin - risk_adjusted_total_margin) * -1
        
        # True Cost Per Unit
        # Base Cost + (Exp Loss / Qty) + Freight Premium
        true_cost = base_unit_cost + (avg_revenue_loss / order_qty) + opt["added_cost"]
        
        results_matrix.append({
            "mode": name,
            "risk_pct": risk_pct,
            "avg_revenue_loss": avg_revenue_loss,
            "risk_adjusted_margin": risk_adjusted_total_margin,
            "true_cost": true_cost,
            "paper_margin": total_paper_margin,
            "net_roi": net_roi,
            "sim_lts": sim_lts,
            "deadline": deadline,
            "opportunity_cost_lost_peak": np.mean(shortage_days * sales_velocity * (seasonality_factor - 1)) * item_retail_price if seasonality_factor > 1 else 0
        })

    optimal_idx = np.argmax([r["risk_adjusted_margin"] for r in results_matrix])
    optimal_mode = results_matrix[optimal_idx]

    return {
        "full_matrix": results_matrix,
        "optimal": optimal_mode,
        "base_cost": base_unit_cost,
        "retail_price": item_retail_price,
        "qty": order_qty
    }
