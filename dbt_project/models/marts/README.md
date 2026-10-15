# Data Marts Layer (`marts/`)

The Presentation Layer contains models exposed to downstream consumers (Tableau, PowerBI, and the AI Engine).

Data Marts are organized into specific business domains:
- **`ambulatoria/`**: Models relating to outpatient consultations, daily metrics, and diagnosis statistics.
- **`internacion/`**: Models dealing with active hospital stays, bed occupancy (`ocupacion_camas`), vital signs, and inpatient prescriptions.

### Performance Matters
To ensure efficient query execution, many models in this layer are built using **`materialized_view`** or **incremental** materialization strategies, allowing consumers to query large volumes of data without touching the operational database.
