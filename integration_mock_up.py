import pandas as pd
from datetime import datetime, timedelta
from prophet import Prophet
import process_data
import matplotlib.pyplot as plt
import numpy as np
from scipy.interpolate import make_interp_spline
import matplotlib.dates as mdates
import warnings
warnings.filterwarnings("ignore")

# Global parameters: dynamic price index range and forecast period
BASE_PRICE = 4.79 #Fixed price reference from charger operator
PRICE_ELASTICITY = 0.1  # Factor that changes volume based on price change
PRICE_INDEX_MIN = 0.6   # Minimum dynamic price index
PRICE_INDEX_MAX = 1.4   # Maximum dynamic price index
FORECAST_START_DATE = datetime(2024, 5, 31)   # Start date for forecast simulation
SIMULATION_END_DATE = datetime(2024, 9, 30)    # End date for simulation

# Load full hourly data from file and ensure 'Start time' is datetime
def load_full_data():
    print("Loading full data from file...")
    data = process_data.get_data().reset_index()
    data['Start time'] = pd.to_datetime(data['Start time'])
    print("Full data loaded. Total records:", len(data))
    return data

# Scale y between scalemin and scalemax based on [ymin, ymax] (returns midpoint if no variation)
def linear_scale_value(y, ymin, ymax, scalemin=PRICE_INDEX_MIN, scalemax=PRICE_INDEX_MAX):
    if ymax == ymin:
        return (scalemin + scalemax) / 2
    return (y - ymin) / (ymax - ymin) * (scalemax - scalemin) + scalemin

# Compute hourly price index using a 24h rolling window on forecasted 'yhat'
def compute_hourly_price_index(fcst_day, scalemin=PRICE_INDEX_MIN, scalemax=PRICE_INDEX_MAX):
    df = fcst_day[['ds', 'yhat']].copy().set_index('ds')
    rolling = df.rolling('24h', center=True)
    df['ymin'] = rolling['yhat'].min()  # Rolling min of yhat
    df['ymax'] = rolling['yhat'].max()  # Rolling max of yhat
    df = df.reset_index()
    df['price_index'] = df.apply(lambda r: linear_scale_value(r['yhat'], r['ymin'], r['ymax'], scalemin, scalemax), axis=1)
    return df[['ds', 'price_index']]

# Forecast next 24h using training_data and return hourly forecast and daily aggregates
def forecast_one_day(training_data, forecast_date, scalemin=PRICE_INDEX_MIN, scalemax=PRICE_INDEX_MAX):
    print(f"\nForecasting for day starting at {forecast_date} ...")
    train_df = training_data.rename(columns={'Start time': 'ds', 'Energy_Wh': 'y'})
    print("Training Prophet model on data up to", train_df['ds'].max())
    model = Prophet(changepoint_prior_scale=0.05, seasonality_mode='multiplicative')
    model.fit(train_df)
    future = model.make_future_dataframe(periods=24, freq='h')
    fcst = model.predict(future)
    fcst_day = fcst[(fcst['ds'] >= forecast_date) & (fcst['ds'] < forecast_date + timedelta(days=1))].copy()
    print(f"Forecast generated for {len(fcst_day)} hours.")
    price_index_df = compute_hourly_price_index(fcst_day, scalemin, scalemax)
    fcst_day = fcst_day.merge(price_index_df, on='ds')
    fcst_day['predicted_revenue'] = fcst_day['yhat'] * BASE_PRICE * fcst_day['price_index']
    forecasted_energy = fcst_day['yhat'].sum()
    predicted_revenue = fcst_day['predicted_revenue'].sum()
    daily_forecast = {'forecasted_energy': forecasted_energy, 'predicted_revenue': predicted_revenue}
    print(f"Aggregated daily forecast: Energy={forecasted_energy:.2f}, Revenue={predicted_revenue:.2f}")
    return fcst_day, daily_forecast

