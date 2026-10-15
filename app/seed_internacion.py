"""
Seed training for the internacion (inpatient / hospitalization) domain.

Provides DDLs, business documentation, and question-SQL examples for
hospitalario_asignacion and related entities (cama, cama_estado, sala, piso,
edificio, hospitalario_evolucion, hospitalario_medicaciones_soluciones,
hospitalario_doctor_datos_alta, hospitalario_cirugia_procedimiento, ...).
Each train_* call dispatches through the shared sink defined in
seed_training.py; entries land in ChromaDB with source='seed:internacion'
and are rebuilt independently of the ambulatoria seed set.
"""

from seed_training import train_ddl, train_doc, train_example

def populate() -> None:
    """Run every populate step for the internacion seed set."""
    _populate_ddls()
    _populate_docs()
    _populate_examples()

# TODO: for all estado columns try to specify possible values (check dao were table used and maybe check ddl and query one recent rows of db to see values and query all possible values for the table)
# also for all json b columns try to specify the structure of the json (CHECK DAO AND RECENT ROWS OF DB but dao should be more reliable)
# also check the deleted relationships if they are properly explained in current document, also check general docs is ok and that examples are correct( you can compare against dao or even execute some of the queries in the mcp against local db) i only checked properly the ddl since it is the most important one, please make this thorough and propely

# =========================================================================
# DDLs
# =========================================================================

