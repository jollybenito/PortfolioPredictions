import pandas as pd
from sqlalchemy import text

def save_to_db_upsert(df, table_name, engine, unique_cols):
    """
    Simulated Upsert: Deletes existing rows for the current date/type before inserting.
    """
    if df.empty:
        return
        
    # Build the deletion criteria based on the first row
    # (Assumes all rows in df share the same date/type/etc. for the 'snapshot')
    conditions = []
    for col in unique_cols:
        val = df[col].iloc[0]
        if isinstance(val, str):
            conditions.append(f"{col} = '{val}'")
        else:
            conditions.append(f"{col} = '{val}'")

    where_clause = " AND ".join(conditions)
    
    with engine.connect() as conn:
        print(f"  Cleaning existing records in {table_name}: {where_clause}")
        conn.execute(text(f"DELETE FROM {table_name} WHERE {where_clause}"))
        conn.commit()
        
    print(f"  Inserting {len(df)} new records into {table_name}...")
    df.to_sql(table_name, engine, if_exists='append', index=False, method='multi', chunksize=1000)