# Simulate day-ahead forecasting: for each day, forecast next 24h, compare with actual, and compute dynamic revenue
def simulate_forecast(forecast_start_date, simulation_end_date, scalemin=PRICE_INDEX_MIN, scalemax=PRICE_INDEX_MAX, price_elasticity=PRICE_ELASTICITY):
    print("\nStarting simulation of day-ahead forecasts...")
    full_data = load_full_data()
    current_date = forecast_start_date + timedelta(days=1)
    results = []
    max_test_date = full_data['Start time'].dt.date.max()
    
    while current_date.date() <= max_test_date and current_date <= simulation_end_date:
        print("\n========================================")
        print("Processing forecast for day:", current_date.date())
        training_data = full_data[full_data['Start time'] < current_date].copy()
        print(f"Training data now includes records up to {training_data['Start time'].max()}")
        fcst_day, daily_forecast = forecast_one_day(training_data, current_date, scalemin, scalemax)
        
        # Get actual hourly data for the forecasted day
        actual_next_day = full_data[(full_data['Start time'] >= current_date) & (full_data['Start time'] < current_date + timedelta(days=1))].copy()
        actual_energy = actual_next_day['Energy_Wh'].sum() if not actual_next_day.empty else None
        actual_revenue = actual_energy * BASE_PRICE
        
        # Merge actual hourly data with forecasted price indices to compute dynamic revenue per hour
        actual_next_day = actual_next_day.rename(columns={'Start time': 'ds', 'Energy_Wh': 'actual_energy'})
        merged_actual = fcst_day[['ds', 'price_index']].merge(actual_next_day[['ds', 'actual_energy']], on='ds', how='inner')
        merged_actual['volume_delta'] = (merged_actual['price_index'] - 1) * merged_actual['actual_energy'] * price_elasticity
        merged_actual['revenue_with_dynamic_price'] = (merged_actual['actual_energy'] - merged_actual['volume_delta']) * BASE_PRICE * merged_actual['price_index']
        revenue_with_dynamic_price = merged_actual['revenue_with_dynamic_price'].sum()
        #plot hourly
        #plot_merged_revenue(merged_actual)
    
        # Compute percentage difference using revenue with dynamic price vs actual revenue
        pct_diff = round((revenue_with_dynamic_price - actual_revenue) / actual_revenue, 2) if actual_revenue and actual_revenue != 0 else None
        
        print(f"Day {current_date.date()}: Forecasted Energy = {daily_forecast['forecasted_energy']:.2f}, Predicted Revenue = {daily_forecast['predicted_revenue']:.2f}")
        print(f"Day {current_date.date()}: Actual Energy = {actual_energy}, Actual Revenue = {actual_revenue}")
        print(f"Day {current_date.date()}: Revenue with dynamic price = {revenue_with_dynamic_price:.2f}")
        print(f"Percentage Difference (Revenue): {pct_diff}")
        
        results.append({
            'date': current_date.date(),
            'forecasted_energy': daily_forecast['forecasted_energy'],
            'predicted_revenue': daily_forecast['predicted_revenue'],
            'actual_energy': actual_energy,
            'actual_revenue': actual_revenue,
            'revenue_with_dynamic_price': revenue_with_dynamic_price,
            'pct_diff': pct_diff
        })
        current_date += timedelta(days=1)
    
    results_df = pd.DataFrame(results)
    print("\nSimulation completed.")
    return results_df

