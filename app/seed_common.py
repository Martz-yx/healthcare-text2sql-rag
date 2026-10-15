"""
Seed training for shared/common tables and documentation.

Contains DDLs, documentation, and examples for tables referenced by BOTH
the ambulatoria and internacion domains: paciente, usuario, profesional,
servicio, establecimiento, CIE-10 hierarchy, medicamento, via_medicine,
geography (pais, region, departamento, distrito, barrio), and demographic
lookups.  Also includes cross-domain business documentation (ILIKE usage,
date handling, patient name construction, etc.).

Each train_* call dispatches through the shared sink defined in
seed_training.py; entries land in ChromaDB with source='seed:common'
and are rebuilt independently of the other seed sets.
"""

from seed_training import train_ddl, train_doc, train_example

def populate() -> None:
    """Run every populate step for the common seed set."""
    _populate_ddls()
    _populate_docs()
    _populate_examples()

# =========================================================================
# DDLs — shared reference tables
# =========================================================================

def _populate_ddls() -> None:
    """DDLs for tables referenced by both ambulatoria and internacion."""

    # -----------------------------------------------------------------
    # Core entities: paciente, usuario, profesional
    # -----------------------------------------------------------------
    print("  DDLs: core entities (paciente, usuario, profesional)...")

    train_ddl("""
-- Tabla maestra de pacientes. Referenciada por ambos dominios:
-- ambulatoria: paciente_asignacion.codigo_paciente
-- internacion: hospitalario_asignacion.codigo_paciente
CREATE TABLE public.paciente (
    codigo_paciente character varying(20) NOT NULL PRIMARY KEY,  -- cedula o pasaporte (PK)
    tipo_documento character varying(1) NOT NULL,                -- '1'=cedula, '2'=pasaporte, '4'=otro
    codigo_ficha character varying(13),                          -- numero de ficha clinica
    primer_nombre text,
    segundo_nombre text,
    primer_apellido text,
    segundo_apellido text,
    apelido_casada text,                                         -- apellido de casada
    fecha_nacimiento date,
    hora_nacimiento time without time zone,
    cod_lugar_nacimiento character varying(3),
    codigo_departamento character varying(2),                    -- departamento de nacimiento
    codigo_distrito character varying(3),                        -- distrito de nacimiento
    codigo_nacionalidad character varying(3),                    -- nacionalidad (join pais)
    codigo_etnia character varying(5),                           -- etnia (join etnia)
    sexo character varying(1),                                   -- '1'=femenino, '2'=masculino, '0'=no especificado
    estado_civil character varying(1),                           -- '1'=SD, '2'=soltero, '3'=casado, '4'=divorciado, '5'=viudo, '6'=union libre, '9'=no especificado
    cod_departamento_residencia character varying(2),            -- departamento residencia (join departamento)
    cod_distrito_residencia character varying(3),                -- distrito residencia (join distrito)
    direccion_residencia character varying(40),
    cod_barrio_residencia character varying(3),                  -- barrio residencia (join barrio)
    area character varying(1),                                   -- '0'=urbano, '1'=rural
    sector character varying(5),
    manzana character varying(5),
    numero_casa character varying(5),
    residencia_telefono character varying(15),
    email character varying(128),
    residencia_ocacional character varying(40),
    residencia_referencia text,
    nivel_educativo character varying(2),                        -- '1'=Ninguno, '2'=Educ.Inicial, '3'=Primaria, '4'=Secundaria, '5'=Escolar Basica, '6'=Escolar Media, '7'=Universitario, '8'=Sup No Universitario, '9'=No Aplica, '10'=Ignorado
    anho_cursado character varying(2),                          -- ultimo anho cursado
    seguro_medico character varying(8),
    situacion_laboral character varying(1),                      -- '1'=No Aplica, '2'=No Trabaja, '3'=Trabaja
    ocupacion character varying(4),                              -- (join ocupacion)
    profesion character varying(4),                              -- (join profesion)
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    alterar_telefono character(15),
    codigo_tipo_sangre smallint,                                 -- (join tipo_sangre)
    codigo_relacion_guardian smallint,                            -- (join relacion_guardian)
    codigo_guardian character varying(20),                        -- cedula del guardian
    nombres_guardian text,
    apellidos_guardian text,
    estado_privacidad boolean,
    btimestamp character varying(15),
    otro_barrio character varying(40),
    is_desconocido boolean                                       -- true=paciente no identificado (trauma inconsciente)
);
""")

    train_ddl("""
-- Tabla de usuarios del sistema (medicos, enfermeros, administrativos).
-- Referenciada por ambos dominios via codigo_medico, creacion_usuario, etc. y el codigo establecimiento.
-- ATENCION (Multi-hospital): Un mismo profesional (médico/enfermero) puede trabajar en múltiples establecimientos. Por ello, la tabla replica el mismo codigo_usuario para cada codigo_establecimiento. Para evitar multiplicidad de filas (fan-out) en las consultas, SIEMPRE se debe hacer JOIN combinando codigo_usuario y codigo_establecimiento, o aislar el registro mediante un SELECT DISTINCT.
CREATE TABLE public.usuario_replication (
    usuario_replication_id uuid NOT NULL
    codigo_establecimiento character varying(16), NOT NULL
    codigo_usuario character varying(10) NOT NULL PRIMARY KEY,
    nombres character varying(30),
    apellidos character varying(30),
    descripcion character varying(128),
    estado character varying(1),                                -- estado de la cuenta, 0- Inactivo, 1- Activo
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    btimestamp character varying(15),
    pin_usuario character varying(32),
    servicios integer[],                                        -- array de IDs de servicios con acceso
    eid_timestamp timestamp without time zone
);
""")

    train_ddl("""
-- Extension de usuario con datos profesionales/licencia medica.
-- Se une a: usuario.codigo_usuario via codigo_medico (FK)
-- ATENCION (Multi-hospital): Un mismo profesional médico puede trabajar en múltiples establecimientos. Por ello, la tabla replica el mismo codigo_medico para cada codigo_establecimiento. Para evitar multiplicidad de filas (fan-out) en las consultas, SIEMPRE se debe hacer JOIN combinando codigo_medico y codigo_establecimiento, o aislar el registro mediante un SELECT DISTINCT.
CREATE TABLE public.profesional_replication (
    profesional_replication_id uuid NOT NULL
    codigo_establecimiento character varying(16), NOT NULL
    codigo_medico character varying(10) NOT NULL PRIMARY KEY,   -- = usuario.codigo_usuario
    numero_registro character varying(10) NOT NULL,             -- numero de registro profesional
    codigo_especialidad character varying(10),                  -- especialidad medica
    activo character varying(1),                                -- activo como profesional
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    verificar character varying(1),                             -- estado de verificacion
    title character varying(128),                               -- titulo profesional
    verificar_fecha date,
    verificar_hora time without time zone,
    FOREIGN KEY (codigo_medico) REFERENCES usuario(codigo_usuario)
);
""")

    # -----------------------------------------------------------------
    # Organization: servicio, establecimiento, clase
    # -----------------------------------------------------------------
    print("  DDLs: organization (servicio, establecimiento)...")

    train_ddl("""
-- Catalogo de servicios/departamentos medicos.
-- Referenciado por ambos dominios: paciente_asignacion.codigo_servicio,
-- hospitalario_asignacion.codigo_servicio, sala.codigo_servicio, etc.
CREATE TABLE public.servicio (
    codigo_servicio integer NOT NULL PRIMARY KEY,
    nombre_servicio character varying(200) NOT NULL,          -- ej. 'Medicina General', 'Pediatria'
    codigo_clase character varying(5),                        -- clase/familia (join clase)
    activo character varying(1),                              -- '1'=activo
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10)
);
""")

    train_ddl("""
-- Tabla maestra de establecimientos de salud.
-- Se une a: distrito via codigo_distrito (distrito del establecimiento)
-- Referenciado por: casi todas las tablas de ambos dominios via codigo_establecimiento
-- Usar ILIKE para buscar por nombre: WHERE nombre_establecimiento ILIKE '%regional%'
CREATE TABLE public.establecimiento (
    codigo_establecimiento character varying(16) NOT NULL PRIMARY KEY,
    codigo_region character varying(4) NOT NULL,              -- region sanitaria
    codigo_subregion character varying(4) NOT NULL,           -- subregion sanitaria
    codigo_distrito character varying(4) NOT NULL,            -- distrito del establecimiento (join distrito)
    codigo_serv character varying(4) NOT NULL,                -- codigo de servicio
    tipo_servicio character varying(4),
    nombre_establecimiento character varying(60),             -- nombre del hospital/USF
    director character varying(80),
    direccion character varying(100),
    telefono character varying(30),
    email character varying(30),
    area character varying(1),
    estado character varying(1),
    codigoesta character varying(12),
    observacion character varying(120),
    latitud numeric(11,7),
    longitud numeric(11,7),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    id_establecimiento character(4)
);
""")

    train_ddl("""
-- Clasificacion jerarquica de servicios (arbol padre/hijo).
-- Referenciado por: servicio.codigo_clase
-- Nivel 1: CONSULTORIOS, INTERNADOS, URGENCIAS, METODOS AUXILIARES, etc.
-- Nivel 2: LABORATORIO, IMAGENES, PROCEDIMIENTOS, etc.
CREATE TABLE public.clase (
    codigo integer NOT NULL PRIMARY KEY,
    nombre text NOT NULL,
    codigo_padre integer,                                     -- padre en jerarquia (self-join)
    nivel smallint,                                           -- 1=raiz, 2=hijo, ...
    orden smallint,
    tiene_horario boolean,                                    -- permite agendar horarios
    activo boolean,
    FOREIGN KEY (codigo_padre) REFERENCES clase(codigo)
);
""")

    # -----------------------------------------------------------------
    # Medication catalogs
    # -----------------------------------------------------------------
    print("  DDLs: medication catalogs...")

    train_ddl("""
-- Catalogo de medicamentos por establecimiento/sucursal.
-- Referenciado por: consulta_medicamento (ambulatoria),
--   hospitalario_medicaciones_soluciones (internacion)
CREATE TABLE public.medicamento_total (
	codigo_medicamento int8 NOT NULL,
	nombre_droga text NULL,                                    -- nombre comercial
	presentacion text NULL,                                    -- Caja, Unidad, etc.
	forma_farmaceutica text NULL,                              -- Inyectable, comprimido, etc.
	concentracion text NULL,                                   -- 4MG, 125 ML, 2 %, etc.
	creacion_fecha date NULL,
	modificacion_fecha date NULL,
	CONSTRAINT medicamento_total_pkey PRIMARY KEY (codigo_medicamento)
);
""")

    # -----------------------------------------------------------------
    # CIE-10 hierarchy
    # -----------------------------------------------------------------
    print("  DDLs: CIE-10 hierarchy...")

    train_ddl("""
-- Catalogo de diagnosticos CIE-10 (nivel mas detallado).
-- Referenciado por: consulta_diagnostico (ambulatoria),
--   hospitalario_doctor_diagnostico y hospitalario_doctor_datos_alta (internacion)
CREATE TABLE public.cie10 (
    codigo_cie10a character varying(3) NOT NULL,              -- categoria (3 chars, ej. 'J06')
    codigo_cie10b character varying(4) NOT NULL,              -- subcategoria (1 char, ej. '9')
    nombre_cie10 character varying(300),                      -- nombre del diagnostico
    descripcion_cie10 text,
    aplimasc numeric(1,0),                                    -- aplica a masculinos (1=si)
    aplifem numeric(1,0),                                     -- aplica a femeninos (1=si)
    apldesde numeric(3,0),                                    -- edad minima
    apltdesde character varying(1),
    aplhasta numeric(3,0),                                    -- edad maxima
    aplthasta character varying(1),
    aplmort numeric(1,0),                                     -- mortalidad (1=si)
    maldef numeric(1,0),                                      -- malformacion congenita (1=si)
    PRIMARY KEY (codigo_cie10a, codigo_cie10b)
);
""")

    train_ddl("""
-- Subgrupos CIE-10 (categoria de 3 caracteres)
-- Se une a: cap_cie10.codcap via codcap, grupo_cie10.codgru via codgru
-- codigo_cie10a = cie10.codigo_cie10a
CREATE TABLE public.subgrupo_cie10 (
    codigo_cie10a character varying(3) NOT NULL PRIMARY KEY,
    nombre_subgrupo character varying(250),
    defincl text,
    defnoincl text,
    aplimasc numeric(1,0),
    aplifem numeric(1,0),
    apldesde numeric(3,0),
    apltdesde character varying(1),
    aplhasta numeric(3,0),
    aplthasta character varying(1),
    aplmort numeric(1,0),
    maldef numeric(1,0),
    codcap character varying(2) NOT NULL,                     -- capitulo
    codgru character varying(10)                              -- grupo
);
""")

    # -----------------------------------------------------------------
    # Geography: pais, region, departamento, distrito, barrio
    # -----------------------------------------------------------------
    print("  DDLs: geography...")

    train_ddl("""
-- Catalogo de paises / nacionalidades
-- Referenciado por: paciente.codigo_nacionalidad
CREATE TABLE public.pais (
    codigo_nacimiento character varying(3) NOT NULL PRIMARY KEY,
    nombre_nacionalidad character varying(40),
    pais character varying(40),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora date,
    modificacion_usuario character varying(10),
    iso_3166_1 character varying(3)
);
""")

    train_ddl("""
-- Catalogo de regiones sanitarias
CREATE TABLE public.region (
    codigo_region character varying(2) NOT NULL,
    codigo_subregion character varying(3) NOT NULL,
    nombre_region character varying(40) NOT NULL,
    director character varying(30),
    direccion character varying(50),
    telefono character varying(30),
    email character varying(30),
    PRIMARY KEY (codigo_region, codigo_subregion)
);
""")

    train_ddl("""
-- Catalogo de departamentos (equivalente a provincia/estado)
-- Referenciado por: paciente.cod_departamento_residencia, distrito.codigo_departamento
CREATE TABLE public.departamento (
    codigo_departamento character varying(3) NOT NULL PRIMARY KEY,
    nombre_departamento character varying(40),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora date,
    modificacion_usuario character varying(10),
    latitud numeric(11,7),
    longitud numeric(11,7)
);
""")

    train_ddl("""
-- Catalogo de distritos dentro de un departamento
-- Referenciado por: paciente ON (cod_departamento_residencia, cod_distrito_residencia)
CREATE TABLE public.distrito (
    codigo_departamento character varying(2) NOT NULL,
    codigo_distrito character varying(3) NOT NULL,
    nombre_distrito character varying(50) NOT NULL,
    codigo_region character varying(2) NOT NULL,
    codigo_subregion character varying(3) NOT NULL,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    latitud numeric(11,7),
    longitud numeric(11,7),
    PRIMARY KEY (codigo_departamento, codigo_distrito)
);
""")

    train_ddl("""
-- Catalogo de barrios dentro de un distrito
-- Referenciado por: paciente ON (cod_departamento_residencia, cod_distrito_residencia, cod_barrio_residencia)
CREATE TABLE public.barrio (
    codigo_departamento character varying(2) NOT NULL,
    codigo_distrito character varying(3) NOT NULL,
    codigo_barrio character varying(3) NOT NULL,
    nombre_barrio character varying(50),
    latitud double precision,
    longitud double precision,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_departamento, codigo_distrito, codigo_barrio)
);
""")

    # -----------------------------------------------------------------
    # Demographic / relation lookups
    # -----------------------------------------------------------------
    print("  DDLs: demographic lookups...")

    train_ddl("""
-- Catalogo de etnias. Referenciado por: paciente.codigo_etnia
CREATE TABLE public.etnia (
    codigo_etnia character varying(5) NOT NULL PRIMARY KEY,
    nombre_etnia character varying(40),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora date,
    modificacion_usuario character varying(10)
);
""")

    train_ddl("""
-- Catalogo de ocupaciones. Referenciado por: paciente.ocupacion
CREATE TABLE public.ocupacion (
    codigo_ocupacion character varying(4) NOT NULL PRIMARY KEY,
    nombre_ocupacion character varying(150),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10)
);
""")

    train_ddl("""
-- Catalogo de tipos de sangre. Referenciado por: paciente.codigo_tipo_sangre
CREATE TABLE public.tipo_sangre (
    codigo_tipo_sangre smallint NOT NULL PRIMARY KEY,        -- 1=A+, 2=B+, 3=O+, 4=AB+, 5=A-, 6=B-, 7=O-, 8=AB-, 9=NO SE
    tipo_sangre character(8) NOT NULL
);
""")

    train_ddl("""
-- Catalogo de unidades de edad. Referenciado por: paciente_asignacion.tipo_edad,
-- hospitalario_asignacion.tipo_edad
CREATE TABLE public.tipo_edad (
    tipo numeric NOT NULL PRIMARY KEY,                       -- 1=Anho, 2=Mes, 3=Dia, 4=Hora, 5=Minuto
    descripcion text
);
""")

    train_ddl("""
-- Catalogo de tipos de relacion familiar
-- Referenciado por: relacion_familia.tipo_relacion_familiar
CREATE TABLE public.tipo_relacion_familiar (
    codigo_relacion smallint,                                 -- 1=Madre, 2=Padre, 3=Hermana, 4=Hermano, 5=Esposa, 6=Marido, 7=Hija, 8=Hijo, ...
    nombre_relacion character varying(20),
    genero character(1)                                       -- 'F'=femenino, 'M'=masculino
);
""")
    print()

