import pandas as pd

RAW_PATH = "data/raw/DataCoSupplyChainDataset.csv"
CLEAN_PATH = "data/clean/dataco_cleaned.csv"

def main():
    # Load full dataset (fast, safe)
    df = pd.read_csv(
        RAW_PATH,
        encoding="latin1",
        low_memory=True
    )

    # Rename date columns
    df = df.rename(columns={
        "order date (DateOrders)": "order_date",
        "shipping date (DateOrders)": "shipping_date"
    })

    # Parse dates
    df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
    df["shipping_date"] = pd.to_datetime(df["shipping_date"], errors="coerce")

    # Drop PII
    pii_cols = [
        "Customer Email",
        "Customer Fname",
        "Customer Lname",
        "Customer Password",
        "Customer Street",
        "Customer Zipcode"
    ]
    df = df.drop(columns=[c for c in pii_cols if c in df.columns])

    # Lead-time metric
    df["order_to_ship_days"] = (
        df["shipping_date"] - df["order_date"]
    ).dt.days

    # Remove invalid rows
    df = df[df["order_to_ship_days"] >= 0]

    # Export clean dataset
    df.to_csv(CLEAN_PATH, index=False)

    print(f"Export complete: {len(df):,} rows written to {CLEAN_PATH}")

if __name__ == "__main__":
    main()