def plot_monthly_revenue_scenarios_stacked(low_df, med_df, high_df):
    """
    Creates a stacked bar chart for monthly revenue scenarios.
    
    Each input DataFrame (from simulate_forecast) must include:
      - 'date': the day (as a datetime),
      - 'actual_revenue': computed as actual_energy * BASE_PRICE,
      - 'revenue_with_dynamic_price': dynamic revenue for that scenario.
      
    For each month, the stacked bar will consist of:
      • Bottom segment: Actual Revenue (color: "#d0cece")
      • Next segment: [Low dynamic – Actual Revenue] (color: "#b0ccf7")
      • Next segment: [Medium dynamic – Low dynamic] (color: "#3c649f")
      • Top segment: [High dynamic – Medium dynamic] (color: "#1a2d48")
    """
    # Ensure the date column is datetime and create a 'month' column (format: YYYY-MM)
    for df in [low_df, med_df, high_df]:
        df['date'] = pd.to_datetime(df['date'])
        df['month'] = df['date'].dt.strftime('%Y-%m')
    
    # Aggregate monthly values (sum daily values)
    low_monthly = low_df.groupby('month').agg({
        'actual_revenue': 'sum',
        'revenue_with_dynamic_price': 'sum'
    }).reset_index().rename(columns={'revenue_with_dynamic_price': 'low_dynamic'})
    
    med_monthly = med_df.groupby('month').agg({
        'actual_revenue': 'sum',
        'revenue_with_dynamic_price': 'sum'
    }).reset_index().rename(columns={'revenue_with_dynamic_price': 'med_dynamic'})
    
    high_monthly = high_df.groupby('month').agg({
        'actual_revenue': 'sum',
        'revenue_with_dynamic_price': 'sum'
    }).reset_index().rename(columns={'revenue_with_dynamic_price': 'high_dynamic'})
    
    # Merge monthly aggregates (actual revenue should be the same across scenarios)
    monthly = low_monthly[['month', 'actual_revenue']].copy()
    monthly = monthly.merge(low_monthly[['month', 'low_dynamic']], on='month', how='left')
    monthly = monthly.merge(med_monthly[['month', 'med_dynamic']], on='month', how='left')
    monthly = monthly.merge(high_monthly[['month', 'high_dynamic']], on='month', how='left')
    
    # Calculate the additional revenue (differences) for stacking.
    # We assume the dynamic revenues are greater than or equal to actual revenue.
    low_diff = monthly['low_dynamic'] - monthly['actual_revenue']
    med_diff = monthly['med_dynamic'] - monthly['low_dynamic']
    high_diff = monthly['high_dynamic'] - monthly['med_dynamic']
    
    x = np.arange(len(monthly))
    width = 0.6  # bar width

    fig, ax = plt.subplots(figsize=(10, 6))
    
    # Plot the bottom segment: Actual Revenue
    ax.bar(x, monthly['actual_revenue'], width, label='Actual Revenue', color="#d0cece")
    # Plot the next segment: Low Risk additional revenue
    ax.bar(x, low_diff, width, bottom=monthly['actual_revenue'], 
           label='Dynamic Revenue (Low)', color="#b0ccf7")
    # Next segment: Medium Risk additional revenue
    ax.bar(x, med_diff, width, bottom=monthly['actual_revenue'] + low_diff, 
           label='Dynamic Revenue (Medium)', color="#3c649f")
    # Top segment: High Risk additional revenue
    ax.bar(x, high_diff, width, bottom=monthly['actual_revenue'] + low_diff + med_diff, 
           label='Dynamic Revenue (High)', color="#1a2d48")
    
    ax.set_xticks(x)
    ax.set_xticklabels(monthly['month'])
    ax.set_ylabel('Revenue (SEK)')
    ax.set_title('Monthly Revenue Scenarios (Stacked)')
    ax.legend()
    
    plt.tight_layout()
    plt.show()


  