# =========================================================================
# Business documentation — cross-domain
# =========================================================================

def _populate_docs() -> None:
    """Business documentation that applies to both ambulatoria and internacion."""
    print("  Docs: cross-domain documentation...")

    train_doc(
        "RESUMEN DEL SISTEMA: Esta base de datos cubre dos dominios del Sistema de Informacion "
        "Hospitalaria (HIS):\n\n"
        "1) AMBULATORIA (consultas externas): La tabla central es paciente_asignacion. "
        "Cubre turnos/citas, triaje (preconsulta), consulta medica, diagnosticos CIE-10 "
        "(consulta_diagnostico), medicamentos (consulta_medicamento), procedimientos "
        "(consulta_procedimiento), trauma (trauma_consulta/trauma_preconsulta), "
        "prescripciones a largo plazo (long_term_prescription), certificados medicos, "
        "y agenda de turnos. "
        "Flujo: agenda -> paciente_asignacion -> preconsulta (triaje enfermeria) -> consulta (medico). "
        "Para turnos cancelados: cancelar_turno = 'SI'. "
        "Edad del paciente: paciente_asignacion.edad_paciente + tipo_edad (1=anho, 2=mes, 3=dia).\n\n"
        "2) INTERNACION (hospitalizacion): La tabla central es hospitalario_asignacion. "
        "Cubre admisiones, infraestructura de camas (edificio > piso > sala > cama > cama_estado), "
        "nota inicial del medico, evoluciones medicas SOAP, medicaciones hospitalarias, "
        "cirugias, interconsultas, enfermeria NANDA-Henderson, dietas, datos de alta/egreso, "
        "obstetricia, y trauma hospitalario. Todas las tablas hospitalario_* se unen via "
        "(codigo_establecimiento, codigo_asignacion). "
        "Filtro critico para pacientes actualmente internados: "
        "fin_del_evento = '0' AND is_outdated = false. "
        "fin_del_evento = '1' significa alta/egreso; is_outdated = true significa "
        "reemplazado por transferencia de cama.\n\n"
        "TABLAS COMPARTIDAS: paciente, usuario, profesional, servicio, establecimiento, "
        "medicamento, cie10/grupo_cie10/subgrupo_cie10/cap_cie10, via_medicine, "
        "departamento/distrito/barrio, y catalogos demograficos. "
        "Estas tablas se usan en ambos dominios para JOINs."
    )

    train_doc(
        "IMPORTANTE: Las columnas de texto pueden tener capitalizacion inconsistente. "
        "Usar ILIKE en vez de LIKE para busquedas por patron (ej. WHERE nombre_cie10 ILIKE '%diabetes%'). "
        "Usar LOWER() para comparaciones de igualdad. "
        "Nunca usar = o LIKE para comparaciones de texto a menos que se requiera coincidencia exacta. "
        "Esto aplica a nombres de pacientes, medicamentos, diagnosticos, servicios y establecimientos."
    )

    train_doc(
        "JERARQUIA GEOGRAFICA: pais > region > departamento > distrito > barrio. "
        "paciente almacena residencia al nivel de departamento/distrito/barrio. "
        "paciente_asignacion (ambulatoria) replica estos campos para la residencia al momento del turno. "
        "Para agrupar por departamento: JOIN departamento d ON p.cod_departamento_residencia = d.codigo_departamento."
    )

    train_doc(
        "USUARIO vs PROFESIONAL: usuario es la cuenta de sistema (login, nombre, servicios). "
        "profesional extiende a usuario agregando datos de licencia medica (numero_registro, especialidad, titulo). "
        "No todo usuario es profesional; todo profesional tiene un usuario. "
        "Para nombre de medico/enfermero: u.nombres || ' ' || u.apellidos. "
        "Para nombre de paciente: TRIM(p.primer_nombre) || ' ' || TRIM(p.primer_apellido)."
    )

    train_doc(
        "JERARQUIA CIE-10 — COMO AGREGAR DIAGNOSTICOS: "
        "Niveles: cap_cie10 (capitulos, 2 chars) > grupo_cie10 (grupos, ej. 'J00-J06') "
        "> subgrupo_cie10 (subcategorias, 3 chars) > cie10 (detalle, 3+4 chars). "
        "Para agrupar diagnosticos por capitulo o grupo, unir consulta_diagnostico (ambulatoria) "
        "o hospitalario_doctor_diagnostico (internacion) a la jerarquia via codigo_cie10a -> "
        "subgrupo_cie10 -> grupo_cie10 -> cap_cie10."
    )

    train_doc(
        "Todas las tablas incluyen codigo_establecimiento como parte de sus claves. "
        "Este campo identifica el hospital/establecimiento. En la mayoria de los casos, "
        "las consultas pueden omitir el filtro de establecimiento para obtener datos globales, "
        "o unirse a la tabla establecimiento para mostrar el nombre del hospital."
    )

    print()

# =========================================================================
# Question-SQL examples — cross-domain
# =========================================================================

def _populate_examples() -> None:
    """Question-SQL pairs that involve shared tables."""
    print("  Examples: cross-domain question-SQL pairs...")

    train_example(
        "Cuantos pacientes hay registrados en el sistema?",
        "SELECT COUNT(*) AS total_pacientes FROM paciente;"
    )

    train_example(
        "Cuantos medicos activos hay en el sistema?",
        "SELECT COUNT(*) AS total_medicos "
        "FROM profesional pr "
        "JOIN usuario u ON pr.codigo_medico = u.codigo_usuario "
        "WHERE u.estado = '1' AND pr.activo = '1';"
    )

    train_example(
        "Cuantos servicios medicos activos hay?",
        "SELECT COUNT(*) AS total_servicios "
        "FROM servicio WHERE activo = '1';"
    )

    train_example(
        "Listar los establecimientos de salud con su ubicacion",
        "SELECT e.nombre_establecimiento, d.nombre_distrito "
        "FROM establecimiento e "
        "LEFT JOIN distrito d ON e.codigo_distrito = d.codigo_distrito "
        "ORDER BY e.nombre_establecimiento;"
    )

    print()
