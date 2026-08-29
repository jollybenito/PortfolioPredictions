# Docker Management Instructions

This project uses Docker to manage the PostgreSQL database and the Python environment for portability and consistency.

## Database Credentials
Defined in the `.env` file at the root:
- **DB Name**: `portfolio_db`
- **User**: `portfolio_admin`
- **Password**: `secure_portfolio_pwd_2026`
- **Port**: `5432` (mapped to localhost:5432)

## Commands

### 1. Start the System
To build the application image and start the database:
```bash
docker compose up -d
```

### 2. Stop thedocker compose up -d
 System
To stop all containers:
```bash
docker compose stop
```

### 3. Tear Down
To stop and remove containers and networks:
```bash
docker compose down
```

### 4. Run Migration (First Time Only) # NO LONGER RELEVANT
### docker compose exec app python migrate_csv_to_db.py

### 5. Run the ETL Pipeline
To download new data and update portfolios:
```bash
docker compose exec app python ETL_portfolio_pipeline.py
```

### 6. Access Database (CLI)
```bash
docker compose exec db psql -U portfolio_admin -d portfolio_db
```

## Data Persistence
PostgreSQL data is stored in the `./pgdata/` folder in your project root. Do not delete this folder unless you want to reset the database.
