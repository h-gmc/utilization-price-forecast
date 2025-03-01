import pandas as pd

def get_data(file_path="data/site_data.csv"):
    """
    Reads the CSV file, filters out charging sessions with duration less than 5 minutes
    or greater than 60 minutes, and accurately distributes energy demand on an hourly basis.
    For each session (lasting at most 1 hour):
      - If the session is fully within one hour, all energy is assigned to that hour.
      - If the session spans two hours, energy is split proportionally between the two hours.
      
    Returns:
        A DataFrame with 'Start time' (floored to the hour) as the index and 'Energy_Wh' as the only column.
    """
    # Read CSV and parse dates for both start and stop times
    df = pd.read_csv(file_path, parse_dates=["Start time", "Count.Stop time"])
    
    # Calculate session duration in minutes
    df["Duration"] = (df["Count.Stop time"] - df["Start time"]).dt.total_seconds() / 60
    
    # Filter out sessions with duration less than 5 minutes or greater than 60 minutes
    df = df[(df["Duration"] >= 5) & (df["Duration"] <= 60)]
    
    # Rename the energy column for consistency
    df.rename(columns={"Modified Count.Energy (Wh)": "Energy_Wh"}, inplace=True)
    
    # Convert Energy_Wh to numeric and drop rows with NaN values in Energy_Wh
    df["Energy_Wh"] = pd.to_numeric(df["Energy_Wh"], errors="coerce")
    df.dropna(subset=["Energy_Wh"], inplace=True)
    
    # List to store hourly contributions
    hourly_data = []
    
    # Process each session
    for _, row in df.iterrows():
        start = row["Start time"]
        stop = row["Count.Stop time"]
        energy = row["Energy_Wh"]
        
        # If the session is completely within one hour, assign all energy to that hour.
        if start.floor("H") == stop.floor("H"):
            hour = start.floor("H")
            hourly_data.append({"Start time": hour, "Energy_Wh": energy})
        else:
            # The session spans two hours.
            # Compute the end of the first hour
            first_hour_end = start.floor("H") + pd.Timedelta(hours=1)
            # Calculate the fraction of the session in the first hour
            first_fraction = (first_hour_end - start).total_seconds() / (stop - start).total_seconds()
            second_fraction = 1 - first_fraction
            
            # Energy allocated to the first hour
            energy_first = energy * first_fraction
            # Energy allocated to the second hour
            energy_second = energy * second_fraction
            
            hourly_data.append({"Start time": start.floor("H"), "Energy_Wh": energy_first})
            hourly_data.append({"Start time": stop.floor("H"), "Energy_Wh": energy_second})
    
    # Convert list to DataFrame and aggregate energy per hour
    hourly_df = pd.DataFrame(hourly_data)
    hourly_df = hourly_df.groupby("Start time", as_index=True).sum()
    
    return hourly_df

if __name__ == "__main__":
    data = get_data()
    print(data.head())

