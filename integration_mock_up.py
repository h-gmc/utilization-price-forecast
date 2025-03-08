import pandas as pd
from datetime import datetime, timedelta
from prophet import Prophet
import process_data
import warnings
warnings.filterwarnings("ignore")

# Global parameters: dynamic price index range and forecast period
PRICE_INDEX_MIN = 1.0   # Minimum dynamic price index
PRICE_INDEX_MAX = 1.4   # Maximum dynamic price index
FORECAST_START_DATE = datetime(2024, 7, 1)   # Start date for forecast simulation
SIMULATION_END_DATE = datetime(2024, 7, 10)    # End date for simulation

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
    fcst_day['predicted_revenue'] = fcst_day['yhat'] * fcst_day['price_index']
    forecasted_energy = fcst_day['yhat'].sum()
    predicted_revenue = fcst_day['predicted_revenue'].sum()
    daily_forecast = {'forecasted_energy': forecasted_energy, 'predicted_revenue': predicted_revenue}
    print(f"Aggregated daily forecast: Energy={forecasted_energy:.2f}, Revenue={predicted_revenue:.2f}")
    return fcst_day, daily_forecast

# Simulate day-ahead forecasting: for each day, forecast next 24h, compare with actual, and compute dynamic revenue
def simulate_forecast(forecast_start_date, simulation_end_date, scalemin=PRICE_INDEX_MIN, scalemax=PRICE_INDEX_MAX):
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
        actual_revenue = actual_energy  # Fixed price of 1
        
        # Merge actual hourly data with forecasted price indices to compute dynamic revenue per hour
        actual_next_day = actual_next_day.rename(columns={'Start time': 'ds', 'Energy_Wh': 'actual_energy'})
        merged_actual = fcst_day[['ds', 'price_index']].merge(actual_next_day[['ds', 'actual_energy']], on='ds', how='inner')
        merged_actual['revenue_with_dynamic_price'] = merged_actual['actual_energy'] * merged_actual['price_index']
        revenue_with_dynamic_price = merged_actual['revenue_with_dynamic_price'].sum()
        
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

if __name__ == '__main__':
    results_df = simulate_forecast(FORECAST_START_DATE, SIMULATION_END_DATE)
    print("\nDaily forecasting simulation results:")
    print(results_df)
