import pandas as pd

def get_data(file_path="data/site_data.csv"):
    """
    Reads the CSV file, filters out anomalous charging sessions,
    and returns data with 'Start time' as the index and 'Energy_Wh' as the only column.
    """
    # Read CSV and parse dates
    df = pd.read_csv(file_path, parse_dates=["Start time", "Count.Stop time"])
    
    # Calculate session duration in minutes
    df["Duration"] = (df["Count.Stop time"] - df["Start time"]).dt.total_seconds() / 60  # Convert to minutes

    # Filter out anomalies: Remove rows where duration < 5 min or > 60 min
    df = df[(df["Duration"] >= 5) & (df["Duration"] <= 60)]
    
    # Rename 'Modified Count.Energy (Wh)' to 'Energy_Wh'
    df.rename(columns={"Modified Count.Energy (Wh)": "Energy_Wh"}, inplace=True)

    # Convert 'Energy_Wh' to numeric
    df["Energy_Wh"] = pd.to_numeric(df["Energy_Wh"], errors="coerce")

    # Drop NaN values in 'Energy_Wh'
    df.dropna(subset=["Energy_Wh"], inplace=True)

    # Set 'Start time' as the index
    df.set_index("Start time", inplace=True)

    # Return only the 'Energy_Wh' column
    return df[["Energy_Wh"]]

if __name__ == "__main__":
    # Print first few rows for testing
    data = get_data()
    print(data.head())