def _populate_ddls() -> None:
    """DDLs for internacion-related tables."""
    print("Adding DDLs for internacion-related tables...")

    # -----------------------------------------------------------------
    # Physical infrastructure: edificio -> piso -> sala -> cama
    # -----------------------------------------------------------------

    train_ddl("""
-- Edificios del hospital. Jerarquia: edificio > piso > sala > cama.
-- Se une a: establecimiento.codigo_establecimiento via codigo_establecimiento
CREATE TABLE public.edificio (
    codigo_establecimiento character varying(16) NOT NULL,  -- hospital
    codigo_edificio character varying(3) NOT NULL,           -- id del edificio dentro del hospital
    nombre_edificio character varying(64) NOT NULL,          -- nombre legible (ej: "Edificio Principal")
    activo character varying(1) NOT NULL,                    -- 'Y'=activo, 'N'=inactivo
    observacion text,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_edificio)
);
    """)

    train_ddl("""
-- Pisos dentro de un edificio.
-- Se une a: edificio via (codigo_establecimiento, codigo_edificio)
CREATE TABLE public.piso (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_edificio character varying(3) NOT NULL,           -- edificio padre
    codigo_piso character varying(4) NOT NULL,               -- id del piso
    nombre_piso character varying(64) NOT NULL,              -- nombre legible (ej: "Planta Baja", "1er Piso")
    activo character varying(1) NOT NULL,                    -- 'Y'=activo, 'N'=inactivo
    observacion text,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_piso)
);
    """)

    train_ddl("""
-- Salas/habitaciones dentro de un piso. Cada sala pertenece a un servicio medico.
-- Se une a: piso via (codigo_establecimiento, codigo_piso)
-- Se une a: edificio via (codigo_establecimiento, codigo_edificio)
-- Se une a: servicio.codigo_servicio via codigo_servicio (servicio medico de la sala)
CREATE TABLE public.sala (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_edificio character varying(3) NOT NULL,
    codigo_piso character varying(4) NOT NULL,
    codigo_sala character varying(4) NOT NULL,               -- id de la sala
    nombre_sala character varying(64) NOT NULL,              -- nombre legible (ej: "Sala A", "UTI Pediatrica")
    tipo_sala character varying(1),                          -- tipo de sala
    codigo_servicio integer NOT NULL,                        -- servicio medico asignado
    activo character varying(1) NOT NULL,                    -- 'Y'=activo, 'N'=inactivo
    observacion text,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_sala)
);
    """)

    train_ddl("""
-- Camas fisicas del hospital. Cada cama pertenece a una sala/piso/edificio.
-- Se une a: sala via (codigo_establecimiento, codigo_sala)
-- Se une a: piso via (codigo_establecimiento, codigo_piso)
-- Se une a: edificio via (codigo_establecimiento, codigo_edificio)
-- Se une a: servicio.codigo_servicio via codigo_servicio
CREATE TABLE public.cama (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_edificio character varying(3) NOT NULL,
    codigo_piso character varying(4) NOT NULL,
    codigo_sala character varying(4) NOT NULL,
    codigo_cama character varying(6) NOT NULL,               -- id de la cama
    nombre_cama character varying(64) NOT NULL,              -- nombre visible (ej: "Cama 101")
    tipo_cama character varying(1),                          -- 'G'=General, 'T'=UTI (terapia intensiva)
    codigo_servicio integer NOT NULL,                        -- servicio medico asignado
    activo character varying(1) NOT NULL,                    -- 'Y'=activo, 'N'=inactivo
    observacion text,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_cama)
);
    """)

    train_ddl("""
-- Estado actual de cada cama. Una fila por cama, se actualiza en tiempo real.
-- Se une a: cama via (codigo_establecimiento, codigo_cama)
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion) cuando la cama esta ocupada
CREATE TABLE public.cama_estado (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_cama character varying(6) NOT NULL,
    estado character varying(1) NOT NULL,        -- '1'=DISPONIBLE, '2'=OCUPADO, '3'=PREPARACION, '4'=AISLADO, '5'=EN_REPARACION
    activo character varying(1) NOT NULL,        -- 'Y'=activo, 'N'=inactivo
    codigo_asignacion character varying(10),     -- si esta ocupada, referencia a la asignacion del paciente internado
    medico_suplente character varying(10),       -- medico suplente asignado a la cama
    observacion text,
    motivo_reparacion text,                      -- motivo cuando estado='5' (en reparacion)
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_cama)
);
    """)

    # -----------------------------------------------------------------
    # Core hospitalization: asignacion, orden
    # -----------------------------------------------------------------

    train_ddl("""
-- TABLA CENTRAL de internacion. Cada fila es una asignacion de un paciente a una cama.
-- Representa una estancia hospitalaria completa: desde la admision hasta el alta.
-- Se une a: paciente.codigo_paciente via codigo_paciente (datos del paciente)
-- Se une a: usuario.codigo_usuario via codigo_medico (medico tratante)
-- Se une a: usuario.codigo_usuario via medico_suplente (medico suplente)
-- Se une a: servicio.codigo_servicio via codigo_servicio (servicio/departamento)
-- Se une a: establecimiento.codigo_establecimiento via codigo_establecimiento (hospital)
-- Se une a: cama via (codigo_establecimiento, codigo_cama)
-- Se une a: sala via (codigo_establecimiento, codigo_sala)
-- Se une a: piso via (codigo_establecimiento, codigo_piso)
-- Se une a: edificio via (codigo_establecimiento, codigo_edificio)
CREATE TABLE public.hospitalario_asignacion (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,        -- identificador unico de la internacion
    orden_asignacion integer NOT NULL DEFAULT 1,             -- orden para re-asignaciones (transferencias de cama); 1=primera asignacion
    codigo_paciente character varying(20) NOT NULL,          -- paciente internado
    tipo_documento character varying(1),                     -- tipo de doc del paciente
    hospitalario_fecha date,                                 -- fecha de ingreso/internacion
    hospitalario_hora time without time zone,                -- hora de ingreso
    codigo_medico character varying(10),                     -- medico tratante
    medico_suplente character varying(10),                   -- medico suplente
    cancelar_hospitalario character varying(1),              -- flag de cancelacion '1'=cancelado
    fecha_cancelar_hospitalario character varying(1),
    hora_cancelar_hospitalario time without time zone,
    estado character varying(1),                             -- 'D'=dado de alta, 'B'=activo/internado, 'C'=cancelado
    primera_consulta_anho character varying(1),
    referido character varying(2),
    serefiere_local character varying(2),
    codigo_servicio integer NOT NULL,                        -- servicio medico asignado
    edad_paciente integer NOT NULL,                          -- edad al momento de la internacion
    tipo_edad integer NOT NULL,                              -- 1=anhos, 2=meses, 3=dias
    cod_departamento_residencia character(2),
    cod_distrito_residencia character(3),
    cod_barrio_residencia character varying(3),
    area character varying(3),
    codigo_edificio character varying(3),                    -- ubicacion fisica
    codigo_piso character varying(4),
    codigo_sala character varying(4),
    codigo_cama character varying(6),
    nombre_cama character varying(64),
    tipo_cama character varying(1),                          -- 'G'=General, 'T'=UTI
    btimestamp character varying(15),
    seguro_medico character varying(8),
    fecha_alta_hospitalario date,                            -- fecha real de alta
    hora_alta_hospitalario time without time zone,           -- hora real de alta
    fin_del_evento character varying(1) DEFAULT '0',         -- '0'=internado activo, '1'=alta/egreso completado
    codigo_hospitalario_orden character varying(10),          -- referencia a la orden de internacion
    fecha_alta_autorizada date,                              -- fecha autorizada para alta
    hora_alta_autorizada time without time zone,
    fin_del_evento_autorizada character varying(1) DEFAULT '0', -- '0'=alta no autorizada aun, '1'=alta autorizada. Se marca '1' cuando el medico autoriza el alta, antes de que se complete el proceso de egreso (fin_del_evento).
    is_outdated boolean NOT NULL DEFAULT false,              -- true si fue reemplazado por otra asignacion (transferencia de cama)
    persona_responsable_telefono character varying(15),
    persona_responsable_codigo character varying(20),
    persona_responsable_nombre character varying(60),
    otro_barrio character varying(40),
    nivel_urgencia smallint,                                 -- nivel de urgencia al ingreso
    re_hospitalizar_en_14_dias boolean,                      -- si es re-internacion dentro de 14 dias
    estado_civil character varying(1),
    ocupacion character varying(4),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden_asignacion)
);
    """)

    # -----------------------------------------------------------------
    # Initial note & clinical assessment
    # -----------------------------------------------------------------

    train_ddl("""
-- Nota inicial del medico para una internacion. Cualquier medico puede crear una nota inicial,
-- no solo el medico tratante. Puede haber multiples notas (medico tratante + interconsultantes).
-- Tabla padre de: hospitalario_doctor_diagnostico, hospitalario_doctor_examen_fisico,
-- hospitalario_doctor_antropometricos, hospitalario_historia_clinica (todas con misma PK).
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: servicio.codigo_servicio via codigo_servicio
-- Se une a: usuario.codigo_usuario via codigo_medico
-- Se une a: hospitalario_pedido_interconsulta via (codigo_establecimiento, codigo_asignacion, codigo_pedido_interconsulta)
CREATE TABLE public.hospitalario_doctor_nota_inicial (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_nota_inicial character varying(10) NOT NULL,       -- secuencial por asignacion
    codigo_pedido_interconsulta character varying(10),        -- null si es medico tratante; llenado si es interconsulta
    codigo_servicio integer NOT NULL,                         -- servicio del medico que escribe
    codigo_medico character varying(10) NOT NULL,             -- medico que escribe la nota
    es_medico_tratante boolean,                               -- true si es el medico tratante principal
    es_interconsulta_medico_tratante boolean,                 -- true si medico tratante responde interconsulta
    estado character varying(1),                              -- 'P'=pendiente, 'F'=finalizado, 'E'=eliminado
    tiempo_finalizar timestamp without time zone,             -- cuando se finalizo la nota
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
);
    """)

    train_ddl("""
-- Diagnosticos CIE-10 registrados en la nota inicial.
-- Tiene 1 diagnostico principal (main) y hasta 15 secundarios (minor_01..15).
-- Se une a: hospitalario_doctor_nota_inicial via (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
-- Se une a: cie10 via (codigo_cie10a_main, codigo_cie10b_main) para el diagnostico principal
CREATE TABLE public.hospitalario_doctor_diagnostico (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_nota_inicial character varying(10) NOT NULL,
    codigo_cie10a_main character varying(3),       -- codigo CIE-10 parte A del diagnostico principal
    codigo_cie10b_main character varying(4),       -- codigo CIE-10 parte B del diagnostico principal
    nombre_cie10_main text,                        -- nombre del diagnostico principal
    nuevo_main character varying(1),               -- 'S'=nuevo diagnostico, 'N'=preexistente
    nota_cie10_main text,                          -- nota/observacion sobre el diagnostico principal
    -- minor_01 a minor_15: diagnosticos secundarios con la misma estructura
    codigo_cie10a_minor_01 character varying(3),
    codigo_cie10b_minor_01 character varying(4),
    nombre_cie10_minor_01 text,
    nuevo_main_minor_01 character varying(1),
    nota_cie10_minor_01 text,
    -- ... (minor_02 a minor_15 con la misma estructura) ...
    analisis_diagnostico text,                     -- analisis narrativo del diagnostico
    notificacion character varying(1),             -- 'S' si requiere notificacion epidemiologica
    plan_trabajo_tratamiento text,                 -- plan de trabajo y tratamiento propuesto
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
);
    """)

    # -----------------------------------------------------------------
    # Evolution (progress notes)
    # -----------------------------------------------------------------

    train_ddl("""
-- Notas de evolucion medica (formato SOAP). Los medicos escriben evoluciones
-- periodicas durante toda la estancia del paciente.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: servicio.codigo_servicio via codigo_servicio (servicio que escribe)
-- Se une a: usuario.codigo_usuario via creacion_usuario (medico que escribe)
CREATE TABLE public.hospitalario_evolucion (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_evolucion integer NOT NULL,                       -- secuencial por asignacion
    tiempo_ejecucion timestamp without time zone,            -- momento en que se escribio la evolucion
    subjetivo text,                                          -- S del SOAP: sintomas referidos por el paciente
    objetivo text,                                           -- O del SOAP: hallazgos objetivos del examen
    analisis text,                                           -- A del SOAP: analisis/valoracion medica
    plan text,                                               -- P del SOAP: plan de tratamiento
    estado character varying(1),                             -- 'A'=finalizado/activo, 'P'=pendiente, 'D'=eliminado
    codigo_servicio integer,                                 -- servicio medico que escribe
    tipo_evolucion tipo_evolucion_enum NOT NULL,             -- 'EVO'=evolucion normal, 'SUS'=suspension de medicamento
    sync_time timestamp with time zone,                      -- timestamp de sincronizacion
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_evolucion)
);
    """)

    # -----------------------------------------------------------------
    # Medications & solutions
    # -----------------------------------------------------------------

    train_ddl("""
-- Medicaciones y soluciones indicadas durante la internacion.
-- Cada fila es una prescripcion individual de un medicamento.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: via_medicine.vme_id via vme_id (via de administracion)
-- Se une a: medicamento via (codigo_establecimiento, codigo_medicamento) (catalogo de medicamentos)
CREATE TABLE public.hospitalario_medicaciones_soluciones (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_medicaciones_soluciones integer NOT NULL,          -- secuencial por asignacion
    codigo_medicamento bigint NOT NULL,                       -- id del medicamento en el catalogo
    nombre_medicamento text NOT NULL,                         -- nombre del medicamento
    forma_farmaceutica text,                                  -- forma farmaceutica (tableta, ampolla, etc.)
    concentracion text,                                       -- concentracion del medicamento
    cantidad_uso integer DEFAULT 0,                           -- cantidad por toma
    tiempo_indefinido boolean NOT NULL DEFAULT false,          -- true si la medicacion es por tiempo indefinido
    vme_id integer NOT NULL,                                  -- via de administracion (FK a via_medicine)
    dosis character varying(10),                              -- dosis prescrita
    fecha_inicio date,                                        -- fecha de inicio
    hora_uso text,                                            -- intervalo entre dosis en horas (ej: '8', '12', '24'). Es un numero como texto, no texto descriptivo.
    dias_uso integer,                                         -- duracion en dias
    indicaciones text,                                        -- instrucciones adicionales
    estado character varying(1),                              -- 'a'=activo, 'd'=descontinuado, 's'=suspendido
    tipo_uso character varying(1),                            -- 'd'=por dia, 'v'=por vez
    segun_necesidad text,                                     -- nota si es segun necesidad (PRN)
    unidad_dosis smallint,                                    -- unidad de la dosis (FK a unidades_recetadas)
    otro_unidad_dosis character varying(32),
    dosis_real integer,
    presentacion text,
    tiempo_ultima_confirmacion timestamp without time zone,   -- timestamp de la ultima confirmacion por el medico tratante
    tiempo_confirmacion_solicitar timestamp without time zone,
    otro_via character varying(10),                           -- via alternativa si vme_id no aplica
    codigo_grupo group_hms NOT NULL,                          -- grupo: 'I'=indicacion simple, 'IP'=indicacion que pertenece a un plan, 'H'=hidratacion, 'N'=nutricion, 'IN'=infusion. Medicamentos con 'IP' se vinculan a hospitalario_medicaciones_planes via hospitalario_medicaciones_planes_soluciones
    hora_inicio time without time zone DEFAULT '00:00:00',
    last_confirmed_timeslot integer NOT NULL,                 -- ultimo timeslot confirmado por enfermeria
    motivo_suspension text,                                   -- razon si fue suspendido
    creacion_fecha date NOT NULL DEFAULT CURRENT_DATE,
    creacion_hora time without time zone NOT NULL DEFAULT CURRENT_TIME,
    creacion_usuario character varying(10) NOT NULL,
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones)
);
    """)

    train_ddl("""
-- Registro de administracion de medicamentos por enfermeria.
-- Cada vez que una enfermera administra un medicamento, se crea un registro.
-- Se une a: hospitalario_medicaciones_soluciones via (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones)
-- Se une a: via_medicine.vme_id via via_forma (via de administracion usada)
CREATE TABLE public.hospitalario_registro_medicacion (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_medicaciones_soluciones integer NOT NULL,          -- medicacion a la que corresponde
    orden integer NOT NULL DEFAULT nextval('hospitalario_registro_medicacion_orden_seq'),
    codigo_medicamento bigint NOT NULL,                       -- id del medicamento
    nombre_medicamento text NOT NULL,                         -- nombre del medicamento
    via_forma integer NOT NULL,                               -- via de administracion (FK a via_medicine)
    frecuencia text,                                          -- frecuencia formateada (ej: 'c/ 8 hs', 'c/ 12 hs')
    tiempo_ejecucion timestamp without time zone NOT NULL,    -- momento exacto de administracion
    observacion text,                                         -- nota de enfermeria
    cantidad integer NOT NULL,                                -- cantidad administrada
    fecha_deduccion date,                                     -- fecha de deduccion de stock
    estado estado_hrm DEFAULT 'A',                            -- 'A'=activo, 'E'=eliminado
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(10) NOT NULL,
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones, orden)
);
    """)

    # NOTE: via_medicine moved to seed_common.py

    # -----------------------------------------------------------------
    # Diet & nursing measures
    # -----------------------------------------------------------------

    train_ddl("""
-- Indicaciones de dieta para el paciente internado.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_indicacion_dieta (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    orden integer NOT NULL DEFAULT nextval('hospitalario_indicacion_dieta_orden_seq'),  -- secuencial
    is_outdated boolean NOT NULL DEFAULT false,              -- true si fue reemplazada por una dieta mas reciente
    dieta text,                                              -- descripcion de la dieta indicada
    estado character varying,                                -- 'a'=activa, 'd'=descontinuada
    creacion_fecha date NOT NULL DEFAULT CURRENT_DATE,
    creacion_hora time without time zone NOT NULL DEFAULT CURRENT_TIME,
    creacion_usuario character varying(10) NOT NULL,
    servicios_historial jsonb,                               -- JSON array: [{"codigo_servicio": N, "nombre_servicio": "..."}]
    dieta_old text,                                          -- valor anterior (para auditoria)
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden)
);
    """)

    train_ddl("""
-- Medidas de enfermeria indicadas por el medico.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_indicacion_medidas (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    orden integer NOT NULL DEFAULT nextval('hospitalario_indicacion_medidas_orden_seq'),
    is_outdated boolean NOT NULL DEFAULT false,              -- true si fue reemplazada por una medida mas reciente
    medidas_enfermeria text,                                 -- descripcion de las medidas indicadas
    estado character varying,                                -- 'a'=activa, 'd'=descontinuada
    creacion_fecha date NOT NULL DEFAULT CURRENT_DATE,
    creacion_hora time without time zone NOT NULL DEFAULT CURRENT_TIME,
    creacion_usuario character varying(10) NOT NULL,
    servicios_historial jsonb,                               -- JSON array: [{"codigo_servicio": N, "nombre_servicio": "..."}]
    medidas_enfermeria_old text,                             -- valor anterior (para auditoria)
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden)
);
    """)

    # -----------------------------------------------------------------
    # Nursing care (NANDA / NOC / NIC)
    # -----------------------------------------------------------------

    train_ddl("""
-- Atencion de enfermeria usando el marco NANDA (diagnosticos de enfermeria).
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: nanda_henderson_diagnostico via (diagnostico, codigo_nanda)
CREATE TABLE public.hospitalario_nursing_atencion_enfermeria (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_enfermeria character varying(10) NOT NULL,        -- secuencial
    tiempo_ejecucion timestamp without time zone,            -- cuando se realizo la valoracion
    valoracion text,                                         -- valoracion narrativa de enfermeria
    diagnostico smallint,                                    -- necesidad Henderson (FK a nanda_henderson_necesidad)
    codigo_nanda character varying(5),                       -- codigo NANDA del diagnostico de enfermeria
    evaluacion text,                                         -- evaluacion/resultado
    activo integer DEFAULT 1,                                -- 1=activo, 0=inactivo
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_enfermeria)
);
    """)

    train_ddl("""
-- Intervenciones NOC (resultados) y NIC (intervenciones) de enfermeria.
-- Cada entrada se vincula a un diagnostico NANDA.
-- Se une a: hospitalario_nursing_atencion_enfermeria via (codigo_establecimiento, codigo_asignacion, codigo_enfermeria)
CREATE TABLE public.hospitalario_nursing_noc_nic (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_enfermeria character varying(10) NOT NULL,
    orden integer NOT NULL,                                  -- secuencial dentro del diagnostico
    typo_enfermeria character varying(3) NOT NULL,           -- 'NOC'=resultado, 'NIC'=intervencion
    codigo_procedimiento character varying(4) NOT NULL,      -- codigo del procedimiento NOC/NIC
    nombre_procedimiento text,                               -- nombre legible
    nota text,                                               -- nota adicional
    activo integer,                                          -- 1=activo, 0=inactivo
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_enfermeria, orden)
);
    """)

    # -----------------------------------------------------------------
    # Interconsultation
    # -----------------------------------------------------------------

    train_ddl("""
-- Pedidos de interconsulta: solicitud de opinion de otro servicio/especialista.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: usuario.codigo_usuario via pedido_codigo_medico (medico solicitante)
-- Se une a: usuario.codigo_usuario via codigo_asignar_medico (medico asignado)
-- Se une a: usuario.codigo_usuario via codigo_recibir_medico (medico que recibe)
-- Se une a: servicio.codigo_servicio via codigo_servicio (servicio destino)
CREATE TABLE public.hospitalario_pedido_interconsulta (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_pedido_interconsulta character varying(10) NOT NULL,
    pedido_codigo_medico character varying(10),              -- medico que solicita
    pedido_interconsulta_fecha date,
    pedido_interconsulta_hora time without time zone,
    codigo_servicio integer NOT NULL,                        -- servicio destino de la interconsulta
    codigo_asignar_medico character varying(10),             -- medico asignado para responder
    motivo text,                                             -- motivo de la interconsulta
    estado character varying(1),                             -- 'u'=pendiente, 'h'=en proceso, 'c'=finalizado, 'd'=eliminado
    codigo_recibir_medico character varying(10),             -- medico que recibe/responde
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_pedido_interconsulta)
);
    """)

    # -----------------------------------------------------------------
    # Surgery
    # -----------------------------------------------------------------

    train_ddl("""
-- Procedimientos quirurgicos realizados durante la internacion.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_cirugia_procedimiento (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    orden_cirugia integer NOT NULL DEFAULT 1,                -- secuencial si hubo multiples cirugias
    codigo_cirugia_procedimiento smallint,
    tiempo_ejecucion timestamp without time zone NOT NULL,   -- momento de la cirugia
    diagnostico_preoperatorio text,                          -- diagnostico antes de operar
    diagnostico_posoperatorio text,                          -- diagnostico despues de operar
    cirugia_realizada text,                                  -- descripcion de la cirugia
    descripcion text,                                        -- descripcion detallada del procedimiento
    complicaciones text,                                     -- complicaciones durante la cirugia
    perdida_estimada_sangre smallint,                        -- ml de sangre perdidos
    muestra text,                                            -- muestras enviadas a patologia
    cirujano jsonb,                                          -- JSON array: [{"codigo_medico": "...", "nombre_medico": "..."}]
    ayudante jsonb,                                          -- JSON array: [{"codigo_medico": "...", "nombre_medico": "..."}]
    anestesista jsonb,                                       -- JSON array: [{"codigo_medico": "...", "nombre_medico": "..."}]
    tiempo_total_cirugia integer,                            -- duracion total en minutos
    tipo_anestesia text,                                     -- tipo de anestesia usada
    tiempo_anestesia integer,                                -- duracion de la anestesia en minutos
    tipo_cirugia smallint,                                   -- tipo de cirugia (electiva, urgencia, etc.)
    rcp_minutos integer,                                     -- minutos de RCP si aplico
    estado character varying(1),                             -- 'A'=finalizado, 'P'=pendiente, 'D'=eliminado
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(15),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(15),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden_cirugia)
);
    """)

    # -----------------------------------------------------------------
    # Transfers
    # -----------------------------------------------------------------

    train_ddl("""
-- Solicitudes de transferencia de cama o servicio durante la internacion.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: servicio.codigo_servicio via codigo_servicio_solicitado (servicio origen)
-- Se une a: servicio.codigo_servicio via codigo_servicio_recommendado (servicio destino)
-- Se une a: cama via (codigo_establecimiento, codigo_cama_recommendado) (cama destino)
-- Se une a: usuario.codigo_usuario via codigo_medico_solicitado (medico que solicita)
-- Se une a: usuario.codigo_usuario via codigo_medico_recommendado (medico que recomienda)
CREATE TABLE public.hospitalario_gestion_solicitar_transferencia (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_solicitud_transferencia character varying(10) NOT NULL,
    tiempo_solicitar_transferencia timestamp without time zone NOT NULL,
    codigo_servicio_solicitado integer NOT NULL,              -- servicio que solicita la transferencia
    codigo_medico_solicitado character varying(10),           -- medico solicitante
    tipo_transferencia character varying(1),                  -- tipo de transferencia
    codigo_servicio_recommendado integer NOT NULL,            -- servicio destino recomendado
    codigo_edificio_recommendado character varying(3),
    codigo_piso_recommendado character varying(4),
    codigo_sala_recommendado character varying(4),
    codigo_cama_recommendado character varying(4),
    codigo_medico_recommendado character varying(10),
    estado character varying(1),                             -- 'p'=pendiente, 'f'=finalizado, 'e'=eliminado
    motivo text,                                             -- motivo de la transferencia
    resultado_proceso text,                                  -- resultado/resolucion
    codigo_servicio_original integer,                        -- servicio original antes de la transferencia
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_solicitud_transferencia)
);
    """)

    # -----------------------------------------------------------------
    # Discharge
    # -----------------------------------------------------------------

    train_ddl("""
-- Datos de alta medica. Se llena al momento del egreso del paciente.
-- Contiene diagnosticos de egreso (1 principal + hasta 15 secundarios), resumen y recomendaciones.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: condicion_egreso via condicion_egreso (1=curado, 2=mejorado, 3=estacionario, 4=empeorado, 5=fallecido)
-- Se une a: tipo_egreso via tipo_egreso (1=alta medica, 2=traslado, 3=retiro voluntario, 4=fuga, 5=defuncion, 10=rechazo)
-- Se une a: servicio.codigo_servicio via servicio_proxima_consulta
-- Se une a: cie10 via (codigo_cie10a_main, codigo_cie10b_main) para el diagnostico principal de egreso
CREATE TABLE public.hospitalario_doctor_datos_alta (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    fecha_ingreso date NOT NULL,                             -- fecha de ingreso al hospital
    fecha_egreso date NOT NULL,                              -- fecha de egreso/alta
    condicion_egreso character varying(1),                   -- condicion al egreso (1-5, ver condicion_egreso)
    tipo_egreso character varying(1),                        -- tipo de egreso (1-5,10, ver tipo_egreso)
    -- diagnostico principal de egreso
    codigo_cie10a_main character varying(3),
    codigo_cie10b_main character varying(4),
    nombre_cie10_main text,
    nota_cie10_main text,
    -- diagnosticos secundarios de egreso (otros_01 a otros_15, misma estructura)
    codigo_cie10a_otros_01 character varying(3),
    codigo_cie10b_otros_01 character varying(4),
    nombre_cie10_otros_01 text,
    nota_cie10_otros_01 text,
    -- ... (otros_02 a otros_15 con la misma estructura) ...
    resumen_evolutivo text,                                  -- resumen de la evolucion durante la estancia
    signo_vital_egreso text,                                 -- signos vitales al momento del egreso
    examen_fisico_egreso text,                               -- examen fisico al egreso
    otra_recomendacion text,                                 -- recomendaciones adicionales
    fecha_proxima_consulta date,                             -- fecha de control post-alta
    servicio_proxima_consulta integer,                       -- servicio para el control
    dieta_alta text,                                         -- dieta indicada al alta
    instruccion_alta text,                                   -- instrucciones al alta
    orden_alta character varying(1),                         -- indica si se dio orden de alta
    orden_transferir text,                                   -- si es traslado, detalles del destino
    estado character varying(1),                             -- 'f'=finalizado, 'p'=pendiente
    is_delivery character varying(1),                        -- 'S' si fue parto/cesarea
    causas_externas character varying(1),                    -- 'S' si hubo causas externas
    sitio_ocurrencia character varying(1),                   -- sitio donde ocurrio el evento
    motivo_reversion text,                                   -- motivo si se revierte el alta
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion)
);
    """)

    # -----------------------------------------------------------------
    # Reference / lookup tables
    # -----------------------------------------------------------------

    train_ddl("""
-- Tipo de egreso hospitalario (tabla de referencia).
-- Referenciada por: hospitalario_doctor_datos_alta.tipo_egreso
CREATE TABLE public.tipo_egreso (
    teg_id serial NOT NULL PRIMARY KEY,   -- 1=ALTA MEDICA, 2=TRASLADO A OTRO ESTABLECIMIENTO, 3=RETIRO VOLUNTARIO,
                                          -- 4=FUGA, 5=DEFUNCION, 10=RECHAZO DE HOSPITALIZACION
    teg_des text                          -- descripcion del tipo
);
    """)

    # -----------------------------------------------------------------
    # Initial note children: antropometricos, examen fisico, historia clinica
    # -----------------------------------------------------------------

    train_ddl("""
-- Signos vitales y medidas antropometricas registrados por el medico en la nota inicial.
-- Se une a: hospitalario_doctor_nota_inicial via (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_doctor_antropometricos (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_nota_inicial character varying(10) NOT NULL,
    temperatura_axilar numeric(3,1),               -- temperatura axilar en grados Celsius
    der_presion_arterial_sis numeric,              -- presion arterial sistolica brazo derecho (mmHg)
    der_presion_arterial_dias numeric,             -- presion arterial diastolica brazo derecho (mmHg)
    izq_presion_arterial_sis numeric,              -- presion arterial sistolica brazo izquierdo
    izq_presion_arterial_dias numeric,             -- presion arterial diastolica brazo izquierdo
    saturacion_oxigeno integer,                    -- SpO2 en porcentaje
    frecuencia_cardiaca numeric,                   -- latidos por minuto
    frecuencia_respiratoria numeric,               -- respiraciones por minuto
    pulso numeric,                                 -- pulso por minuto
    perimetro_cefalico numeric,                    -- perimetro cefalico en cm (pediatria)
    perimetro_cefalico_percentil text,             -- percentil del perimetro cefalico
    peso numeric(4,1),                             -- peso en kg
    peso_percentil text,                           -- percentil del peso
    talla numeric(4,1),                            -- talla en cm
    talla_percentil text,                          -- percentil de la talla
    indice_masa_corporal numeric(4,2),             -- IMC calculado
    indice_masa_corporal_percentil text,           -- percentil del IMC
    circunferencia_abdominal numeric(4,1),         -- circunferencia abdominal en cm
    fum date,                                      -- fecha de ultima menstruacion
    embarazada boolean,                            -- true si la paciente esta embarazada
    semana_gestacion integer,                      -- semanas de gestacion si embarazada
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
);
    """)

    train_ddl("""
-- Examen fisico por sistema registrado por el medico en la nota inicial.
-- Cada campo es una nota narrativa sobre un sistema corporal.
-- Se une a: hospitalario_doctor_nota_inicial via (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_doctor_examen_fisico (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_nota_inicial character varying(10) NOT NULL,
    nota_aspecto_general text,                     -- aspecto general del paciente
    nota_cabeza text,                              -- hallazgos en cabeza
    nota_cuello text,                              -- hallazgos en cuello
    nota_torax text,                               -- hallazgos en torax
    nota_respiratorio text,                        -- sistema respiratorio
    nota_cardiovascular text,                      -- sistema cardiovascular
    nota_abdomen text,                             -- hallazgos abdominales
    nota_genito_urinario text,                     -- sistema genito-urinario
    nota_musculoesqueletico text,                  -- sistema musculoesqueletico
    nota_piel_faneras text,                        -- piel y faneras
    nota_hemolinfopoyetico text,                   -- sistema hemolinfopoyetico
    nota_neurologico text,                         -- sistema neurologico
    nota_psiquiatrico text,                        -- evaluacion psiquiatrica
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
);
    """)

    train_ddl("""
-- Historia clinica completa registrada en la nota inicial del medico.
-- Contiene antecedentes, alergias, medicamentos en uso, inmunizaciones.
-- Se une a: hospitalario_doctor_nota_inicial via (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_historia_clinica (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_nota_inicial character varying(10) NOT NULL,
    tiempo_ejecucion timestamp without time zone,  -- cuando se registro la historia
    motivo_consulta text,                          -- motivo de consulta / ingreso
    historia_actual text,                          -- enfermedad actual / historia presente
    antecedentes_medicos text,                     -- antecedentes patologicos medicos
    antecedentes_quirurgicos text,                 -- antecedentes quirurgicos
    antecedentes_neonatales text,                  -- antecedentes neonatales (pediatria)
    antecedentes_familiares text,                  -- antecedentes familiares
    historia_social text,                          -- historia social del paciente
    habitos_exposiciones text,                     -- habitos y exposiciones (tabaco, alcohol, etc.)
    alergias text,                                 -- alergias conocidas
    medicamentos_uso text,                         -- medicamentos que usa actualmente
    inmunizaciones text,                           -- estado de inmunizaciones
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)
);
    """)

    # -----------------------------------------------------------------
    # Nursing vitals
    # -----------------------------------------------------------------

    train_ddl("""
-- Signos vitales y medidas antropometricas registrados por enfermeria.
-- Similar a hospitalario_doctor_antropometricos pero una sola fila por asignacion.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_nursing_antropometricos (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    temperatura_axilar numeric(3,1),
    der_presion_arterial_sis numeric,
    der_presion_arterial_dias numeric,
    izq_presion_arterial_sis numeric,
    izq_presion_arterial_dias numeric,
    frecuencia_cardiaca numeric,
    frecuencia_respiratoria numeric,
    pulso numeric,
    perimetro_cefalico numeric,
    perimetro_cefalico_percentil text,
    peso numeric(4,1),
    peso_percentil text,
    talla numeric(4,1),
    talla_percentil text,
    indice_masa_corporal numeric(4,2),
    indice_masa_corporal_percentil text,
    circunferencia_abdominal numeric(4,1),
    saturacion_oxigeno integer,
    fum date,
    embarazada boolean,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion)
);
    """)

    # -----------------------------------------------------------------
    # Panoramic nursing
    # -----------------------------------------------------------------

    train_ddl("""
-- Hoja de monitoreo diario de enfermeria (panoramica). Cada fila es un item
-- de control (ej: signos vitales, balance hidrico) con su valor y timestamp.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_panoramica_enfermeria (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    orden integer NOT NULL,                        -- secuencial por asignacion
    tiempo_ejecucion timestamp without time zone,  -- momento del registro
    codigo_item_examination character varying(6) NOT NULL,  -- codigo del item de control
    valor text,                                    -- valor registrado para el item
    estado character varying(1),                   -- 'A'=activo, 'D'=eliminado
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden, codigo_item_examination)
);
    """)

    # -----------------------------------------------------------------
    # Medication plans (IV drip / infusion plans)
    # -----------------------------------------------------------------

    train_ddl("""
-- Medicamentos recetados al alta (para llevar a casa).
-- Estructura similar a hospitalario_medicaciones_soluciones pero para el alta.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: via_medicine.vme_id via vme_id
CREATE TABLE public.hospitalario_medicaciones_alta (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_medicaciones_soluciones integer NOT NULL,
    codigo_medicamento bigint NOT NULL,             -- id del medicamento
    nombre_medicamento text,                        -- nombre del medicamento
    forma_farmaceutica text,
    concentracion text,
    cantidad_uso integer,
    tiempo_indefinido boolean DEFAULT false,
    vme_id integer,                                 -- via de administracion (FK a via_medicine)
    dosis character varying(10),
    fecha_inicio date,
    hora_uso text,
    dias_uso integer,
    tipo_uso character varying(1),
    indicaciones text,
    estado character varying(1),                    -- 'p'=pendiente, 'f'=finalizado, 'd'=eliminado
    unidad_dosis smallint,
    otro_unidad_dosis character varying(32),
    dosis_real integer,
    otro_via character varying(10),
    creacion_fecha date NOT NULL DEFAULT CURRENT_DATE,
    creacion_hora time without time zone NOT NULL DEFAULT CURRENT_TIME,
    creacion_usuario character varying(10) NOT NULL,
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones)
);
    """)

    # -----------------------------------------------------------------
    # Staffing: professional-service assignments
    # -----------------------------------------------------------------

    train_ddl("""
-- Asignacion de profesionales (medicos/enfermeros) a servicios hospitalarios.
-- Se une a: servicio.codigo_servicio via codigo_servicio
-- Se une a: usuario.codigo_usuario via codigo_usuario
CREATE TABLE public.hospitalario_profesional_servicio (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_servicio integer NOT NULL,              -- servicio al que se asigna
    codigo_usuario character varying(10) NOT NULL,  -- profesional asignado
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_servicio, codigo_usuario)
);
    """)

    train_ddl("""
-- Profesionales responsables por servicio (jefe de servicio, encargado).
-- Se une a: servicio.codigo_servicio via codigo_servicio
-- Se une a: usuario.codigo_usuario via codigo_usuario
CREATE TABLE public.hospitalario_profesional_responsable (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_servicio integer NOT NULL,
    codigo_usuario character varying(10) NOT NULL,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_servicio, codigo_usuario)
);
    """)

    # -----------------------------------------------------------------
    # Studies & procedures
    # -----------------------------------------------------------------

    train_ddl("""
-- Ordenes de estudios complementarios (laboratorio, imagenes, etc.) durante la internacion.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_estudios_complementarios (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_estudios_complementarios character varying(10) NOT NULL,
    codigo_grupo_examen_estudio character varying(1) NOT NULL,  -- grupo del estudio (ej: 'L'=lab, 'I'=imagen)
    codigo_item_examen_estudio character varying(10) NOT NULL,  -- item especifico del estudio
    fecha_inicio date,                             -- fecha solicitada
    hora_inicio time without time zone,
    tipo_vez character varying(1) NOT NULL,        -- tipo de vez
    hora_uso text,                                 -- frecuencia
    por_uso integer,                               -- cantidad por uso
    tipo_uso character varying(1),                 -- tipo de uso
    nota text,                                     -- nota/instrucciones
    orden integer NOT NULL,                        -- orden secuencial
    estado character varying(1),                   -- 'u'=pendiente/uso, 'd'=eliminado
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_estudios_complementarios)
);
    """)

    train_ddl("""
-- Procedimientos medicos realizados durante la internacion (no quirurgicos).
-- Usa codigos CIE-9 para procedimientos. Tiene un campo JSONB para valores detallados.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_procedimiento (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    orden integer NOT NULL,                        -- secuencial por asignacion
    codigo_procedimiento character varying(9) NOT NULL,  -- codigo CIE-9 del procedimiento
    nombre_procedimiento character varying(120),   -- nombre del procedimiento
    nota text,                                     -- nota adicional
    valor_procedimiento jsonb,                     -- JSON array: [{"valor": "...", "estado": "f/p/d", "sub_orden": N}]
    estado character varying(1),                  -- 'f'=finalizado, 'p'=pendiente, 'd'=eliminado
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden)
);
    """)

    # -----------------------------------------------------------------
    # Obstetric
    # -----------------------------------------------------------------

    train_ddl("""
-- Datos obstetricos del alta. Resumen de la informacion obstetrica al momento del egreso.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: hospitalario_cirugia_obstetrico via (codigo_establecimiento, codigo_asignacion, orden_cirugia)
CREATE TABLE public.hospitalario_obstetrico_alta (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    orden_cirugia smallint NOT NULL,
    numero_gestacion integer,
    numero_partos integer,
    numero_abortos integer,
    numero_controles_prenatales integer,
    info_prenatal_antes_4to_mes character varying(1),
    info_prenatal_4to_mes_y_mas character varying(1),
    tipo_nacimiento character varying(1),
    tipo_parto character varying(1),
    tipo_profesional jsonb,                        -- tipo de profesional que atendio
    profesional jsonb,                             -- datos del profesional
    datos_recien_nacido jsonb,                     -- datos resumen del recien nacido
    estado character varying(1),                   -- 'f'=finalizado, 'p'=pendiente, 'c'=cancelado, 'd'=eliminado
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden_cirugia)
);
    """)

    # -----------------------------------------------------------------
    # Trauma discharge
    # -----------------------------------------------------------------

    train_ddl("""
-- Datos de alta de trauma. Solo se crea para pacientes con causas externas (trauma).
-- No tiene columna estado; usa is_outdated para versionar.
-- Registro detallado de causas externas, mecanismos de lesion,
-- tipo de accidente, elementos de seguridad, agresiones, envenenamiento, quemaduras.
-- is_outdated=true marca versiones anteriores; filtrar por is_outdated=false para vigente.
-- Se une a: hospitalario_doctor_datos_alta via (codigo_establecimiento, codigo_asignacion) (tabla padre de alta)
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_alta_trauma (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    version_alta_trauma integer NOT NULL,          -- version para historial
    is_outdated boolean NOT NULL,                  -- true si fue reemplazado por version mas reciente
    motivo_consulta smallint,                      -- motivo de consulta codificado
    lugar_del_evento smallint,                     -- lugar donde ocurrio el evento
    lugar_del_evento_otros character varying(50),
    escala_glasgow smallint,                       -- puntaje Glasgow (3-15)
    tipo_accidente smallint,                       -- tipo de accidente
    tipo_accidente_otros character varying(50),
    accidentado smallint,                          -- rol del accidentado
    accidentado_otros character varying(50),
    tipo_transporte smallint,
    tipo_transporte_otros character varying(50),
    -- Elementos de seguridad
    elemento_de_seguridad_cinturon boolean,
    elemento_de_seguridad_airbag boolean,
    elemento_de_seguridad_casco boolean,
    elemento_de_seguridad_silla_bebe boolean,
    elemento_de_seguridad_otros character varying(50),
    extricacion boolean,
    extricacion_descripcion character varying(50),
    contraparte smallint,
    contraparte_otros character varying(50),
    -- Caida
    caida smallint,
    caida_otros character varying(50),
    caida_metros integer,                          -- altura de la caida en metros
    caida_centimetros integer,                     -- altura de la caida en centimetros
    caida_comentarios character varying(50),
    -- Agresion
    tipo_agresion smallint,
    tipo_agresion_otros character varying(50),
    sexo_del_agresor smallint,
    antecedente_previo_agresion smallint,
    relacion_con_agresor smallint,
    contexto smallint,
    contexto_otros character varying(50),
    lesion_con smallint,
    lesion_con_otros character varying(50),
    antecedente_previo_lesion smallint,
    -- Envenenamiento
    envenenamiento smallint,
    envenenamiento_otros character varying(50),
    envenenamiento_accidental smallint,
    envenenamiento_accidental_otros character varying(50),
    factor_precipitante smallint,
    factor_precipitante_otros character varying(50),
    -- Quemaduras y otros
    quemadura smallint,
    quemaduras_otros character varying(50),
    picaduras_mordeduras smallint,
    picaduras_mordeduras_otros character varying(50),
    otros_mecanismos character varying(50),
    otros_mecanismos_observaciones character varying(50),
    alta_trauma_case_ambulatoria smallint NOT NULL DEFAULT 0, -- 0=hospitalario, 1=ambulatoria
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, version_alta_trauma)
);
    """)

    train_ddl("""
-- Causas externas CIE-10 asociadas al alta de trauma.
-- Se une a: hospitalario_alta_trauma via (codigo_establecimiento, codigo_asignacion, version_alta_trauma)
CREATE TABLE public.hospitalario_alta_trauma_causa (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    version_alta_trauma integer NOT NULL,
    orden integer NOT NULL,                        -- secuencial
    is_outdated boolean NOT NULL,
    codigo_cie10a character varying(3),            -- codigo CIE-10 parte A de causa externa
    codigo_cie10b character varying(4),            -- codigo CIE-10 parte B
    nombre_cie10 text,                             -- nombre de la causa externa
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, version_alta_trauma, orden)
);
    """)

    # -----------------------------------------------------------------
    # Order link
    # -----------------------------------------------------------------

    train_ddl("""
-- Tabla puente que vincula una asignacion (codigo_asignacion) con su orden (codigo_hospitalario_orden).
-- Tiene muchas mas filas que hospitalario_orden_internacion porque la mayoria de ordenes vienen del sistema ambulatoria.
-- Estructura similar a hospitalario_orden_internacion pero indexada por asignacion.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: hospitalario_orden_internacion via (codigo_establecimiento, codigo_hospitalario_orden)
CREATE TABLE public.hospitalario_orden (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_hospitalario_orden character varying(10) NOT NULL,
    pedido_fecha date,
    internacion_fecha date,
    tipo_especialidad integer,
    otro_especialidad character varying(3),
    doctor_servicio integer NOT NULL,              -- servicio del medico
    motivo_internacion text,
    tratamientos text,
    cirugia character varying(1) NOT NULL,         -- 'Y'=requiere cirugia
    codigo_procedimiento character varying(9),
    nombre_procedimiento character varying(120),
    citar_opciones character varying(128),
    codigo_servicio integer,
    codigo_edificio character varying(3),
    codigo_piso character varying(4),
    codigo_sala character varying(4),
    codigo_cama character varying(4),
    nombre_cama character varying(64),
    nombre_persona_responsable text,
    tipo_vinculo integer,
    otro_vinculo smallint,
    codigo_persona_responsable character varying(20),
    tipo_documento_persona_responsable character varying(1),
    codigo_admisionista character varying(10),
    admisionista_fecha date,
    admisionista_hora time without time zone,
    tipo_cama character varying(1),
    codigo_servicio_destino integer,
    estado character varying(1) DEFAULT 'A',
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_hospitalario_orden)
);
    """)

    # -----------------------------------------------------------------
    # Pharmacy / dispensation
    # -----------------------------------------------------------------

    train_ddl("""
-- Formulario de solicitud de medicamentos a farmacia (cabecera).
-- Creado por enfermeria: las enfermeras generan la solicitud de medicamentos que luego es procesada por farmacia.
-- Una solicitud puede abarcar multiples pacientes/medicamentos.
-- Se une a: usuario.codigo_usuario via codigo_enfermera (enfermera que solicita)
-- Se une a: servicio via codigo_servicio (servicios que solicitan, es un array)
CREATE TABLE public.hospitalario_formulario_solicitud_medicamentos (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_solicitud_medicamentos character varying(10) NOT NULL,
    codigo_enfermera character varying(10) NOT NULL, -- enfermera que genera la solicitud
    codigo_servicio integer[] NOT NULL,             -- servicios que solicitan (array)
    estado estado_solicitud_medicamentos,           -- 'Preparando', 'En Proceso', 'Completo'
    creacion_fecha date NOT NULL DEFAULT CURRENT_DATE,
    creacion_hora time without time zone NOT NULL DEFAULT CURRENT_TIME,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_solicitud_medicamentos)
);
    """)

    train_ddl("""
-- Detalle por paciente de una solicitud de medicamentos a farmacia.
-- Se une a: hospitalario_formulario_solicitud_medicamentos via (codigo_establecimiento, codigo_solicitud_medicamentos)
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: hospitalario_medicaciones_soluciones via (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones)
CREATE TABLE public.hospitalario_solicitud_medicamentos_detail (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_medicaciones_soluciones integer NOT NULL,
    solicitud_fecha date NOT NULL,                 -- fecha de la solicitud
    codigo_solicitud_medicamentos character varying(10) NOT NULL,
    codigo_medicamento bigint NOT NULL,
    nombre_medicamento text,
    cantidad_dispensada integer NOT NULL DEFAULT 0, -- cantidad dispensada por farmacia
    numero_total integer,                          -- cantidad total solicitada
    estado estado_solicitud_medicamentos,           -- 'Preparando', 'En Proceso', 'Completo'
    tipo_recurso character varying(2) NOT NULL,    -- tipo de recurso solicitado
    creacion_fecha date NOT NULL DEFAULT CURRENT_DATE,
    creacion_hora time without time zone NOT NULL DEFAULT CURRENT_TIME,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones, solicitud_fecha, tipo_recurso)
);
    """)

    train_ddl("""
-- Registro de medicamentos dispensados por farmacia.
-- Cada fila es una transaccion de entrega de medicamento a un paciente internado.
-- Se sincroniza con el sistema gubernamental SICIAP de farmacia via un job programado. El campo estado rastrea el estado de sincronizacion.
-- Se une a: hospitalario_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: hospitalario_medicaciones_soluciones via (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones)
-- Se une a: hospitalario_formulario_solicitud_medicamentos via (codigo_establecimiento, codigo_solicitud_medicamentos)
CREATE TABLE public.hospitalario_registro_dispensadas (
    codigo_transaccion integer NOT NULL DEFAULT nextval('hospitalario_registro_dispensadas_codigo_transaccion_seq'),
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_medicaciones_soluciones integer NOT NULL,
    solicitud_fecha date,
    codigo_solicitud_medicamentos character varying(10) NOT NULL,
    codigo_medicamento integer NOT NULL,
    cantidad_dispensada integer NOT NULL,           -- cantidad entregada
    estado text,                                   -- NULL=pendiente, 'HIS LOCAL FARMACIA'=local, 'SINCRONIZADO'=sincronizado con SICIAP, 'NO PROCESADO'=error
    codigo_consumo text,                           -- codigo de consumo en farmacia
    codigo_sucursal character varying(10),          -- sucursal de farmacia
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_transaccion, codigo_establecimiento)
);
    """)

    # -----------------------------------------------------------------
    # NANDA Henderson nursing taxonomy (reference tables)
    # -----------------------------------------------------------------

    # -----------------------------------------------------------------
    # Audit tables (DDL only, lighter documentation)
    # -----------------------------------------------------------------

    train_ddl("""
-- Auditoria de datos de alta medica. Cada version previa se almacena aqui.
-- Se une a: hospitalario_doctor_datos_alta via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.hospitalario_doctor_datos_alta_auditoria (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    version_alta integer NOT NULL,                 -- version de la auditoria
    fecha_ingreso date NOT NULL,
    fecha_egreso date NOT NULL,
    condicion_egreso character varying(1),
    tipo_egreso character varying(1),
    codigo_cie10a_main character varying(3),
    codigo_cie10b_main character varying(4),
    nombre_cie10_main text,
    nota_cie10_main text,
    -- diagnosticos secundarios (otros_01 a otros_15, misma estructura)
    codigo_cie10a_otros_01 character varying(3),
    codigo_cie10b_otros_01 character varying(4),
    nombre_cie10_otros_01 text,
    nota_cie10_otros_01 text,
    -- ... (otros_02 a otros_15 con la misma estructura) ...
    resumen_evolutivo text,
    signo_vital_egreso text,
    examen_fisico_egreso text,
    otra_recomendacion text,
    fecha_proxima_consulta date,
    servicio_proxima_consulta integer,
    dieta_alta text,
    instruccion_alta text,
    orden_alta character varying(1),
    orden_transferir text,
    estado character varying(1),
    is_delivery character varying(1),
    causas_externas character varying(1),
    sitio_ocurrencia character varying(1),
    motivo_reversion text,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, version_alta)
);
    """)

    train_ddl("""
-- Auditoria de medicaciones/soluciones. Cada cambio genera una nueva version.
-- Se une a: hospitalario_medicaciones_soluciones via (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones)
CREATE TABLE public.hospitalario_medicaciones_soluciones_auditoria (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_medicaciones_soluciones integer NOT NULL,
    version integer NOT NULL,                      -- version de la auditoria
    codigo_medicamento bigint NOT NULL,
    nombre_medicamento text NOT NULL,
    forma_farmaceutica text,
    concentracion text,
    cantidad_uso integer DEFAULT 0,
    tiempo_indefinido boolean NOT NULL DEFAULT false,
    vme_id integer NOT NULL,
    dosis character varying(10),
    fecha_inicio date,
    hora_uso text,
    dias_uso integer,
    indicaciones text,
    estado character varying(1),
    tipo_uso character varying(1),
    segun_necesidad text,
    unidad_dosis smallint,
    otro_unidad_dosis character varying(32),
    dosis_real integer,
    presentacion text,
    tiempo_ultima_confirmacion timestamp without time zone,
    tiempo_confirmacion_solicitar timestamp without time zone,
    otro_via character varying(10),
    codigo_grupo group_hms NOT NULL,
    hora_inicio time without time zone,
    last_confirmed_timeslot integer NOT NULL,
    motivo_suspension text,
    creacion_fecha date NOT NULL DEFAULT CURRENT_DATE,
    creacion_hora time without time zone NOT NULL DEFAULT CURRENT_TIME,
    creacion_usuario character varying(10) NOT NULL,
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_medicaciones_soluciones, version)
);
    """)