def plot_merged_revenue(merged_actual):
    #1a2d48
    #2c456b
    #3c649f
    #83aff0
    #b0ccf7
    #e4eefc
    # Hardcoded colors
    line_color1 = '#1a2d48'    # Actual Revenue line color
    marker_color1 = '#1a2d48'  # Actual Revenue marker color
    line_color2 = '#b0ccf7'    # Dynamic Revenue line color
    marker_color2 = '#b0ccf7'  # Dynamic Revenue marker color

    # Compute actual revenue per hour
    merged_actual = merged_actual.copy()
    merged_actual['actual_revenue'] = merged_actual['actual_energy'] * BASE_PRICE

    # Convert timestamps to numeric values for interpolation
    x = mdates.date2num(merged_actual['ds'])
    
    # Define new x-axis values with more points for a smooth curve
    x_new = np.linspace(x.min(), x.max(), 300)

    # Generate smooth curves via cubic spline interpolation
    spline_actual = make_interp_spline(x, merged_actual['actual_revenue'], k=3)
    actual_revenue_smooth = spline_actual(x_new)

    spline_dynamic = make_interp_spline(x, merged_actual['revenue_with_dynamic_price'], k=3)
    dynamic_revenue_smooth = spline_dynamic(x_new)

    # Create the plot
    plt.figure(figsize=(10, 6))
    plt.plot(mdates.num2date(x_new), actual_revenue_smooth, label='Actual Revenue', linewidth=2, color=line_color1)
    plt.plot(mdates.num2date(x_new), dynamic_revenue_smooth, label='Dynamic Revenue', linewidth=2, color=line_color2)
    
    # Plot the original data points with small markers
    plt.plot(merged_actual['ds'], merged_actual['actual_revenue'], 'o', markersize=4, color=marker_color1)
    plt.plot(merged_actual['ds'], merged_actual['revenue_with_dynamic_price'], 'o', markersize=4, color=marker_color2)
    
    plt.xlabel('Time')
    plt.ylabel('Revenue (SEK)')
    plt.title('Hourly Revenue: Actual vs Dynamic Pricing')
    plt.legend()
    plt.grid(False)
    ax = plt.gca()
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=1))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.show()

if __name__ == '__main__':
     # Define forecast period (assumed already defined as global variables)
    # FORECAST_START_DATE and SIMULATION_END_DATE should be defined globally.

    # --- Low-Risk Scenario ---
    # For a conservative scenario, we use a slightly higher minimum,
    # lower maximum, and lower elasticity.
    low_scalemin =  0.9   # e.g. increasing the minimum index
    low_scalemax = 1.2   # e.g. decreasing the maximum index
    low_elasticity = 0.1  # lower responsiveness
    low_df = simulate_forecast(FORECAST_START_DATE, SIMULATION_END_DATE,
                               scalemin=low_scalemin,
                               scalemax=low_scalemax,
                               price_elasticity=low_elasticity)
    
    # --- Medium-Risk Scenario (Default) ---
    
    med_scalemin = 0.8   # e.g. increasing the minimum index
    med_scalemax = 1.4   # e.g. decreasing the maximum index
    med_elasticity = 0.07  # lower responsiveness
    med_df = simulate_forecast(FORECAST_START_DATE, SIMULATION_END_DATE,
                               scalemin=med_scalemin,
                               scalemax=med_scalemax,
                               price_elasticity=med_elasticity)
    
    # --- High-Risk Scenario ---
    # For an aggressive scenario, we use a lower minimum,
    # higher maximum, and higher elasticity.
    high_scalemin = 0.7   # lower minimum index
    high_scalemax = 1.7     # higher maximum index
    high_elasticity = 0.01  # higher responsiveness
    high_df = simulate_forecast(FORECAST_START_DATE, SIMULATION_END_DATE,
                                scalemin=high_scalemin,
                                scalemax=high_scalemax,
                                price_elasticity=high_elasticity)
    # 
    # Now pass the three DataFrames to our monthly plotting function
    plot_monthly_revenue_scenarios_stacked(low_df, med_df, high_df)
    #results_df = simulate_forecast(FORECAST_START_DATE, SIMULATION_END_DATE)
    # print("\nDaily forecasting simulation results:")
    # print(results_df)
    # totals = results_df.aggregate({'actual_revenue': 'sum', 'revenue_with_dynamic_price': 'sum'})
    # totals['pct_diff'] = (totals['revenue_with_dynamic_price'] - totals['actual_revenue']) / totals['actual_revenue']
    # # make pct diff print decimal value with 4 decimals
    # totals['pct_diff'] = f"{totals['pct_diff']:,.4f}"
    # print("\nTotal revenues")
    # print(totals)
