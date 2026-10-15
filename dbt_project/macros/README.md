# Macros (`macros/`)

Macros are Jinja templates used to reuse SQL logic across the project, maintaining a DRY codebase.

Macros streamline repetitive transformations by abstracting complex SQL logic (e.g., `CASE WHEN` statements or string concatenations).

### Key Macros in this Project
- **`decodificar_sexo.sql`**: A standard macro to decode gender acronyms (M/F) into descriptive strings across patient models.
- **`edad_con_unidad.sql`**: Handles the logic of calculating ages and appending the correct unit (Years/Months/Days) for pediatric and adult patients.
- **`nombre_medico.sql` & `nombre_paciente.sql`**: Standardizes the concatenation of First Name, Last Name, and Titles to ensure reporting consistency.
- **`override_create_schema.sql`**: A system override macro. By default, dbt generates schemas with a `target_schema_custom_schema` naming convention. This macro overrides that behavior to enforce output into the `dbt_analytics` schema.