# =========================================================================
# Business documentation
# =========================================================================

def _populate_docs() -> None:
    """Business documentation for the internacion domain."""
    print("Adding documentation for internacion domain...")

    train_doc(
        "Este dominio cubre la internacion (hospitalizacion) de pacientes. "
        "La tabla central es hospitalario_asignacion que representa una estancia "
        "hospitalaria: un paciente asignado a una cama en un servicio medico. "
        "Todas las tablas hospitalario_* se unen a ella via (codigo_establecimiento, codigo_asignacion). "
        "El campo fin_del_evento='0' indica paciente actualmente internado; "
        "fin_del_evento='1' indica que ya fue dado de alta o egresado."
    )

    train_doc(
        "REGLA CRITICA PARA FILTRAR PACIENTES INTERNADOS ACTIVOS: "
        "siempre usar fin_del_evento = '0' AND is_outdated = false en hospitalario_asignacion. "
        "fin_del_evento = '0' significa internado activo; '1' significa alta/egreso completado. "
        "is_outdated = false significa asignacion vigente; true significa reemplazada por transferencia de cama. "
        "Omitir is_outdated duplica pacientes transferidos. "
        "Para filtrar cancelados agregar: cancelar_hospitalario IS DISTINCT FROM 'S'."
    )

    train_doc(
        "La tabla hospitalario_asignacion es la tabla central de internacion. "
        "Cada fila representa una asignacion de un paciente a una cama. "
        "Si un paciente es transferido de cama, se crea un nuevo registro con "
        "orden_asignacion incrementado y el anterior se marca con is_outdated=true. "
        "Para obtener la asignacion vigente, filtrar por is_outdated = false. "
        "Para saber si el paciente sigue internado, verificar fin_del_evento = '0'. "
        "Para contar internaciones activas, usar: fin_del_evento = '0' AND is_outdated = false. "
        "El campo hospitalario_fecha es la fecha de ingreso. "
        "El campo fecha_alta_hospitalario es la fecha real de alta (NULL si sigue internado). "
        "codigo_medico contiene el medico tratante. "
        "tipo_cama: 'G'=general, 'T'=UTI/terapia intensiva. "
        "tipo_edad: 1=anhos, 2=meses, 3=dias."
    )

    train_doc(
        "La infraestructura fisica de camas sigue la jerarquia: "
        "edificio > piso > sala > cama. Todas scoped a codigo_establecimiento. "
        "Para obtener la ubicacion completa de una cama: "
        "JOIN cama c ON ... JOIN sala s ON c.codigo_establecimiento = s.codigo_establecimiento "
        "AND c.codigo_sala = s.codigo_sala JOIN piso p ON ... AND c.codigo_piso = p.codigo_piso "
        "JOIN edificio e ON ... AND c.codigo_edificio = e.codigo_edificio."
    )

    train_doc(
        "La tabla cama_estado contiene el estado actual de cada cama en tiempo real. "
        "Los valores de estado son: "
        "'1' = DISPONIBLE (cama libre, puede recibir paciente), "
        "'2' = OCUPADO (paciente internado, codigo_asignacion indica quien), "
        "'3' = PREPARACION (siendo preparada para nuevo paciente), "
        "'4' = AISLADO (aislamiento por infeccion u otra razon), "
        "'5' = EN_REPARACION (fuera de servicio, motivo_reparacion explica por que). "
        "Para el censo de camas (ocupacion), contar camas agrupadas por estado. "
        "Para camas disponibles: estado = '1' AND activo = 'Y'."
    )

    train_doc(
        "REGLA CRITICA — REGISTROS PENDIENTES: varias tablas de internacion tienen un campo 'estado' "
        "que indica si el registro fue finalizado por el medico. Los registros pendientes NO deben "
        "contarse como datos reales — son borradores en progreso. "
        "SIEMPRE filtrar por estado finalizado a menos que se pida explicitamente ver pendientes: "
        "hospitalario_evolucion: estado = 'A' (finalizado), 'P' = pendiente, 'D' = eliminado. "
        "hospitalario_cirugia_procedimiento: estado = 'A' (finalizado), 'P' = pendiente, 'D' = eliminado. "
        "hospitalario_cirugia_obstetrico: estado = 'A' (finalizado), 'P' = pendiente, 'D' = eliminado. "
        "hospitalario_doctor_nota_inicial: estado = 'F' (finalizado), 'P' = pendiente, 'E' = eliminado."
    )

    train_doc(
        "La tabla hospitalario_evolucion contiene las notas de evolucion medica en formato SOAP: "
        "subjetivo (lo que refiere el paciente), objetivo (hallazgos del examen), "
        "analisis (valoracion del medico), plan (plan de tratamiento). "
        "tipo_evolucion: 'EVO' = evolucion clinica normal, 'SUS' = suspension de medicamento "
        "(se genera automaticamente al suspender un medicamento en hospitalario_medicaciones_soluciones). "
        "Los medicos escriben evoluciones periodicas durante toda la estancia. "
        "Para contar evoluciones por paciente: agrupar por codigo_asignacion. "
        "IMPORTANTE: filtrar estado = 'A' para contar solo evoluciones finalizadas."
    )

    train_doc(
        "La tabla hospitalario_medicaciones_soluciones contiene todas las prescripciones "
        "de medicamentos durante la internacion. "
        "El campo codigo_grupo (enum group_hms) clasifica el tipo: "
        "'I' = indicacion simple de medicamento, "
        "'IP' = indicacion como parte de un plan de hidratacion, "
        "'H' = hidratacion/solucion parenteral, "
        "'N' = nutricion parenteral, "
        "'IN' = infusion, "
        "'AL' = medicamento de alta (recetado para llevar al egreso). "
        "estado: 'a' = activo, 'd' = descontinuado, 's' = suspendido. "
        "hora_uso es el intervalo entre dosis en horas como texto (ej: '8', '12', '24'), no texto descriptivo. "
        "Para medicamentos activos: estado = 'a'. "
        "Para medicamentos de alta: codigo_grupo = 'AL'. "
        "La via de administracion se une a via_medicine.vme_id: "
        "1=Gastroenterica, 2=IM, 3=IV, 4=Oftalmica, 5=Oral, 6=Parenteral, "
        "7=Rectal, 8=Respiratoria, 9=Subcutanea, 10=Sublingual, 11=Transdermica, "
        "12=Vaginal, 13=Otros."
    )

    train_doc(
        "La tabla hospitalario_registro_medicacion es el registro de administracion de "
        "medicamentos por enfermeria. Cada vez que una enfermera administra un medicamento, "
        "se crea un registro con el tiempo_ejecucion (momento exacto). "
        "estado (enum estado_hrm): 'A' = activo/administrado, 'E' = eliminado. "
        "Se une a hospitalario_medicaciones_soluciones para obtener los detalles de la prescripcion."
    )

    train_doc(
        "La tabla hospitalario_indicacion_dieta contiene las ordenes de dieta. "
        "Cuando el medico cambia la dieta, se crea un nuevo registro y el anterior "
        "se marca con is_outdated = true. Para obtener la dieta vigente: "
        "is_outdated = false AND (estado IS DISTINCT FROM 'd'). "
        "La tabla hospitalario_indicacion_medidas funciona identicamente pero para "
        "medidas de enfermeria (cuidados generales, posicion del paciente, etc.)."
    )

    train_doc(
        "La tabla hospitalario_nursing_atencion_enfermeria usa el sistema de clasificacion "
        "NANDA-Henderson. El campo diagnostico es la necesidad Henderson (1-14), "
        "codigo_nanda es el codigo NANDA del diagnostico de enfermeria. "
        "La tabla hospitalario_nursing_noc_nic contiene las intervenciones asociadas: "
        "typo_enfermeria = 'NOC' para resultados esperados (Nursing Outcomes Classification) "
        "y 'NIC' para intervenciones (Nursing Interventions Classification). "
        "activo = 1 significa que sigue vigente, 0 = inactivo."
    )

    train_doc(
        "La tabla hospitalario_doctor_nota_inicial contiene la nota medica inicial "
        "al momento de la admision. Puede haber multiples notas para una misma "
        "asignacion: una del medico tratante (es_medico_tratante = true) y otras "
        "de interconsultantes (codigo_pedido_interconsulta IS NOT NULL). "
        "Cualquier medico puede crear una nota inicial, no solo el medico tratante. "
        "Los flags es_medico_tratante y es_interconsulta_medico_tratante marcan el rol pero no restringen la creacion. "
        "IMPORTANTE: filtrar estado = 'F' para contar solo notas finalizadas. "
        "Es la tabla padre de: hospitalario_doctor_antropometricos, hospitalario_doctor_examen_fisico, "
        "hospitalario_historia_clinica, y hospitalario_doctor_diagnostico (diagnosticos CIE-10). "
        "Los diagnosticos se almacenan en formato desnormalizado: "
        "codigo_cie10a_main + codigo_cie10b_main = diagnostico principal, "
        "codigo_cie10a_minor_01..15 + codigo_cie10b_minor_01..15 = diagnosticos secundarios."
    )

    train_doc(
        "La tabla hospitalario_pedido_interconsulta registra solicitudes de opinion "
        "de otro servicio/especialista. pedido_codigo_medico es quien solicita, "
        "codigo_servicio es el servicio destino, motivo es la razon de la consulta. "
        "estado: 'u'=pendiente, 'h'=en proceso, 'c'=finalizado, 'd'=eliminado."
    )

    train_doc(
        "La tabla hospitalario_cirugia_procedimiento registra las cirugias realizadas "
        "durante la internacion. cirujano, ayudante y anestesista se almacenan como "
        "JSONB con el formato [{\"codigo_medico\": \"...\", \"nombre_medico\": \"...\"}]. "
        "tiempo_total_cirugia y tiempo_anestesia estan en minutos. "
        "perdida_estimada_sangre esta en mililitros. "
        "IMPORTANTE: filtrar estado = 'A' para contar solo cirugias finalizadas."
    )

    train_doc(
        "La tabla hospitalario_gestion_solicitar_transferencia registra solicitudes de "
        "transferencia de cama/servicio durante la internacion. "
        "codigo_servicio_original es el servicio actual, "
        "codigo_servicio_recommendado es el servicio destino propuesto. "
        "Cuando se aprueba, se crea una nueva fila en hospitalario_asignacion "
        "con orden_asignacion incrementado y la fila anterior se marca is_outdated = true."
    )

    train_doc(
        "La tabla hospitalario_doctor_datos_alta contiene los datos del alta/egreso. "
        "Solo existe si el paciente ya fue dado de alta. "
        "condicion_egreso es un codigo numerico (como caracter): "
        "1=CURADO/A, 2=MEJORADO/A, 3=ESTACIONARIO/A, 4=EMPEORADO/A, 5=FALLECIDO/A. "
        "Estos se unen a condicion_egreso.ceg_id para obtener la descripcion. "
        "tipo_egreso: 1=ALTA MEDICA, 2=TRASLADO A OTRO ESTABLECIMIENTO, "
        "3=RETIRO VOLUNTARIO, 4=FUGA, 5=DEFUNCION, 10=RECHAZO DE HOSPITALIZACION. "
        "Estos se unen a tipo_egreso.teg_id para obtener la descripcion. "
        "Los diagnosticos de egreso siguen el mismo patron que la nota inicial: "
        "codigo_cie10a_main/b_main para el principal, otros_01..15 para secundarios. "
        "is_delivery = 'S' indica que fue un parto/cesarea."
    )

    train_doc(
        "La tabla hospitalario_orden_internacion contiene la orden/solicitud de internacion. "
        "Se crea antes o al momento de la admision por el medico. "
        "motivo_internacion es la razon medica. cirugia = 'Y' si requiere cirugia. "
        "estado: 'A' = activo, 'E' = eliminado. "
        "Se vincula a hospitalario_asignacion a traves de codigo_hospitalario_orden."
    )

    train_doc(
        "La tabla epicrisis es un resumen narrativo de toda la estancia hospitalaria. "
        "Contiene el campo evolucion (texto libre) que resume lo ocurrido durante "
        "la internacion, y las fechas de ingreso y egreso (fec_ingreso, fec_egreso). "
        "Se usa junto con hospitalario_doctor_datos_alta para el informe completo de alta."
    )

    # NOTE: JOIN relationships are documented inline in each DDL via "-- Se une a:" comments.
    # This way they travel with the DDL during ChromaDB retrieval — no need for a separate doc.

    train_doc(
        "La nota inicial del medico tiene 3 tablas hijas, todas con PK "
        "(codigo_establecimiento, codigo_asignacion, codigo_nota_inicial):\n"
        "- hospitalario_doctor_antropometricos: signos vitales y medidas al ingreso "
        "(temperatura_axilar, presion arterial, saturacion_oxigeno, frecuencia_cardiaca, "
        "peso, talla, IMC, embarazada, semana_gestacion).\n"
        "- hospitalario_doctor_examen_fisico: notas del examen fisico por sistema "
        "(nota_aspecto_general, nota_cabeza, nota_cuello, nota_torax, nota_respiratorio, "
        "nota_cardiovascular, nota_abdomen, nota_genito_urinario, nota_musculoesqueletico, "
        "nota_piel_faneras, nota_hemolinfopoyetico, nota_neurologico, nota_psiquiatrico).\n"
        "- hospitalario_historia_clinica: historia clinica completa (motivo_consulta, "
        "historia_actual, antecedentes_medicos/quirurgicos/neonatales/familiares, alergias, "
        "medicamentos_uso, inmunizaciones).\n"
        "Todas se unen a hospitalario_doctor_nota_inicial via "
        "(codigo_establecimiento, codigo_asignacion, codigo_nota_inicial)."
    )

    train_doc(
        "La tabla hospitalario_nursing_antropometricos contiene los signos vitales "
        "registrados por enfermeria al momento de la admision. Tiene la misma estructura "
        "que hospitalario_doctor_antropometricos pero con PK (codigo_establecimiento, "
        "codigo_asignacion) en vez de incluir codigo_nota_inicial. "
        "Incluye temperatura_axilar, presion arterial (der/izq), frecuencia_cardiaca, "
        "frecuencia_respiratoria, pulso, saturacion_oxigeno, peso, talla, IMC."
    )

    train_doc(
        "La panoramica de enfermeria (hospitalario_panoramica_enfermeria) es la hoja "
        "de monitoreo diario de enfermeria. Cada fila tiene un codigo_item_examination "
        "(tipo de control), un valor (el valor registrado) y un tiempo_ejecucion "
        "(momento del registro). Se vincula a planes de medicacion a traves de "
        "hospitalario_panoramica_enfermeria_planes."
    )

    train_doc(
        "Los planes de medicacion (hospitalario_medicaciones_planes) representan planes "
        "de goteo IV o infusiones que agrupan multiples medicamentos. Cada plan tiene "
        "nombre_plan, indicaciones, y estado. La tabla de union "
        "hospitalario_medicaciones_planes_soluciones vincula planes con medicamentos "
        "individuales de hospitalario_medicaciones_soluciones. "
        "hospitalario_medicaciones_alta contiene los medicamentos recetados para llevar "
        "al alta, con la misma estructura que medicaciones_soluciones."
    )

    train_doc(
        "Las tablas hospitalario_profesional_servicio y hospitalario_profesional_responsable "
        "mapean profesionales (medicos/enfermeros) a servicios hospitalarios. "
        "hospitalario_profesional_servicio indica quien trabaja en que servicio; "
        "hospitalario_profesional_responsable indica quien es el responsable/jefe. "
        "Ambas se unen a usuario.codigo_usuario y servicio.codigo_servicio."
    )

    train_doc(
        "La tabla hospitalario_estudios_complementarios registra ordenes de estudios "
        "(laboratorio, imagenes, etc.). codigo_grupo_examen_estudio indica el grupo "
        "y codigo_item_examen_estudio el estudio especifico. "
        "hospitalario_procedimiento registra procedimientos medicos (no quirurgicos) "
        "usando codigos CIE-9 (codigo_procedimiento). valor_procedimiento es JSONB "
        "con detalles. hospitalario_procedimiento_valor almacena sub-valores."
    )

    train_doc(
        "La anestesia tiene 4 tablas relacionadas, todas unidas por "
        "(codigo_establecimiento, codigo_asignacion, codigo_anestesia):\n"
        "- hospitalario_pre_anestesia: evaluacion preoperatoria con diagnostico, "
        "cirugia_propuesta, comorbilidades (hta, arritmias, epoc, asma, etc.), "
        "via aerea (mallampati 1-4, dtm, apertura_bucal), score Goldman "
        "(puntaje_total), clasificacion ASA (asa 1-6), peso, talla.\n"
        "- hospitalario_intra_anestesia: tecnica anestesica usada "
        "(general, regional, sedacion) con detalles de intubacion y bloques regionales.\n"
        "- hospitalario_intra_anestesia_registro: serie temporal de eventos durante la "
        "cirugia. Cada fila tiene tiempo_actual, grupo_intra_anestesia (SV=signos "
        "vitales, DR=drogas), y valor.\n"
        "- hospitalario_post_anestesia: recuperacion en PACU con hasta 10 controles "
        "periodicos, score Steward para ninos (nino_total >= 6 para alta) y "
        "score Aldrete para adultos (adulto_total >= 9 para alta), "
        "visual_dolor (escala 0-10), destino post-PACU."
    )

    train_doc(
        "Las tablas obstetricas registran datos de partos/cesareas:\n"
        "- hospitalario_cirugia_obstetrico: datos de la gestacion (numero_gestacion, "
        "numero_partos, numero_abortos, semanas_de_gestacion, tipo_nacimiento, "
        "tipo_parto: 1=espontaneo, 2=cesarea, 3=instrumentado).\n"
        "- hospitalario_cirugia_obstetrico_nacidos: datos de cada recien nacido "
        "(peso_al_nacer en gramos, talla en cm, sexo: 1=M, 2=F, "
        "condicion_nacimiento: 1=vivo, 2=muerto).\n"
        "- hospitalario_obstetrico_alta: resumen obstetrico al alta con "
        "datos_recien_nacido en JSONB.\n"
        "Se vinculan a hospitalario_cirugia_procedimiento via "
        "(codigo_establecimiento, codigo_asignacion, orden_cirugia)."
    )

    train_doc(
        "El alta de trauma usa 3 tablas:\n"
        "- hospitalario_alta_trauma: datos detallados del mecanismo de lesion "
        "(tipo_accidente, caida, agresion, envenenamiento, quemadura, etc.), "
        "escala de Glasgow (escala_glasgow 3-15), is_outdated para versiones.\n"
        "- hospitalario_alta_trauma_causa: codigos CIE-10 de causas externas.\n"
        "- hospitalario_alta_trauma_diagnostico: codigos CIE-10 de diagnosticos "
        "de trauma, con tipo_diagnostico para principal/secundario.\n"
        "La tabla hospitalario_doctor_anamnesis contiene la anamnesis de trauma: "
        "motivo_ingreso, causa_externa_traumatismo, tipo de vehiculo, agresion, "
        "violencia, quemadura, sitio_ocurrencia."
    )

    train_doc(
        "La tabla hospitalario_orden es la tabla puente que vincula una asignacion (codigo_asignacion) "
        "con su orden (codigo_hospitalario_orden). Tiene la misma estructura que "
        "hospitalario_orden_internacion pero indexada por "
        "(codigo_establecimiento, codigo_asignacion, codigo_hospitalario_orden). "
        "Tiene muchas mas filas que hospitalario_orden_internacion porque la mayoria de ordenes "
        "vienen del sistema ambulatoria. Usar esta tabla para obtener la orden de internacion "
        "de un paciente ya asignado."
    )

    train_doc(
        "El flujo de solicitud y dispensacion de medicamentos a farmacia involucra:\n"
        "- hospitalario_formulario_solicitud_medicamentos: cabecera de la solicitud "
        "(codigo_enfermera, codigo_servicio como array de servicios).\n"
        "- hospitalario_solicitud_medicamentos_detail: detalle por paciente y medicamento "
        "(cantidad_dispensada, numero_total solicitado).\n"
        "- hospitalario_registro_dispensadas: registro de cada entrega de farmacia "
        "(codigo_transaccion, cantidad_dispensada, codigo_consumo).\n"
        "Para saber que medicamentos fueron dispensados a un paciente, unir "
        "hospitalario_registro_dispensadas via (codigo_establecimiento, codigo_asignacion)."
    )

    train_doc(
        "Las tablas nanda_henderson_* forman la taxonomia de enfermeria:\n"
        "- nanda_henderson_necesidad: 14 necesidades humanas de Henderson (1-14).\n"
        "- nanda_henderson_diagnostico: diagnosticos NANDA agrupados por necesidad.\n"
        "- nanda_henderson_objetivo: objetivos NOC (resultados) por diagnostico.\n"
        "- nanda_henderson_intervencion: intervenciones NIC por diagnostico.\n"
        "- nanda_henderson_actividad: actividades por intervencion NIC.\n"
        "Jerarquia: necesidad -> diagnostico -> (objetivo NOC | intervencion NIC) -> actividad.\n"
        "hospitalario_nursing_atencion_enfermeria.diagnostico = nanda_henderson_necesidad.codigo_necesidad, "
        "hospitalario_nursing_atencion_enfermeria.codigo_nanda = nanda_henderson_diagnostico.codigo_diagnostico."
    )

    train_doc(
        "Las tablas de auditoria almacenan versiones historicas:\n"
        "- hospitalario_doctor_datos_alta_auditoria: versiones previas del alta, "
        "PK incluye version_alta.\n"
        "- hospitalario_medicaciones_soluciones_auditoria: versiones previas de "
        "prescripciones, PK incluye version.\n"
        "- hospitalario_estudios_complementarios_alta: versiones previas de estudios, "
        "PK incluye version_estudio.\n"
        "- hospitalario_procedimiento_alta: versiones previas de procedimientos, "
        "PK incluye version_procedimiento.\n"
        "Usar estas tablas para consultas de historial de cambios."
    )

    # NOTE: Same — additional relationships already documented in DDL "-- Se une a:" comments.

    train_doc(
        "Cuando un paciente es transferido de cama/servicio, la fila anterior en "
        "hospitalario_asignacion se marca is_outdated = true y se crea una nueva fila "
        "con el mismo codigo_asignacion pero orden_asignacion incrementado. "
        "Para ver el historial completo de ubicaciones de un paciente: "
        "SELECT * FROM hospitalario_asignacion WHERE codigo_asignacion = '...' "
        "ORDER BY orden_asignacion. La fila con is_outdated = false es la ubicacion actual."
    )

    train_doc(
        "Una internacion puede terminar de dos formas: "
        "1) Alta/egreso normal: fin_del_evento = '1', con datos en hospitalario_doctor_datos_alta. "
        "2) Cancelacion: estado = 'C'. "
        "Nota: cancelar_hospitalario no se utiliza actualmente (siempre NULL en la practica). "
        "Para pacientes actualmente internados: fin_del_evento = '0' AND is_outdated = false."
    )

