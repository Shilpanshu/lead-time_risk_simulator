import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from simulator import run_simulation_v2
import time

# Page Configuration
st.set_page_config(
    page_title="Supply Chain Risk Intelligence",
    page_icon="🛳️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Standard Supplier Parameters (Source of Truth)
TIER_PARAMS = {
    "Supplier A (Domestic High-Speed)": {"avg_lt": 7, "std_lt": 1, "tier": "A"},
    "Supplier B (Near-shore Mid-Speed)": {"avg_lt": 21, "std_lt": 4, "tier": "B"},
    "Supplier C (Offshore Low-Speed)": {"avg_lt": 60, "std_lt": 12, "tier": "C"},
    "A": {"avg_lt": 7, "std_lt": 1},
    "B": {"avg_lt": 21, "std_lt": 4},
    "C": {"avg_lt": 60, "std_lt": 12}
}

# Custom Styling
st.markdown("""
<style>
    .main { background-color: #0e1117; color: #ffffff; }
    .stMetric { background-color: #1e2130 !important; padding: 20px !important; border-radius: 10px !important; border: 1px solid #3d4455 !important; }
    .banner-recommendation { background: linear-gradient(90deg, #1e2130 0%, #2c3e50 100%); padding: 20px; border-radius: 12px; border-left: 8px solid #2ecc71; margin-bottom: 30px; font-size: 1.2rem; font-weight: 500; }
    .banner-recommendation.critical { border-left-color: #e74c3c; }
    .banner-recommendation.warning { border-left-color: #f1c40f; }
</style>
""", unsafe_allow_html=True)

# Tabs
tab_dive, tab_triage = st.tabs(["🔍 Single SKU Deep Dive", "📊 Portfolio Triage"])

# --- TAB 1: SINGLE SKU DEEP DIVE ---
with tab_dive:
    st.sidebar.title("🎛️ SKU Simulation Controls")
    
    supplier_key = st.sidebar.selectbox("Choose Supplier Profile", 
        ["Supplier A (Domestic High-Speed)", "Supplier B (Near-shore Mid-Speed)", "Supplier C (Offshore Low-Speed)"], index=2)
    
    # Get parameters from source of truth
    params = TIER_PARAMS[supplier_key]
    
    order_qty = st.sidebar.number_input("Order Quantity (Units)", min_value=1, value=1000, key="sku_qty")
    base_unit_cost = st.sidebar.number_input("Base Unit Cost ($)", min_value=0.1, value=15.0, key="sku_cost")
    item_retail_price = st.sidebar.number_input("Retail Price per Unit ($)", min_value=1.0, value=100.0, key="sku_price")
    sales_velocity = st.sidebar.number_input("Daily Sales Velocity (Units/Day)", min_value=1.0, value=15.0, key="sku_velocity")
    current_inventory = st.sidebar.number_input("Current Inventory Level (Units)", min_value=1, value=150, key="sku_inv")
    seasonality = st.sidebar.select_slider("Seasonality Factor", options=[1.0, 1.5, 2.0, 2.5, 3.0], value=1.5, key="sku_season")
    iterations = st.sidebar.selectbox("Sim Iterations", [10000, 50000, 100000], index=2, key="sku_iter")
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### SKU Physics & Timelines")
    length_cm = st.sidebar.number_input("Length (cm)", min_value=1.0, value=40.0, key="sku_len")
    width_cm = st.sidebar.number_input("Width (cm)", min_value=1.0, value=30.0, key="sku_wid")
    height_cm = st.sidebar.number_input("Height (cm)", min_value=1.0, value=20.0, key="sku_hgt")
    weight_kg = st.sidebar.number_input("Weight (kg)", min_value=0.1, value=5.0, key="sku_wgt")
    season_deadline_days = st.sidebar.number_input("Season Deadline (Days)", min_value=1, value=45, key="sku_dl")
    import_duty_pct = st.sidebar.number_input("Import Duty %", min_value=0.0, max_value=1.0, value=0.20, key="sku_duty")

    # Run Simulation (Using unified signature)
    res = run_simulation_v2(
        avg_lead_time=params["avg_lt"],
        std_dev=params["std_lt"],
        sales_velocity=sales_velocity,
        current_inventory=current_inventory,
        item_retail_price=item_retail_price,
        base_unit_cost=base_unit_cost,
        order_qty=order_qty,
        length_cm=length_cm,
        width_cm=width_cm,
        height_cm=height_cm,
        weight_kg=weight_kg,
        season_deadline_days=season_deadline_days,
        seasonality_factor=seasonality,
        iterations=iterations,
        import_duty_pct=import_duty_pct
    )
    opt = res["optimal"]

    st.title("📦 SKU Risk Analysis")
    
    # Executive Banner
    banner_class = "banner-recommendation " + ("critical" if opt["risk_pct"] > 50 else "warning" if opt["risk_pct"] > 20 else "")
    st.markdown(f'<div class="{banner_class}">**Executive Recommendation:** Authorize **{opt["mode"]}**. Preserves **${opt["risk_adjusted_margin"]:,.0f}** in actual margin.</div>', unsafe_allow_html=True)

    # Metrics
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Stockout Risk", f"{opt['risk_pct']:.1f}%")
    c2.metric("True Cost / Unit", f"${opt['true_cost']:,.2f}")
    c3.metric("Expected Margin Loss", f"${opt['expected_margin_loss']:,.0f}")
    c4.metric("Risk-Adjusted Margin", f"${opt['risk_adjusted_margin']:,.0f}")

    # Charts
    st.markdown("---")
    ga, gb = st.columns(2)
    with ga:
        df_m = pd.DataFrame({"Label": ["Paper Margin", "Risk-Adjusted"], "Value": [opt["paper_margin"], opt["risk_adjusted_margin"]]})
        st.plotly_chart(px.bar(df_m, x="Label", y="Value", color="Label", 
                               color_discrete_map={"Paper Margin": "#4b5563", "Risk-Adjusted": "#2ecc71" if opt["risk_adjusted_margin"] > 0 else "#e74c3c"})
                        .update_layout(template="plotly_dark", showlegend=False, paper_bgcolor="rgba(0,0,0,0)"), use_container_width=True)
    with gb:
        df_r = pd.DataFrame({"Mode": [m["mode"] for m in res["full_matrix"]], "Savings": [m["net_roi"] for m in res["full_matrix"]]})
        df_r["Color"] = ["#1f77b4" if m != opt["mode"] else "#2ecc71" for m in df_r["Mode"]]
        st.plotly_chart(px.bar(df_r, y="Mode", x="Savings", orientation='h', color="Color", color_discrete_map="identity")
                        .update_layout(template="plotly_dark", showlegend=False, paper_bgcolor="rgba(0,0,0,0)"), use_container_width=True)

# --- TAB 2: PORTFOLIO TRIAGE ---
with tab_triage:
    st.title("📊 Portfolio Risk Triage")
    st.markdown("### ERP Data Analysis Pipeline")
    
    uploaded_file = st.file_uploader("Upload ERP Data Dump (CSV)", type="csv")
    
    if uploaded_file is not None:
        try:
            df_erp = pd.read_csv(uploaded_file)
            
            # Verify required columns exist
            required_columns = ['SKU_ID', 'Supplier_Tier', 'Current_Stock', 'Daily_Velocity', 'Unit_Cost', 'Retail_Price', 'Order_Qty', 'Length_cm', 'Width_cm', 'Height_cm', 'Weight_kg', 'Season_Deadline_Days']
            if not all(col in df_erp.columns for col in required_columns):
                st.error(f"CSV Schema Error. Required columns: {', '.join(required_columns)}")
            else:
                with st.spinner("Processing Portfolio Simulation..."):
                    results = []
                    for _, row in df_erp.iterrows():
                        tier = row["Supplier_Tier"]
                        # Lookup params based on Tier (A, B, C)
                        p = TIER_PARAMS.get(tier, TIER_PARAMS["C"]) # Default to C if unknown
                        
                        sim = run_simulation_v2(
                            avg_lead_time=p["avg_lt"],
                            std_dev=p["std_lt"],
                            sales_velocity=row["Daily_Velocity"],
                            current_inventory=row["Current_Stock"],
                            item_retail_price=row["Retail_Price"],
                            base_unit_cost=row["Unit_Cost"],
                            order_qty=row["Order_Qty"],
                            length_cm=row["Length_cm"],
                            width_cm=row["Width_cm"],
                            height_cm=row["Height_cm"],
                            weight_kg=row["Weight_kg"],
                            season_deadline_days=row["Season_Deadline_Days"],
                            seasonality_factor=1.5,
                            iterations=100000
                        )
                        best = sim["optimal"]
                        results.append({
                            "SKU_ID": row["SKU_ID"],
                            "Stockout_Risk_%": best["risk_pct"],
                            "Expected_Loss": best["expected_margin_loss"],
                            "Freight_Cost": best["freight_cost"],
                            "Duty_Cost": best["duty_cost"],
                            "Expected_Holding_Cost": best["expected_holding_cost"],
                            "Expected_Markdown_Loss": best["expected_markdown_loss"],
                            "Net_Margin_ROI": best["net_roi"],
                            "Optimal_Freight": best["mode"],
                            "Unit_Cost": row["Unit_Cost"]
                        })
                
                df_results = pd.DataFrame(results)
                
                # Summary Metrics
                total_at_risk = df_results["Expected_Loss"].sum()
                high_risk_count = len(df_results[df_results["Stockout_Risk_%"] > 40])
                
                col_t1, col_t2 = st.columns(2)
                col_t1.metric("Portfolio Total Margin at Risk", f"${total_at_risk:,.0f}", delta=f"{high_risk_count} High-Risk SKUs", delta_color="inverse")
                
                st.markdown("---")
                st.subheader("🚨 Critical Action Board")
                st.markdown("SKUs requiring immediate attention (Risk > 40% OR Expected Loss > $5,000)")
                
                # Filter and Sort
                df_action = df_results[
                    (df_results["Stockout_Risk_%"] > 40) | 
                    (df_results["Expected_Loss"] > 5000)
                ].sort_values(by="Expected_Loss", ascending=False).copy()
                
                # PROFESSIONAL FORMATTING for Executive Presentation
                df_action['Stockout_Risk_%'] = df_action['Stockout_Risk_%'].apply(lambda x: f"{x:.1f}%")
                df_action['Expected_Loss'] = df_action['Expected_Loss'].apply(lambda x: f"${x:,.0f}")
                df_action['Freight_Cost'] = df_action['Freight_Cost'].apply(lambda x: f"${x:,.0f}")
                df_action['Duty_Cost'] = df_action['Duty_Cost'].apply(lambda x: f"${x:,.0f}")
                df_action['Expected_Holding_Cost'] = df_action['Expected_Holding_Cost'].apply(lambda x: f"${x:,.0f}")
                df_action['Expected_Markdown_Loss'] = df_action['Expected_Markdown_Loss'].apply(lambda x: f"${x:,.0f}")
                df_action['Net_Margin_ROI'] = df_action['Net_Margin_ROI'].apply(lambda x: f"${x:,.0f}")
                df_action['Unit_Cost'] = df_action['Unit_Cost'].apply(lambda x: f"${x:,.2f}")
                
                st.dataframe(df_action, use_container_width=True)
                
                # Actionable Insight
                if not df_action.empty:
                    top_sku = df_action.iloc[0]["SKU_ID"]
                    st.info(f"💡 **Triage Insight:** {top_sku} is your highest priority issue. Authorizing air freight immediately will protect your peak margin.")
        except Exception as e:
            st.error(f"Error processing file: {e}")

    else:
        st.info("Please upload an ERP CSV to begin triage.")
        st.markdown("""
        **Expected CSV Format:**
        ```csv
        SKU_ID,Supplier_Tier,Current_Stock,Daily_Velocity,Unit_Cost,Retail_Price,Order_Qty,Length_cm,Width_cm,Height_cm,Weight_kg,Season_Deadline_Days
        SKU-001,C,150,15,15,100,1000,40,30,20,5,45
        SKU-002,A,50,20,45,150,500,50,40,30,12,60
        ```
        """)
