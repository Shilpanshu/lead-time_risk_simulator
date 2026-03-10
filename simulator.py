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
    length_cm,
    width_cm,
    height_cm,
    weight_kg,
    season_deadline_days,
    seasonality_factor=1.0,
    iterations=100000,
    annual_holding_cost_pct=0.20,
    salvage_markdown_pct=0.60,
    import_duty_pct=0.20
):
    """
    Refined Monte Carlo simulation for Supplier Risk and Freight Optimization.
    Takes raw lead time and volatility parameters for maximum flexibility.
    """
    # 1. Dynamic Freight Engine (Volumetric Weight)
    volumetric_weight = (length_cm * width_cm * height_cm) / 5000.0
    chargeable_air_weight_per_unit = max(weight_kg, volumetric_weight)
    cbm_per_unit = (length_cm * width_cm * height_cm) / 1000000.0
    
    freight_options = {
        "Ocean Freight (Default)": {"lt_reduction": 0.0, "added_cost": 150.0 * cbm_per_unit},
        "Express Ocean": {"lt_reduction": 0.2, "added_cost": 250.0 * cbm_per_unit},
        "Standard Air": {"lt_reduction": 0.6, "added_cost": 5.0 * chargeable_air_weight_per_unit},
        "Priority Air": {"lt_reduction": 0.8, "added_cost": 8.0 * chargeable_air_weight_per_unit}
    }

    results_matrix = []
    actual_velocity = sales_velocity * seasonality_factor

    for name, opt in freight_options.items():
        # Adjust lead time based on freight mode
        adjusted_avg_lt = avg_lead_time * (1 - opt["lt_reduction"])
        adjusted_std_lt = std_dev * (1 - opt["lt_reduction"]) 
        
        # Simulated Lead Times using Gamma Distribution
        shape = (adjusted_avg_lt / adjusted_std_lt)**2
        scale = (adjusted_std_lt**2) / adjusted_avg_lt
        sim_lts = np.random.gamma(shape, scale, iterations)

        # Simulated Daily Demand using Poisson Distribution
        simulated_daily_demand = np.random.poisson(actual_velocity, iterations)

        # Calculate stockout deadline based on the simulated burn rate
        deadline = np.zeros(iterations)
        zero_mask = simulated_daily_demand == 0
        deadline[zero_mask] = float('inf')
        deadline[~zero_mask] = current_inventory / simulated_daily_demand[~zero_mask]
        
        # Calculate Shortage
        shortage_days = np.maximum(sim_lts - deadline, 0)
        
        # Cap lost units to order quantity to prevent infinite shortage bug
        lost_units = np.minimum(shortage_days * simulated_daily_demand, order_qty)
        
        # The Top-Line Revenue Fallacy: Optimize for Gross Margin, not Revenue
        gross_margin = item_retail_price - base_unit_cost
        
        # The Founder's Fix: The Sell-Through Window (No Teleportation)
        # 1. We cannot start selling the new batch until it arrives AND old stock is burned.
        start_selling_day = np.maximum(sim_lts, deadline)
        
        # 2. The physical window of time we have left to sell before the season ends.
        sellable_days = np.maximum(season_deadline_days - start_selling_day, 0)
        
        # 3. How many units we can physically move at full price before the deadline.
        # The Founder's Fix: The Ghost Cycle Cap. We cannot sell more full-price units than the batch physical contains.
        full_price_units = np.minimum(sellable_days * simulated_daily_demand, order_qty)
        
        # 4. Any units from the order that we couldn't sell in that window get liquidated.
        units_marked_down = np.maximum(order_qty - full_price_units, 0)
        
        markdown_losses = units_marked_down * item_retail_price * salvage_markdown_pct
        avg_markdown_loss = np.mean(markdown_losses)

        # The Cash-Flow Phantom Debt Fix: Stop Double-Counting
        # You only charge margin_losses for units that didn't get marked down.
        # We cap lost units to the order_qty. 
        # Then, if a unit was marked down, it physical exists, so it wasn't a lost sale.
        chargeable_lost_units = np.maximum(lost_units - units_marked_down, 0)
        margin_losses = chargeable_lost_units * gross_margin
        expected_margin_loss = np.mean(margin_losses)
        
        # CIF Customs Duty escalation & Landed Cost Setup
        unit_duty_cost = (base_unit_cost + opt["added_cost"]) * import_duty_pct
        total_duty_cost = unit_duty_cost * order_qty
        unit_landed_cost = base_unit_cost + opt["added_cost"] + unit_duty_cost

        # 2. Total Holding Cost (In-Transit FOB Trap + Warehouse Bleed)
        # FOB Cash Trap: We pay upon loading, cash is dead while in transit.
        in_transit_holding_costs = (base_unit_cost * annual_holding_cost_pct / 365.0) * sim_lts * order_qty
        avg_in_transit_holding_cost = np.mean(in_transit_holding_costs)
        
        # Warehouse Landed Cost Fallacy: In warehouse, we hold the FULL landed cost.
        early_days = np.maximum(deadline - sim_lts, 0)
        early_days[zero_mask] = 0 # Avoid infinite early days when no demand
        warehouse_holding_costs = (unit_landed_cost * annual_holding_cost_pct / 365.0) * early_days * order_qty
        
        # The Founder's Fix: The Sell-Down Bleed (Cycle Stock Holding Cost)
        # We hold average inventory (full_price_units / 2) over the time it takes to sell it.
        sell_down_days = np.zeros(iterations)
        sell_down_days[~zero_mask] = full_price_units[~zero_mask] / simulated_daily_demand[~zero_mask]
        cycle_holding_costs = (unit_landed_cost * annual_holding_cost_pct / 365.0) * sell_down_days * (full_price_units / 2)
        
        avg_warehouse_holding_cost = np.mean(warehouse_holding_costs + cycle_holding_costs)
        
        avg_total_holding_cost = avg_in_transit_holding_cost + avg_warehouse_holding_cost
        
        # Stockout Risk %
        risk_pct = (np.sum(shortage_days > 0) / iterations) * 100
        
        # Financials
        total_freight_premium = opt["added_cost"] * order_qty
        total_paper_margin = gross_margin * order_qty
        
        risk_adjusted_total_margin = total_paper_margin - total_freight_premium - expected_margin_loss - avg_total_holding_cost - avg_markdown_loss - total_duty_cost
        
        # Net ROI Calculation
        # Savings from preventing stockouts - Freight Premium
        # (Standard Margin Loss - This Mode's Margin Loss) - Freight Premium
        # For simplicity, we compare to the "paper" baseline.
        net_roi = (total_paper_margin - risk_adjusted_total_margin) * -1
        
        # True Cost Per Unit
        # Base Cost + Expected Losses / Qty + Freight Premium + Duty
        true_cost = base_unit_cost + (expected_margin_loss / order_qty) + (avg_total_holding_cost / order_qty) + (avg_markdown_loss / order_qty) + opt["added_cost"] + unit_duty_cost
        
        results_matrix.append({
            "mode": name,
            "risk_pct": risk_pct,
            "expected_margin_loss": expected_margin_loss,
            "expected_holding_cost": avg_total_holding_cost,
            "expected_markdown_loss": avg_markdown_loss,
            "freight_cost": total_freight_premium,
            "duty_cost": total_duty_cost,
            "risk_adjusted_margin": risk_adjusted_total_margin,
            "true_cost": true_cost,
            "paper_margin": total_paper_margin,
            "net_roi": net_roi,
            "sim_lts": sim_lts,
            "deadline": deadline,
            "opportunity_cost_lost_peak": np.mean(shortage_days * actual_velocity * (seasonality_factor - 1)) * item_retail_price if seasonality_factor > 1 else 0
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