# =========================================================================
# Question-SQL examples
# =========================================================================

def _populate_examples() -> None:
    """Question-SQL pairs for the internacion domain."""
    print("Adding question-SQL examples for internacion domain...")

    # -----------------------------------------------------------------
    # Simple single-table queries
    # -----------------------------------------------------------------

    train_example(
        "Cuantos pacientes estan internados actualmente?",
        "SELECT COUNT(*) AS total_internados "
        "FROM dbt_analytics.mart_internados_activos;"
    )

    train_example(
        "Cuantas internaciones hubo este mes?",
        "SELECT COUNT(*) AS total_internaciones "
        "FROM hospitalario_asignacion "
        "WHERE hospitalario_fecha >= date_trunc('month', CURRENT_DATE) "
        "AND is_outdated = false;"
    )

    train_example(
        "Cuantas internaciones hubo el mes pasado?",
        "SELECT COUNT(*) AS total_internaciones "
        "FROM hospitalario_asignacion "
        "WHERE hospitalario_fecha >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month') "
        "AND hospitalario_fecha < date_trunc('month', CURRENT_DATE) "
        "AND is_outdated = false;"
    )

    train_example(
        "Cuantas camas disponibles hay?",
        "SELECT COUNT(*) AS camas_disponibles "
        "FROM dbt_analytics.mart_ocupacion_camas "
        "WHERE estado = 'Disponible';"
    )

    train_example(
        "Cuantas camas ocupadas hay?",
        "SELECT COUNT(*) AS camas_ocupadas "
        "FROM dbt_analytics.mart_ocupacion_camas "
        "WHERE estado = 'Ocupado';"
    )

    train_example(
        "Cual es el censo de camas actual? Mostrar cantidad por estado",
        "SELECT estado AS estado_cama, COUNT(*) AS cantidad "
        "FROM dbt_analytics.mart_ocupacion_camas "
        "GROUP BY estado ORDER BY estado;"
    )

    train_example(
        "Cuantas camas de UTI hay y cuantas estan ocupadas?",
        "SELECT "
        "COUNT(*) AS total_camas_uti, "
        "COUNT(*) FILTER (WHERE estado = 'Ocupado') AS ocupadas, "
        "COUNT(*) FILTER (WHERE estado = 'Disponible') AS disponibles "
        "FROM dbt_analytics.mart_ocupacion_camas "
        "WHERE tipo_cama = 'UTI/Terapia Intensiva';"
    )

    train_example(
        "Cuantas altas se dieron este mes?",
        "SELECT COUNT(*) AS total_altas "
        "FROM dbt_analytics.mart_altas_egresos "
        "WHERE fecha_egreso >= date_trunc('month', CURRENT_DATE) "
        "AND fecha_egreso < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month';"
    )

    train_example(
        "Cuantos pacientes fallecieron este anho?",
        "SELECT COUNT(*) AS total_fallecidos "
        "FROM dbt_analytics.mart_altas_egresos "
        "WHERE condicion_egreso = 'Fallecido/a' "
        "AND fecha_egreso >= date_trunc('year', CURRENT_DATE);"
    )

    train_example(
        "Cual es el promedio de dias de internacion de los pacientes dados de alta este mes?",
        "SELECT ROUND(AVG(dias_estancia), 1) AS promedio_dias "
        "FROM dbt_analytics.mart_altas_egresos "
        "WHERE fecha_egreso >= date_trunc('month', CURRENT_DATE) "
        "AND fecha_egreso < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month';"
    )

    train_example(
        "Cuantas evoluciones medicas se registraron hoy?",
        "SELECT COUNT(*) AS total_evoluciones "
        "FROM dbt_analytics.mart_evoluciones "
        "WHERE estado = 'Finalizado' AND fecha_hora_evolucion::date = CURRENT_DATE;"
    )

    train_example(
        "Cuantos medicamentos activos hay recetados actualmente a pacientes internados?",
        "SELECT COUNT(*) AS total_medicamentos_activos "
        "FROM hospitalario_medicaciones_soluciones hms "
        "JOIN hospitalario_asignacion ha ON hms.codigo_establecimiento = ha.codigo_establecimiento "
        "AND hms.codigo_asignacion = ha.codigo_asignacion "
        "WHERE hms.estado = 'a' AND ha.fin_del_evento = '0' AND ha.is_outdated = false;"
    )

    train_example(
        "Cuantas cirugias se realizaron este mes?",
        "SELECT COUNT(*) AS total_cirugias "
        "FROM dbt_analytics.mart_cirugias "
        "WHERE estado = 'Finalizado' "
        "AND fecha_hora_cirugia >= date_trunc('month', CURRENT_DATE) "
        "AND fecha_hora_cirugia < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month';"
    )

    train_example(
        "Cuantas interconsultas pendientes hay?",
        "SELECT COUNT(*) AS interconsultas_pendientes "
        "FROM hospitalario_pedido_interconsulta "
        "WHERE estado = 'u';"
    )

    # -----------------------------------------------------------------
    # JOIN queries with reference tables
    # -----------------------------------------------------------------

    train_example(
        "Listar pacientes internados actualmente con su nombre, cama y servicio",
        "SELECT nombre_paciente, cama, servicio, fecha_ingreso "
        "FROM dbt_analytics.mart_internados_activos "
        "ORDER BY fecha_ingreso;"
    )

    train_example(
        "Cuantos pacientes internados hay por servicio?",
        "SELECT servicio, COUNT(*) AS total_internados "
        "FROM dbt_analytics.mart_internados_activos "
        "GROUP BY servicio ORDER BY total_internados DESC;"
    )

    train_example(
        "Cuantas internaciones atendio cada medico este mes? Mostrar nombre del medico",
        "SELECT u.nombres || ' ' || u.apellidos AS nombre_medico, "
        "COUNT(*) AS total_internaciones "
        "FROM hospitalario_asignacion ha "
        "JOIN usuario u ON ha.codigo_medico = u.codigo_usuario "
        "WHERE ha.hospitalario_fecha >= date_trunc('month', CURRENT_DATE) "
        "AND ha.is_outdated = false "
        "GROUP BY u.nombres, u.apellidos ORDER BY total_internaciones DESC;"
    )

    train_example(
        "Listar camas disponibles con su sala, piso y edificio",
        "SELECT edificio, piso, sala, cama, tipo_cama "
        "FROM dbt_analytics.mart_ubicacion_camas "
        "WHERE estado = 'Disponible' "
        "ORDER BY edificio, piso, sala, cama;"
    )

    train_example(
        "Censo de camas por sala: mostrar total, ocupadas y disponibles",
        "SELECT sala, "
        "COUNT(*) AS total_camas, "
        "COUNT(*) FILTER (WHERE estado = 'Ocupado') AS ocupadas, "
        "COUNT(*) FILTER (WHERE estado = 'Disponible') AS disponibles "
        "FROM dbt_analytics.mart_ubicacion_camas "
        "GROUP BY sala ORDER BY sala;"
    )

    train_example(
        "Cuantas altas hubo por condicion de egreso este mes?",
        "SELECT condicion_egreso AS condicion, COUNT(*) AS cantidad "
        "FROM dbt_analytics.mart_altas_egresos "
        "WHERE fecha_egreso >= date_trunc('month', CURRENT_DATE) "
        "AND fecha_egreso < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month' "
        "GROUP BY condicion_egreso ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuantas altas hubo por tipo de egreso este mes?",
        "SELECT tipo_egreso AS tipo, COUNT(*) AS cantidad "
        "FROM dbt_analytics.mart_altas_egresos "
        "WHERE fecha_egreso >= date_trunc('month', CURRENT_DATE) "
        "AND fecha_egreso < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month' "
        "GROUP BY tipo_egreso ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuales son los diagnosticos principales mas frecuentes en las altas de este mes?",
        "SELECT diagnostico_egreso_principal AS diagnostico, COUNT(*) AS cantidad "
        "FROM dbt_analytics.mart_altas_egresos "
        "WHERE fecha_egreso >= date_trunc('month', CURRENT_DATE) "
        "AND fecha_egreso < date_trunc('month', CURRENT_DATE) + INTERVAL '1 month' "
        "AND diagnostico_egreso_principal IS NOT NULL "
        "GROUP BY diagnostico_egreso_principal ORDER BY cantidad DESC LIMIT 20;"
    )

    train_example(
        "Listar medicamentos mas recetados a pacientes internados actualmente",
        "SELECT hms.nombre_medicamento, COUNT(*) AS veces_recetado "
        "FROM hospitalario_medicaciones_soluciones hms "
        "JOIN hospitalario_asignacion ha ON hms.codigo_establecimiento = ha.codigo_establecimiento "
        "AND hms.codigo_asignacion = ha.codigo_asignacion "
        "WHERE hms.estado = 'a' AND ha.fin_del_evento = '0' AND ha.is_outdated = false "
        "GROUP BY hms.nombre_medicamento ORDER BY veces_recetado DESC LIMIT 20;"
    )

    train_example(
        "Cuantos medicamentos se administraron via intravenosa este mes?",
        "SELECT COUNT(*) AS total_iv "
        "FROM hospitalario_registro_medicacion hrm "
        "WHERE hrm.via_forma = 3 "
        "AND hrm.creacion_fecha >= date_trunc('month', CURRENT_DATE) "
        "AND (hrm.estado IS DISTINCT FROM 'E');"
    )

    train_example(
        "Cuantas intervenciones de enfermeria se registraron esta semana?",
        "SELECT COUNT(*) AS total_intervenciones "
        "FROM hospitalario_nursing_atencion_enfermeria "
        "WHERE creacion_fecha >= date_trunc('week', CURRENT_DATE) "
        "AND activo = 1;"
    )

    train_example(
        "Cuantas interconsultas se solicitaron por servicio este mes?",
        "SELECT s.nombre_servicio, COUNT(*) AS total_interconsultas "
        "FROM hospitalario_pedido_interconsulta hpi "
        "JOIN servicio s ON hpi.codigo_servicio = s.codigo_servicio "
        "WHERE hpi.creacion_fecha >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY s.nombre_servicio ORDER BY total_interconsultas DESC;"
    )

    train_example(
        "Cual es el promedio de dias de internacion por servicio este anho?",
        "SELECT servicio, "
        "ROUND(AVG(dias_estancia), 1) AS promedio_dias, "
        "COUNT(*) AS total_altas "
        "FROM dbt_analytics.mart_altas_egresos "
        "WHERE fecha_egreso >= date_trunc('year', CURRENT_DATE) "
        "GROUP BY servicio ORDER BY promedio_dias DESC;"
    )

    train_example(
        "Cuantas cirugias realizo cada cirujano este mes?",
        "SELECT elem->>'nombres' || ' ' || elem->>'apellidos' AS cirujano, "
        "COUNT(*) AS total_cirugias "
        "FROM hospitalario_cirugia_procedimiento hcp, "
        "jsonb_array_elements(hcp.cirujano) AS elem "
        "WHERE hcp.estado = 'A' "
        "AND hcp.creacion_fecha >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY elem->>'nombres', elem->>'apellidos' "
        "ORDER BY total_cirugias DESC;"
    )

    train_example(
        "Cuantas transferencias de servicio hubo este mes?",
        "SELECT COUNT(*) AS total_transferencias "
        "FROM hospitalario_gestion_solicitar_transferencia "
        "WHERE creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    # -----------------------------------------------------------------
    # Establishment-filtered queries
    # -----------------------------------------------------------------

    train_example(
        "Cuantos pacientes estan internados en un establecimiento especifico?",
        "SELECT e.nombre_establecimiento, COUNT(*) AS total_internados "
        "FROM hospitalario_asignacion ha "
        "JOIN establecimiento e ON ha.codigo_establecimiento = e.codigo_establecimiento "
        "WHERE ha.fin_del_evento = '0' AND ha.is_outdated = false "
        "AND e.nombre_establecimiento ILIKE '%hospital regional%' "
        "GROUP BY e.nombre_establecimiento;"
    )

    train_example(
        "Censo completo de camas por sala para un establecimiento",
        "SELECT s.nombre_sala, ser.nombre_servicio, "
        "COUNT(*) AS total, "
        "COUNT(*) FILTER (WHERE ce.estado = '1') AS disponibles, "
        "COUNT(*) FILTER (WHERE ce.estado = '2') AS ocupadas, "
        "COUNT(*) FILTER (WHERE ce.estado = '4') AS aisladas, "
        "COUNT(*) FILTER (WHERE ce.estado = '5') AS en_reparacion "
        "FROM cama c "
        "JOIN cama_estado ce ON c.codigo_establecimiento = ce.codigo_establecimiento "
        "AND c.codigo_cama = ce.codigo_cama "
        "JOIN sala s ON c.codigo_establecimiento = s.codigo_establecimiento "
        "AND c.codigo_sala = s.codigo_sala "
        "JOIN servicio ser ON s.codigo_servicio = ser.codigo_servicio "
        "JOIN establecimiento e ON c.codigo_establecimiento = e.codigo_establecimiento "
        "WHERE c.activo = 'Y' AND ce.activo = 'Y' "
        "AND e.nombre_establecimiento ILIKE '%hospital regional%' "
        "GROUP BY s.nombre_sala, ser.nombre_servicio ORDER BY s.nombre_sala;"
    )

    train_example(
        "Porcentaje de ocupacion de camas por servicio",
        "SELECT ser.nombre_servicio, "
        "COUNT(*) AS total_camas, "
        "COUNT(*) FILTER (WHERE ce.estado = '2') AS ocupadas, "
        "ROUND(100.0 * COUNT(*) FILTER (WHERE ce.estado = '2') / COUNT(*), 1) AS porcentaje_ocupacion "
        "FROM cama c "
        "JOIN cama_estado ce ON c.codigo_establecimiento = ce.codigo_establecimiento "
        "AND c.codigo_cama = ce.codigo_cama "
        "JOIN sala s ON c.codigo_establecimiento = s.codigo_establecimiento "
        "AND c.codigo_sala = s.codigo_sala "
        "JOIN servicio ser ON s.codigo_servicio = ser.codigo_servicio "
        "WHERE c.activo = 'Y' AND ce.activo = 'Y' "
        "GROUP BY ser.nombre_servicio ORDER BY porcentaje_ocupacion DESC;"
    )

    train_example(
        "Listar los 10 diagnosticos de ingreso mas frecuentes este anho",
        "SELECT hdd.nombre_cie10_main AS diagnostico, COUNT(*) AS cantidad "
        "FROM hospitalario_doctor_diagnostico hdd "
        "JOIN hospitalario_doctor_nota_inicial hdni "
        "ON hdd.codigo_establecimiento = hdni.codigo_establecimiento "
        "AND hdd.codigo_asignacion = hdni.codigo_asignacion "
        "AND hdd.codigo_nota_inicial = hdni.codigo_nota_inicial "
        "WHERE hdni.es_medico_tratante = true AND hdni.estado = 'F' "
        "AND hdni.creacion_fecha >= date_trunc('year', CURRENT_DATE) "
        "AND hdd.nombre_cie10_main IS NOT NULL "
        "GROUP BY hdd.nombre_cie10_main ORDER BY cantidad DESC LIMIT 10;"
    )

    train_example(
        "Cuantos pacientes fueron re-hospitalizados dentro de 14 dias este anho?",
        "SELECT COUNT(*) AS re_hospitalizaciones "
        "FROM hospitalario_asignacion "
        "WHERE re_hospitalizar_en_14_dias = true "
        "AND hospitalario_fecha >= date_trunc('year', CURRENT_DATE) "
        "AND is_outdated = false;"
    )

    # -----------------------------------------------------------------
    # Examples involving new tables
    # -----------------------------------------------------------------

    train_example(
        "Cual es la presion arterial y temperatura promedio de los pacientes al ingreso este mes?",
        "SELECT "
        "ROUND(AVG(da.der_presion_arterial_sis), 1) AS promedio_pa_sistolica, "
        "ROUND(AVG(da.der_presion_arterial_dias), 1) AS promedio_pa_diastolica, "
        "ROUND(AVG(da.temperatura_axilar), 1) AS promedio_temperatura "
        "FROM hospitalario_doctor_antropometricos da "
        "JOIN hospitalario_doctor_nota_inicial ni "
        "ON da.codigo_establecimiento = ni.codigo_establecimiento "
        "AND da.codigo_asignacion = ni.codigo_asignacion "
        "AND da.codigo_nota_inicial = ni.codigo_nota_inicial "
        "WHERE ni.es_medico_tratante = true AND ni.estado = 'F' "
        "AND ni.creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantos pacientes embarazadas estan internadas actualmente?",
        "SELECT COUNT(*) AS embarazadas_internadas "
        "FROM hospitalario_doctor_antropometricos da "
        "JOIN hospitalario_asignacion ha "
        "ON da.codigo_establecimiento = ha.codigo_establecimiento "
        "AND da.codigo_asignacion = ha.codigo_asignacion "
        "WHERE da.embarazada = true "
        "AND ha.fin_del_evento = '0' AND ha.is_outdated = false;"
    )

    train_example(
        "Cuantos estudios complementarios se solicitaron este mes?",
        "SELECT COUNT(*) AS total_estudios "
        "FROM hospitalario_estudios_complementarios "
        "WHERE creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantos procedimientos se registraron este mes por tipo (codigo CIE-9)?",
        "SELECT hp.codigo_procedimiento, hp.nombre_procedimiento, "
        "COUNT(*) AS cantidad "
        "FROM hospitalario_procedimiento hp "
        "WHERE hp.creacion_fecha >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY hp.codigo_procedimiento, hp.nombre_procedimiento "
        "ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuantas evaluaciones pre-anestesicas se realizaron este mes y cual es la clasificacion ASA mas comun?",
        "SELECT pa.asa AS clasificacion_asa, COUNT(*) AS cantidad "
        "FROM hospitalario_pre_anestesia pa "
        "WHERE pa.creacion_fecha >= date_trunc('month', CURRENT_DATE) "
        "AND pa.asa IS NOT NULL "
        "GROUP BY pa.asa ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuantos partos y cesareas hubo este mes?",
        "SELECT "
        "COUNT(*) FILTER (WHERE tipo_parto = 1) AS partos_espontaneos, "
        "COUNT(*) FILTER (WHERE tipo_parto = 2) AS cesareas, "
        "COUNT(*) FILTER (WHERE tipo_parto = 3) AS instrumentados, "
        "COUNT(*) AS total "
        "FROM hospitalario_cirugia_obstetrico "
        "WHERE creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantos recien nacidos hubo este mes y cual fue el peso promedio al nacer?",
        "SELECT COUNT(*) AS total_nacidos, "
        "ROUND(AVG(peso_al_nacer), 0) AS peso_promedio_gramos, "
        "COUNT(*) FILTER (WHERE condicion_nacimiento = 1) AS nacidos_vivos, "
        "COUNT(*) FILTER (WHERE condicion_nacimiento = 2) AS mortinatos "
        "FROM hospitalario_cirugia_obstetrico_nacidos "
        "WHERE creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantas altas de trauma hubo este anho por tipo de accidente?",
        "SELECT hat.tipo_accidente, COUNT(*) AS cantidad "
        "FROM hospitalario_alta_trauma hat "
        "JOIN hospitalario_asignacion ha "
        "ON hat.codigo_establecimiento = ha.codigo_establecimiento "
        "AND hat.codigo_asignacion = ha.codigo_asignacion "
        "WHERE hat.is_outdated = false "
        "AND ha.hospitalario_fecha >= date_trunc('year', CURRENT_DATE) "
        "GROUP BY hat.tipo_accidente ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuantos medicamentos fueron dispensados por farmacia este mes?",
        "SELECT COUNT(*) AS total_dispensaciones, "
        "SUM(cantidad_dispensada) AS total_unidades "
        "FROM hospitalario_registro_dispensadas "
        "WHERE creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Listar las necesidades Henderson con la cantidad de diagnosticos NANDA asociados",
        "SELECT hn.codigo_necesidad, hn.descripcion AS necesidad, "
        "COUNT(hd.codigo_diagnostico) AS total_diagnosticos "
        "FROM nanda_henderson_necesidad hn "
        "LEFT JOIN nanda_henderson_diagnostico hd "
        "ON hn.codigo_necesidad = hd.codigo_necesidad "
        "GROUP BY hn.codigo_necesidad, hn.descripcion "
        "ORDER BY hn.codigo_necesidad;"
    )

    train_example(
        "Que medicos trabajan en cada servicio hospitalario?",
        "SELECT s.nombre_servicio, u.nombres || ' ' || u.apellidos AS profesional "
        "FROM hospitalario_profesional_servicio hps "
        "JOIN servicio s ON hps.codigo_servicio = s.codigo_servicio "
        "JOIN usuario u ON hps.codigo_usuario = u.codigo_usuario "
        "ORDER BY s.nombre_servicio, profesional;"
    )

    train_example(
        "Cual fue el puntaje Aldrete promedio en las post-anestesias este mes?",
        "SELECT ROUND(AVG(adulto_total), 1) AS aldrete_promedio, "
        "COUNT(*) AS total_post_anestesias "
        "FROM hospitalario_post_anestesia "
        "WHERE creacion_fecha >= date_trunc('month', CURRENT_DATE) "
        "AND adulto_total IS NOT NULL;"
    )

    train_example(
        "Cuantos planes de medicacion (goteos IV) estan activos actualmente?",
        "SELECT COUNT(*) AS planes_activos "
        "FROM hospitalario_medicaciones_planes mp "
        "JOIN hospitalario_asignacion ha "
        "ON mp.codigo_establecimiento = ha.codigo_establecimiento "
        "AND mp.codigo_asignacion = ha.codigo_asignacion "
        "WHERE mp.estado = 'a' "
        "AND ha.fin_del_evento = '0' AND ha.is_outdated = false;"
    )

    # -----------------------------------------------------------------
    # Additional critical examples
    # -----------------------------------------------------------------

    train_example(
        "En que cama esta internado el paciente Juan Perez?",
        "SELECT CONCAT(TRIM(p.primer_nombre), ' ', TRIM(p.primer_apellido)) AS nombre_paciente, "
        "ha.nombre_cama, s.nombre_servicio "
        "FROM hospitalario_asignacion ha "
        "JOIN paciente p ON ha.codigo_paciente = p.codigo_paciente "
        "JOIN servicio s ON ha.codigo_servicio = s.codigo_servicio "
        "WHERE ha.fin_del_evento = '0' AND ha.is_outdated = false "
        "AND (LOWER(p.primer_nombre) ILIKE '%juan%' AND LOWER(p.primer_apellido) ILIKE '%perez%');"
    )

    train_example(
        "Cuantos dias llevan internados los pacientes actuales?",
        "SELECT CONCAT(TRIM(p.primer_nombre), ' ', TRIM(p.primer_apellido)) AS nombre_paciente, "
        "ha.nombre_cama, s.nombre_servicio, ha.hospitalario_fecha AS fecha_ingreso, "
        "CURRENT_DATE - ha.hospitalario_fecha AS dias_internado "
        "FROM hospitalario_asignacion ha "
        "JOIN paciente p ON ha.codigo_paciente = p.codigo_paciente "
        "JOIN servicio s ON ha.codigo_servicio = s.codigo_servicio "
        "WHERE ha.fin_del_evento = '0' AND ha.is_outdated = false "
        "ORDER BY dias_internado DESC;"
    )

    train_example(
        "Cuantos pacientes internados tienen diagnostico de neumonia?",
        "SELECT COUNT(DISTINCT ha.codigo_asignacion) AS total_pacientes "
        "FROM hospitalario_asignacion ha "
        "JOIN hospitalario_doctor_nota_inicial hdni ON ha.codigo_establecimiento = hdni.codigo_establecimiento "
        "AND ha.codigo_asignacion = hdni.codigo_asignacion "
        "JOIN hospitalario_doctor_diagnostico hdd ON hdni.codigo_establecimiento = hdd.codigo_establecimiento "
        "AND hdni.codigo_asignacion = hdd.codigo_asignacion AND hdni.codigo_nota_inicial = hdd.codigo_nota_inicial "
        "WHERE ha.fin_del_evento = '0' AND ha.is_outdated = false "
        "AND hdni.estado = 'F' "
        "AND hdd.nombre_cie10_main ILIKE '%neumonia%';"
    )

    train_example(
        "Que medicamentos tiene recetados actualmente un paciente especifico?",
        "SELECT hms.nombre_medicamento, hms.dosis, vm.vme_des AS via, "
        "hms.hora_uso AS frecuencia, hms.indicaciones, hms.fecha_inicio "
        "FROM hospitalario_medicaciones_soluciones hms "
        "JOIN via_medicine vm ON hms.vme_id = vm.vme_id "
        "JOIN hospitalario_asignacion ha ON hms.codigo_establecimiento = ha.codigo_establecimiento "
        "AND hms.codigo_asignacion = ha.codigo_asignacion "
        "JOIN paciente p ON ha.codigo_paciente = p.codigo_paciente "
        "WHERE hms.estado = 'a' AND ha.fin_del_evento = '0' AND ha.is_outdated = false "
        "AND p.primer_apellido ILIKE '%lopez%' "
        "ORDER BY hms.fecha_inicio;"
    )

    train_example(
        "Cuantas internaciones hubo por dia esta semana?",
        "SELECT ha.hospitalario_fecha AS fecha, COUNT(*) AS internaciones "
        "FROM hospitalario_asignacion ha "
        "WHERE ha.hospitalario_fecha >= date_trunc('week', CURRENT_DATE) "
        "AND ha.is_outdated = false "
        "GROUP BY ha.hospitalario_fecha ORDER BY ha.hospitalario_fecha;"
    )

    train_example(
        "Que pacientes internados no tienen evolucion registrada hoy?",
        "SELECT CONCAT(TRIM(p.primer_nombre), ' ', TRIM(p.primer_apellido)) AS nombre_paciente, "
        "ha.nombre_cama, s.nombre_servicio "
        "FROM hospitalario_asignacion ha "
        "JOIN paciente p ON ha.codigo_paciente = p.codigo_paciente "
        "JOIN servicio s ON ha.codigo_servicio = s.codigo_servicio "
        "WHERE ha.fin_del_evento = '0' AND ha.is_outdated = false "
        "AND NOT EXISTS (SELECT 1 FROM hospitalario_evolucion he "
        "WHERE he.codigo_establecimiento = ha.codigo_establecimiento "
        "AND he.codigo_asignacion = ha.codigo_asignacion "
        "AND he.creacion_fecha = CURRENT_DATE);"
    )

    train_example(
        "Mostrar el censo completo de camas con paciente, medico, servicio, edificio, piso y sala",
        "SELECT e.nombre_edificio, pi.nombre_piso, sa.nombre_sala, "
        "c.nombre_cama, "
        "CASE ce.estado WHEN '1' THEN 'DISPONIBLE' WHEN '2' THEN 'OCUPADO' "
        "WHEN '3' THEN 'PREPARACION' WHEN '4' THEN 'AISLADO' "
        "WHEN '5' THEN 'EN_REPARACION' END AS estado_cama, "
        "CASE c.tipo_cama WHEN 'G' THEN 'General' WHEN 'T' THEN 'UTI' END AS tipo, "
        "CONCAT(TRIM(p.primer_nombre), ' ', TRIM(p.primer_apellido)) AS paciente, "
        "CONCAT(TRIM(u.nombres), ' ', TRIM(u.apellidos)) AS medico, "
        "s.nombre_servicio "
        "FROM cama c "
        "JOIN cama_estado ce ON c.codigo_establecimiento = ce.codigo_establecimiento "
        "AND c.codigo_cama = ce.codigo_cama "
        "JOIN sala sa ON c.codigo_establecimiento = sa.codigo_establecimiento "
        "AND c.codigo_sala = sa.codigo_sala "
        "JOIN piso pi ON c.codigo_establecimiento = pi.codigo_establecimiento "
        "AND c.codigo_piso = pi.codigo_piso "
        "JOIN edificio e ON c.codigo_establecimiento = e.codigo_establecimiento "
        "AND c.codigo_edificio = e.codigo_edificio "
        "LEFT JOIN hospitalario_asignacion ha ON c.codigo_establecimiento = ha.codigo_establecimiento "
        "AND c.codigo_cama = ha.codigo_cama AND ha.is_outdated = false AND ha.fin_del_evento = '0' "
        "LEFT JOIN paciente p ON ha.codigo_paciente = p.codigo_paciente "
        "LEFT JOIN usuario u ON ha.codigo_medico = u.codigo_usuario "
        "LEFT JOIN servicio s ON ha.codigo_servicio = s.codigo_servicio "
        "WHERE c.activo = 'Y' AND ce.activo = 'Y' "
        "ORDER BY e.nombre_edificio, pi.nombre_piso, sa.nombre_sala, c.nombre_cama;"
    )

    train_example(
        "Top 10 diagnosticos de egreso con codigo CIE-10 completo este anho",
        "SELECT CASE WHEN TRIM(alta.codigo_cie10b_main) IS NOT NULL "
        "THEN CONCAT(alta.codigo_cie10a_main, '.', alta.codigo_cie10b_main) "
        "ELSE alta.codigo_cie10a_main END AS codigo_cie10, "
        "alta.nombre_cie10_main AS diagnostico, COUNT(*) AS cantidad "
        "FROM hospitalario_doctor_datos_alta alta "
        "JOIN hospitalario_asignacion ha ON alta.codigo_establecimiento = ha.codigo_establecimiento "
        "AND alta.codigo_asignacion = ha.codigo_asignacion "
        "WHERE alta.fecha_egreso >= date_trunc('year', CURRENT_DATE) "
        "AND ha.is_outdated = false AND alta.nombre_cie10_main IS NOT NULL "
        "GROUP BY codigo_cie10, alta.nombre_cie10_main "
        "ORDER BY cantidad DESC LIMIT 10;"
    )

    train_example(
        "Distribucion de pacientes internados por grupo de edad",
        "SELECT "
        "COUNT(*) FILTER (WHERE ha.edad_paciente BETWEEN 0 AND 4 AND ha.tipo_edad = 1 OR ha.tipo_edad > 1) AS \"0-4\", "
        "COUNT(*) FILTER (WHERE ha.edad_paciente BETWEEN 5 AND 14 AND ha.tipo_edad = 1) AS \"5-14\", "
        "COUNT(*) FILTER (WHERE ha.edad_paciente BETWEEN 15 AND 29 AND ha.tipo_edad = 1) AS \"15-29\", "
        "COUNT(*) FILTER (WHERE ha.edad_paciente BETWEEN 30 AND 49 AND ha.tipo_edad = 1) AS \"30-49\", "
        "COUNT(*) FILTER (WHERE ha.edad_paciente BETWEEN 50 AND 64 AND ha.tipo_edad = 1) AS \"50-64\", "
        "COUNT(*) FILTER (WHERE ha.edad_paciente >= 65 AND ha.tipo_edad = 1) AS \"65+\" "
        "FROM hospitalario_asignacion ha "
        "WHERE ha.hospitalario_fecha >= date_trunc('year', CURRENT_DATE) "
        "AND ha.is_outdated = false;"
    )

    train_example(
        "Cuantos pacientes atendio cada enfermera esta semana? Contar panoramicas y registros de medicacion",
        "SELECT CONCAT(TRIM(u.nombres), ' ', TRIM(u.apellidos)) AS enfermera, "
        "COUNT(DISTINCT hpe.codigo_asignacion) FILTER (WHERE hpe.codigo_asignacion IS NOT NULL) AS pacientes_panoramica, "
        "COUNT(DISTINCT hrm.codigo_asignacion) FILTER (WHERE hrm.codigo_asignacion IS NOT NULL) AS pacientes_medicacion "
        "FROM usuario u "
        "LEFT JOIN hospitalario_panoramica_enfermeria hpe ON u.codigo_usuario = hpe.creacion_usuario "
        "AND hpe.creacion_fecha >= date_trunc('week', CURRENT_DATE) "
        "LEFT JOIN hospitalario_registro_medicacion hrm ON u.codigo_usuario = hrm.creacion_usuario "
        "AND hrm.creacion_fecha >= date_trunc('week', CURRENT_DATE) AND hrm.estado = 'A'::estado_hrm "
        "WHERE hpe.creacion_usuario IS NOT NULL OR hrm.creacion_usuario IS NOT NULL "
        "GROUP BY u.nombres, u.apellidos "
        "ORDER BY pacientes_panoramica DESC NULLS LAST;"
    )
