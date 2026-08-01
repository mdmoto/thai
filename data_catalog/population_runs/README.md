# Population run catalog

Population runs are content-addressed artifacts. Development validation writes
to `docs/validation/population-artifacts`; production runs must write private,
immutable objects to the configured Google Cloud Storage artifact bucket.

PostgreSQL stores only the URI, SHA-256, size, media type, schema version and
access metadata. Population Parquet files and customer inputs must not be
embedded in business JSON columns or made publicly accessible.
