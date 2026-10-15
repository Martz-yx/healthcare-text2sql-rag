"""
Seed training for the ambulatoria (outpatient) domain.

Provides DDLs, business documentation, and question-SQL examples for the
ambulatoria scope: paciente_asignacion, consulta, preconsulta, diagnosticos,
medicamentos, trauma, prescripciones, agenda, catalogos clinicos, y tablas
de procedimientos. Shared reference tables (paciente, usuario, servicio,
establecimiento, CIE-10, medicamento, geografia, demograficos) live in
seed_common.py. Each train_* call dispatches through the shared sink
defined in seed_training.py; entries land in ChromaDB with
source='seed:ambulatoria' and are rebuilt independently of other seed sets.
"""

from seed_training import train_ddl, train_doc, train_example

def populate() -> None:
    """Run every populate step for the ambulatoria seed set."""
    _populate_ddls()
    _populate_docs()
    _populate_examples()

# =========================================================================
# DDLs
# =========================================================================

def _populate_ddls() -> None:
    """DDLs for all ambulatoria-scope tables."""

    # -----------------------------------------------------------------
    # Core visit flow: paciente_asignacion -> preconsulta -> consulta
    # -----------------------------------------------------------------
    print("Adding DDLs for core visit flow...")

    train_ddl("""
-- Tabla central de ambulatoria: cada fila es un turno/visita de un paciente.
-- Se une a: paciente.codigo_paciente via codigo_paciente (datos del paciente)
-- Se une a: usuario.codigo_usuario via codigo_medico (medico titular)
-- Se une a: usuario.codigo_usuario via medico_suplente (medico suplente)
-- Se une a: servicio.codigo_servicio via codigo_servicio (servicio medico)
-- Se une a: establecimiento.codigo_establecimiento via codigo_establecimiento (hospital)
-- Se une a: agenda via (agenda_id, codigo_establecimiento) (turno agendado)
-- Se une a: departamento.codigo_departamento via cod_departamento_residencia (depto residencia)
-- Se une a: distrito via (cod_departamento_residencia, cod_distrito_residencia) (distrito residencia)
-- Se une a: barrio via (cod_departamento_residencia, cod_distrito_residencia, cod_barrio_residencia)
-- Se une a: turno_horario.codigo_turno via codigo_turno (turno del horario)
-- Referenciado por: consulta, preconsulta, consulta_diagnostico, consulta_medicamento,
--   consulta_procedimiento, consulta_anatomia_patologica, trauma_consulta,
--   trauma_preconsulta, etc.
CREATE TABLE public.paciente_asignacion (
    codigo_establecimiento character varying(16) NOT NULL,  -- hospital/establecimiento
    codigo_asignacion character varying(10) NOT NULL,       -- codigo unico de visita/turno
    codigo_paciente character varying(20) NOT NULL,         -- cedula o pasaporte del paciente
    tipo_documento character varying(1),                    -- '1'=cedula, '2'=pasaporte, '4'=otro
    consulta_fecha date,                                    -- fecha del turno
    tipo_consulta character varying(1),                     -- 'A'=ambulatoria, 'U'=urgencia, 'T'=teleconsulta, 'I'=internacion, 'E'=extramural, 'D'=domiciliaria
    codigo_medico character varying(10),                    -- medico titular (join usuario.codigo_usuario)
    medico_suplente character varying(10),                  -- medico suplente (join usuario.codigo_usuario)
    codigo_consultorio character varying(4),                -- consultorio asignado
    hora_inicio time without time zone,                     -- hora programada del turno (local)
    numero_orden_espera integer,                            -- posicion en cola de espera
    persona_cancela character varying(30),                  -- persona que cancelo el turno
    estado character varying(2),                            -- estado del turno (generalmente vacio; 'CA'=cancelado segun flujo)
    primera_consulta_anho character varying(1),             -- '1' si es primera consulta del anho
    referido character varying(2),                          -- '0'/NULL=no referido
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),                 -- usuario creador (join usuario)
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    codigo_servicio numeric,                                -- servicio/departamento medico (join servicio)
    edad_paciente numeric,                                  -- edad al momento del turno
    tipo_edad numeric,                                      -- unidad: 1=anho, 2=mes, 3=dia, 4=hora, 5=minuto (join tipo_edad)
    codigo_turno numeric,                                   -- turno del horario (join turno_horario)
    cod_departamento_residencia character(2),               -- departamento residencia (join departamento)
    cod_distrito_residencia character(3),                   -- distrito residencia (join distrito)
    cod_barrio_residencia character(3),                     -- barrio residencia (join barrio)
    area character(3),                                      -- '0'=urbano, '1'=rural
    btimestamp character varying(15),                       -- timestamp de sincronizacion
    seguro_medico character varying(8),                     -- codigo del seguro medico
    status_ips boolean,                                     -- afiliado al IPS
    codigo_departamento_referido character(2),              -- depto del establecimiento que refiere
    codigo_distrito_referido character(3),                  -- distrito del establecimiento que refiere
    codigo_estabiecimiento_referido character varying(16),  -- establecimiento que refiere
    alterar_estabiecimiento_referido character varying(64), -- nombre manual del referente
    otro_barrio character varying(40),                      -- barrio en texto libre si no esta en catalogo
    agenda_id integer,                                      -- turno agendado (join agenda)
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion)
);
""")

    train_ddl("""
-- Registro de la consulta medica. 1:1 con paciente_asignacion.
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.consulta (
    codigo_establecimiento character varying(16) NOT NULL,  -- hospital
    codigo_asignacion character varying(10) NOT NULL,       -- visita
    motivo_consulta text,                                   -- motivo de la consulta (texto libre)
    historia_actual text,                                   -- historia clinica actual / sintomas
    vacunado character varying(1),                          -- '0'=no vacunado, '1'=vacunado
    derivar character varying(1),                           -- destino del paciente: '0'=No aplica, '1'=Se refiere, '2'=Internacion, '3'=Domicilio, '4'=Fuga/No se realizo, '5'=Muerte, '6'=Incompleto(Re-Evaluar), '7'=Incompleto(Reasignar)
    creacion_fecha date NOT NULL,                           -- fecha de la consulta
    creacion_hora time without time zone NOT NULL,          -- hora de la consulta
    creacion_usuario character varying(10),                 -- medico que registra (join usuario)
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    observacion text,                                       -- observaciones adicionales
    codigo_servicio numeric,                                -- servicio medico
    evolucion text,                                         -- notas de evolucion clinica
    impresion_diagnostica text,                             -- impresion diagnostica del medico
    btimestamp character varying(15),
    peso_nacimiento numeric,                                -- peso al nacer (consulta neonatal)
    edad_gestacional numeric,                               -- semanas de gestacion (neonatal)
    fecha_nacimiento_nino date,                             -- fecha nacimiento del nino (neonatal)
    tipo_observacion character varying(1),                  -- estado de procedimiento: 'S'=Solicitado, 'R'=Realizado, 'H'=Solicitado+Iniciar hoy
    empadronamiento boolean,                                -- indica empadronamiento
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion),
    FOREIGN KEY (codigo_establecimiento, codigo_asignacion)
        REFERENCES paciente_asignacion(codigo_establecimiento, codigo_asignacion)
);
""")

    train_ddl("""
-- Registro de triaje / preconsulta por enfermeria. Contiene signos vitales.
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: consulta via (codigo_establecimiento, codigo_asignacion) (detalle de la consulta)
-- PK incluye creacion_fecha: permite multiples registros de triaje por visita.
CREATE TABLE public.preconsulta (
    codigo_establecimiento character varying(16) NOT NULL,     -- hospital
    codigo_asignacion character varying(10) NOT NULL,          -- visita
    peso numeric,                                              -- peso en kg
    talla numeric,                                             -- estatura en cm
    alimentacion character varying(1),                         -- '0'=Lactancia Materna Exclusiva, '1'=Lactancia Mixta, '2'=Lactancia Artificial
    indice_masa_corporal numeric,                              -- IMC calculado
    circunferencia_abdominal numeric,                          -- circunferencia abdominal en cm
    estado_nutricional character varying(1),                   -- '0'=Normal, '1'=Riesgo desnutricion, '2'=Desnutricion Moderada, '3'=Desnutricion Grave, '4'=Sobrepeso, '5'=Obesidad
    desarrollo_madurativo character varying(50),               -- desarrollo madurativo (pediatria)
    escala_tanner character varying(25),                       -- escala de Tanner (pediatria)
    toaxilar_rectal numeric,                                   -- temperatura axilar/rectal en C
    pulso character varying(3),                                -- pulso (latidos/min)
    frecuencia_respiratoria character varying(3),              -- frecuencia respiratoria (resp/min)
    frecuencia_cardiaca character varying(3),                  -- frecuencia cardiaca (lat/min)
    interconsulta_detalle character varying(255),              -- detalle de interconsulta
    tratamiento_detalles character varying(25),                -- detalles de tratamiento
    examen_fisico text,                                        -- examen fisico texto libre
    embarazada character varying(1),                           -- '1' si esta embarazada
    fum date,                                                  -- fecha de ultima menstruacion
    motivo_consulta text,                                      -- motivo de consulta (texto libre)
    creacion_fecha date NOT NULL,                              -- fecha de registro (parte de PK)
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(10),                    -- enfermero/a que registra
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    presion_arterial_sis numeric(3,0),                         -- presion arterial sistolica mmHg
    presion_arterial_dias numeric(3,0),                        -- presion arterial diastolica mmHg
    nivel_urgencia numeric(1,0),                               -- nivel de urgencia (triaje)
    peso_percentil numeric,                                    -- percentil de peso (pediatria)
    talla_percentil numeric,                                   -- percentil de talla (pediatria)
    perimetro_craneal numeric,                                 -- perimetro craneal cm (pediatria)
    perimetro_craneal_percentil numeric,                       -- percentil perimetro craneal
    indice_masa_corporal_percentil numeric,                    -- percentil de IMC
    saturacion_oxigeno integer,                                -- SpO2 (%)
    hba1c numeric,                                             -- hemoglobina glicosilada (%)
    btimestamp character varying(15),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, creacion_fecha)
);
""")

    # -----------------------------------------------------------------
    # Clinical detail per visit: diagnosticos, medicamentos, procedimientos
    # -----------------------------------------------------------------
    print("Adding DDLs for clinical detail per visit...")

    train_ddl("""
-- Diagnosticos CIE-10 registrados en una consulta ambulatoria.
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: cie10 via (codigo_cie10a, codigo_cie10b) (catalogo CIE-10)
-- Se une a: consulta via (codigo_establecimiento, codigo_asignacion) (detalle de la consulta)
CREATE TABLE public.consulta_diagnostico (
    codigo_establecimiento character varying(16) NOT NULL,  -- hospital
    codigo_asignacion character varying(10) NOT NULL,       -- visita
    orden integer NOT NULL,                                 -- 1=diagnostico principal, 2+=secundarios
    codigo_cie10a character varying(3),                     -- categoria CIE-10 (3 chars, join cie10)
    codigo_cie10b character varying(4),                     -- subcategoria CIE-10 (4 chars, join cie10)
    nombre_cie10 text,                                      -- nombre del diagnostico (desnormalizado)
    nuevo character varying(1),                             -- '1'=diagnostico nuevo, '0'=preexistente
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    btimestamp character varying(15),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden),
    FOREIGN KEY (codigo_establecimiento, codigo_asignacion)
        REFERENCES paciente_asignacion(codigo_establecimiento, codigo_asignacion)
);
""")

    train_ddl("""
-- Medicamentos recetados en una consulta ambulatoria.
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: medicamento via (codigo_establecimiento, codigo_medicamento)
-- Se une a: consulta via (codigo_establecimiento, codigo_asignacion) (detalle de la consulta)
CREATE TABLE public.consulta_medicamento (
    codigo_establecimiento character varying(16) NOT NULL,  -- hospital
    codigo_asignacion character varying(10) NOT NULL,       -- visita
    codigo_grupo integer NOT NULL,                          -- grupo de prescripcion
    codigo_medicamento bigint NOT NULL,                     -- medicamento (join medicamento)
    dosis character varying(10),                            -- dosis prescrita
    forma_uso text,                                         -- instrucciones de uso
    dias_uso integer,                                       -- dias de tratamiento
    forma_medicamento text,                                 -- via de administracion
    cantidad_dispensada integer,                            -- cantidad entregada
    numero_total integer,                                   -- cantidad total recetada
    isdc character varying(1),                              -- 'Y'=eliminado, 'N'=activo
    observacion character varying(255),                     -- observaciones
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    estado text,                                            -- 'Eliminado', 'Completo', 'En Proceso'
    btimestamp character varying(15),
    otro_via character varying(10),                         -- via alternativa si no esta en catalogo
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_grupo, codigo_medicamento)
);
""")

    train_ddl("""
-- Procedimientos solicitados/realizados en una consulta (laboratorio, imagenes, CIE-9).
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: consulta via (codigo_establecimiento, codigo_asignacion) (detalle de la consulta)
-- Se une a: examen_laboratorial.codigo_examen via codigo_procedimiento (examenes de laboratorio)
-- Se une a: cie9.codigo_procedimiento via codigo_procedimiento (procedimientos medicos CIE-9)
CREATE TABLE public.consulta_procedimiento (
    codigo_establecimiento character varying(16) NOT NULL,  -- hospital
    codigo_asignacion character varying(10) NOT NULL,       -- visita
    codigo_paciente character varying(20),                  -- paciente
    codigo_ficha character varying(10),                     -- ficha clinica
    codigo_procedimiento character varying(9) NOT NULL,     -- join examen_laboratorial.codigo_examen (lab, ej. '00101') o cie9.codigo_procedimiento (procedimientos, ej. '00.F9')
    secuencia_numero integer NOT NULL,                      -- secuencia por procedimiento
    reporte_laboratorio character varying(1000),            -- valor del resultado de laboratorio
    valor_referencia character varying(50),                 -- valor de referencia normal
    valor_referencia_maximo character varying(50),          -- rango maximo de referencia
    valor_referencia_minimo character varying(50),          -- rango minimo de referencia
    unidad_medida character varying(10),                    -- unidad de medida del resultado
    isdc character varying(1),                              -- 'S'=eliminado, NULL/otro=activo
    ps character varying(255),                              -- observaciones del procedimiento
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    reporttag character varying(1) NOT NULL,                -- 'Y'=estudio, 'N'=procedimiento
    btimestamp character varying(15),
    nota text,                                              -- notas adicionales
    estado character varying(1),                            -- 'S'=Solicitado, 'R'=Realizado, 'H'=Solicitado+Iniciar hoy
    version integer NOT NULL DEFAULT 1,                     -- version (multiples iteraciones)
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_procedimiento, secuencia_numero, version)
);
""")

    # -----------------------------------------------------------------
    # Trauma: preconsulta, consulta, diagnosticos, evoluciones
    # -----------------------------------------------------------------
    print("Adding DDLs for trauma tables...")

    train_ddl("""
-- Consulta de trauma: signos vitales, scores (Glasgow, RTS, IPT, MESS, AIS, TRISS),
-- examen fisico, quemaduras. Versionada con consulta_version + is_outdated.
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Se une a: consulta via (codigo_establecimiento, codigo_asignacion) (detalle de la consulta)
-- Referenciado por: trauma_consulta_diagnostico via (codigo_establecimiento, codigo_asignacion, consulta_version)
CREATE TABLE public.trauma_consulta (
    codigo_establecimiento character varying(16) NOT NULL,  -- hospital
    codigo_asignacion character varying(10) NOT NULL,       -- visita
    consulta_version smallint NOT NULL,                     -- version de la consulta (incrementa con cada edicion)
    -- Signos vitales
    toaxilar_rectal real,                                   -- temperatura axilar/rectal en C
    presion_arterial_sis smallint,                          -- presion sistolica mmHg
    presion_arterial_dias smallint,                         -- presion diastolica mmHg
    frecuencia_respiratoria smallint,                       -- frecuencia respiratoria (resp/min)
    pulso smallint,                                         -- pulso (lat/min)
    saturacion_oxigeno smallint,                            -- SpO2 (%)
    paro_cardio_respiratorio boolean,                       -- hubo paro cardiorrespiratorio
    tiempo_paro_cardio_respiratorio smallint,               -- duracion del paro (minutos)
    hemorragia_externa_exanguinante boolean,                -- hemorragia externa exanguinante
    describir_hemorragia_externa_exan text,                 -- descripcion de la hemorragia
    -- Evaluacion primaria (ABCDE)
    via_aerea_columna_cervical text,                        -- via aerea y columna cervical
    respiracion_ventilacion text,                           -- respiracion/ventilacion
    circulacion text,                                       -- circulacion
    estado_neurologico text,                                -- estado neurologico
    exposicion_control_ambiental text,                      -- exposicion/control ambiental
    -- FAST y quemaduras
    fast character varying(1),                              -- FAST ecografia: '1'=Positivo, '2'=Negativo, '3'=Indeterminado, '4'=No Aplica, '5'=No se Realiza
    grado_quemadura character varying(4),                   -- mascara binaria: pos1=GradoI, pos2=GradoII, pos3=GradoIII, pos4=Otros ('0'/'1' cada pos)
    otros_grados_quemadura character varying(64),           -- descripcion si pos4 de grado_quemadura='1'
    puntos_quemaduras character varying(15),                -- mascara binaria 15 areas: 1=Cabeza,2=Cuello,3=Torax ant,4=Torax post,5=Brazo der,6=Brazo izq,7=Antebrazo der,8=Antebrazo izq,9=Mano der,10=Mano izq,11=Genitales,12=Muslo der,13=Muslo izq,14=Pierna der,15=Pierna izq
    peso real,                                              -- peso del paciente (kg)
    x_quemadura smallint,                                   -- factor X para calculo quemaduras
    scq_valor real,                                         -- superficie corporal quemada (%)
    parkland real,                                          -- calculo formula de Parkland (ml)
    -- Glasgow Coma Scale
    glasgow boolean,                                        -- true si se evaluo Glasgow
    apertura_ocular smallint,                               -- componente ocular (1-4)
    respuesta_verbal smallint,                              -- componente verbal (1-5)
    respuesta_motora smallint,                              -- componente motor (1-6)
    total_glassgow smallint,                                -- total Glasgow (3-15)
    -- Escala Revisada de Trauma (RTS)
    escala_revisada_trauma boolean,                         -- true si se evaluo RTS
    frecuencia_respiratoria_escala smallint,                -- componente FR codificado (0-4)
    presion_sistolica smallint,                             -- componente PA codificado (0-4)
    escala_glasgow smallint,                                -- componente Glasgow codificado (0-4)
    -- Indice Pediatrico de Trauma (IPT)
    peso_rts_ipt_pediatrico smallint,                       -- componente peso IPT
    via_aerea_rts_ipt_pediatrico smallint,                  -- componente via aerea IPT
    ta_rts_ipt_pediatrico smallint,                         -- componente TA IPT
    snc_rts_ipt_pediatrico smallint,                        -- componente SNC IPT
    heridas_rts_ipt_pediatrico smallint,                    -- componente heridas IPT
    fracturas_rts_ipt_pediatrico smallint,                  -- componente fracturas IPT
    total_escala_revisada smallint,                         -- total RTS o IPT
    -- MESS (Mangled Extremity Severity Score)
    escala_severidad_extremidad_mutilada boolean,           -- true si se evaluo MESS
    lesion_mess smallint,                                   -- componente lesion (1-4)
    isquemia_mess smallint,                                 -- componente isquemia (1-3)
    choque_mess smallint,                                   -- componente choque (0-2)
    edad_mess smallint,                                     -- componente edad (0-2)
    total_mess smallint,                                    -- total MESS (>=7 indica amputacion probable)
    -- AIS (Abbreviated Injury Scale) por region corporal
    ais_cabeza smallint,                                    -- AIS cabeza (0-6)
    ais_cara smallint,                                      -- AIS cara (0-6)
    ais_torax smallint,                                     -- AIS torax (0-6)
    ais_abdomen smallint,                                   -- AIS abdomen (0-6)
    ais_extremidad smallint,                                -- AIS extremidades (0-6)
    ais_externa smallint,                                   -- AIS externa (0-6)
    -- Examen fisico por region (texto libre por area corporal)
    examen_fisico_cabeza text,                              -- hallazgos en cabeza
    examen_fisico_cuello text,                              -- hallazgos en cuello
    examen_fisico_torax text,                               -- hallazgos en torax
    examen_fisico_abdomen_genito_urinario text,             -- hallazgos en abdomen/genitourinario
    examen_fisico_pelvis_perine text,                       -- hallazgos en pelvis/perine
    examen_fisico_extremidades_musculo_esqueletico text,    -- hallazgos en extremidades/musculoesqueletico
    evolucion_paciente text,                                -- notas de evolucion del paciente
    -- Versionado y auditoria
    is_outdated boolean NOT NULL,                           -- true=version anterior reemplazada
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(10) NOT NULL,
    -- TRISS (Trauma and Injury Severity Score)
    enable_triss boolean,                                   -- true si se calculo TRISS
    historia_actual text,                                   -- historia actual del trauma
    impresion_diagnostica text,                             -- impresion diagnostica
    tipo_trauma smallint,                                   -- 0=cerrado (blunt), 1=penetrante
    prob_sobrevida_cerrado real,                            -- probabilidad sobrevida trauma cerrado
    prob_sobrevida_penetrante real,                         -- probabilidad sobrevida trauma penetrante
    triss_rts real,                                         -- RTS usado para TRISS
    triss_iss real,                                         -- ISS usado para TRISS
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, consulta_version)
);
""")

    train_ddl("""
-- Diagnosticos CIE-10 de una consulta de trauma. Versionada con is_outdated.
-- Se une a: trauma_consulta via (codigo_establecimiento, codigo_asignacion, consulta_version)
-- Se une a: cie10 via (codigo_cie10a, codigo_cie10b)
CREATE TABLE public.trauma_consulta_diagnostico (
    codigo_establecimiento character varying(16) NOT NULL,  -- hospital
    codigo_asignacion character varying(10) NOT NULL,       -- visita
    tipo_diagnostico character varying(1) NOT NULL,         -- 'P'=principal, 'S'=secundario
    orden integer NOT NULL,                                 -- secuencia
    consulta_version smallint NOT NULL,                     -- version de la consulta
    codigo_cie10a character varying(3),                     -- categoria CIE-10
    codigo_cie10b character varying(4),                     -- subcategoria CIE-10
    nombre_cie10 text,                                      -- nombre diagnostico (desnormalizado)
    is_outdated boolean NOT NULL,                           -- true=version anterior
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(10) NOT NULL,
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, tipo_diagnostico, orden, consulta_version)
);
""")

    train_ddl("""
-- Notas de evolucion de trauma. Versionadas con evolucion_version + is_outdated.
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.trauma_consulta_evolucion (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    evolucion text,                                         -- texto de la nota de evolucion
    orden integer NOT NULL,                                 -- secuencia de la nota
    evolucion_version smallint NOT NULL,                    -- version de la evolucion
    is_outdated boolean NOT NULL,                           -- true=version anterior
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(10) NOT NULL,
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden, evolucion_version)
);
""")

    train_ddl("""
-- Preconsulta de trauma: datos del evento traumatico (mecanismo, lugar,
-- alcohol/drogas, seguridad, traslado). Versionada con preconsulta_version + is_outdated.
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
-- Referenciado por: trauma_preconsulta_causa, trauma_preconsulta_prehospitalario
CREATE TABLE public.trauma_preconsulta (
    preconsulta_version integer NOT NULL,                            -- version (autoincremental)
    codigo_establecimiento character varying(16) NOT NULL,           -- hospital
    codigo_asignacion character varying(10) NOT NULL,                -- visita
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(10) NOT NULL,
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    -- Evento
    fecha_evento date,                                               -- fecha del evento traumatico
    hora_evento time without time zone,                              -- hora del evento
    lugar_del_evento smallint,                                       -- 1=Bar, 2=Escuela, 3=Calle, 4=Trabajo, 5=Transp.Particular, 6=Transp.Publico, 7=Otros
    lugar_del_evento_otros character varying(50),                    -- texto libre si lugar=Otros
    codigo_departamento character varying(3),                        -- departamento donde ocurrio el evento
    codigo_distrito character varying(3),                            -- distrito donde ocurrio el evento
    actividad_que_realizaba smallint,                                -- 1=Trab.Dependiente, 2=Independiente, 3=Estudiando, 4=Deporte, 5=Viajando, 6=Alcohol, 7=No Sabe, 8=Otra
    actividad_que_realizaba_otros character varying(50),              -- texto libre si actividad=Otra
    -- Alcohol y drogas
    alcohol_segun_rpta_paciente boolean,                         -- paciente reporta consumo de alcohol
    alcohol_segun_rpta_paciente_comentarios character varying(50),
    alcohol_sospecha_clinica boolean,                            -- sospecha clinica de alcohol
    alcohol_sospecha_clinica_comentarios character varying(50),
    drogas_segun_rpta_paciente boolean,                          -- paciente reporta consumo de drogas
    drogas_segun_rpta_paciente_comentarios character varying(50),
    drogas_sospecha_clinica boolean,                             -- sospecha clinica de drogas
    drogas_sospecha_clinica_comentarios character varying(50),
    -- Motivo y tipo de accidente
    motivo_consulta smallint,                                        -- 1=Acc.transito, 2=Agresion, 3=Autoinfligida, 4=Otros mecanismos, 5=Atencion previa
    tipo_accidente smallint,                                         -- 1=Caida, 2=Choque, 3=Vuelco, 4=Arrollado, 5=Otro, 6=No sabe
    tipo_accidente_otros character varying(50),                    -- texto libre si tipo_accidente=Otro
    accidentado smallint,                                            -- 1=Peaton, 2=Conductor, 3=Pasajero, 4=Otro, 5=No sabe
    accidentado_otros character varying(50),                          -- texto libre si accidentado=Otro
    tipo_transporte smallint,                                        -- 1=Auto, 2=Camioneta, 3=Camion, 4=Omnibus, 5=Moto, 6=Bicicleta, 7=Embarcacion, 8=Carreta, 9=Caballo, 10=Otro, 11=No sabe
    tipo_transporte_otros character varying(50),                      -- texto libre si tipo_transporte=Otro
    -- Elementos de seguridad (booleans: true si se uso el elemento)
    elemento_de_seguridad_cinturon boolean,                          -- cinturon de seguridad
    elemento_de_seguridad_airbag boolean,                            -- airbag
    elemento_de_seguridad_casco boolean,                             -- casco
    elemento_de_seguridad_silla_bebe boolean,                        -- silla de bebe
    elemento_de_seguridad_otros character varying(50),                -- otros elementos (texto libre)
    extricacion boolean,                                             -- requirio extricacion vehicular
    extricacion_descripcion character varying(50),                    -- descripcion de la extricacion
    contraparte smallint,                                            -- 1=Auto, 2=Camioneta, 3=Camion, 4=Omnibus, 5=Moto, 6=Motocargas, 7=Triciclon/Cuatriclon, 8=Bicicleta, 9=Embarcacion, 10=Carreta, 11=Caballo, 12=Peaton, 13=Objeto Fijo, 14=Otro, 15=No sabe
    contraparte_otros character varying(50),                          -- texto libre si contraparte=14(Otro)
    -- Caida
    caida smallint,                                                  -- 1=Mismo Nivel, 2=Silla, 3=Cama, 4=Hamaca, 5=Arbol, 6=Altura, 7=Otros, 8=No sabe
    caida_otros character varying(50),                               -- texto libre si caida=7(Otros)
    caida_metros integer,                                            -- altura de la caida en metros (si caida=6 Altura)
    caida_comentarios character varying(50),                          -- comentarios sobre la caida
    -- Agresion
    tipo_agresion smallint,                                          -- 1=Puno/Patada, 2=Arma Contundente, 3=Arma Blanca, 4=Arma de Fuego, 5=Otros
    tipo_agresion_otros character varying(50),                        -- texto libre si tipo_agresion=5(Otros)
    sexo_del_agresor smallint,                                       -- 1=Masculino, 2=Femenino, 3=Ambos, 4=N/S
    antecedente_previo_agresion smallint,                             -- 1=SI, 2=NO, 3=N/S
    relacion_con_agresor smallint,                                    -- 1=Pareja/Ex Pareja, 2=Padres, 3=Otro Familiar, 4=Conocido, 5=Desconocido
    contexto smallint,                                                -- 1=Pelea, 2=Robo, 3=Agresion Sexual, 4=Pandillas, 5=Violencia Intrafamiliar, 6=Bala Perdida, 7=Otro, 8=No sabe
    contexto_otros character varying(50),                              -- texto libre si contexto=7(Otro)
    lesion_con smallint,                                              -- 1=Arma Blanca, 2=Arma de Fuego, 3=Arma Contusa, 4=Otro
    lesion_con_otros character varying(50),                            -- texto libre si lesion_con=4(Otro)
    antecedente_previo_lesion smallint,                                -- 1=SI, 2=NO, 3=N/S
    -- Envenenamiento
    envenenamiento smallint,                                          -- 1=Medicamento, 2=Alcohol, 3=Plaguicida, 4=Gases y Vapores, 5=Otros
    envenenamiento_otros character varying(50),                        -- texto libre si envenenamiento=5(Otros)
    envenenamiento_accidental smallint,                                -- 1=Medicamento, 2=Alcohol, 3=Plaguicida, 4=Gases y Vapores, 5=Otros
    envenenamiento_accidental_otros character varying(50),              -- texto libre si envenenamiento_accidental=5(Otros)
    factor_precipitante smallint,                                      -- 1=Conflicto Pareja/Familiar, 2=Enfermedad Fisica, 3=Problema Financiero, 4=Problema Judicial, 5=Abuso Sexual, 6=Embarazo no Deseado, 7=Problema Escolar, 8=Otro, 9=No sabe
    factor_precipitante_otros character varying(50),                    -- texto libre si factor_precipitante=8(Otro)
    -- Quemaduras y mordeduras
    quemadura smallint,                                                -- 1=Material Inflamable, 2=Fuego/Llamas, 3=Sustancias Quimicas, 4=Agua Caliente, 5=Petardo, 6=Otros, 7=No sabe
    quemaduras_otros character varying(50),                             -- texto libre si quemadura=6(Otros)
    picaduras_mordeduras smallint,                                     -- 1=Perro, 2=Serpiente, 3=Alacran, 4=Otros, 5=No sabe
    picaduras_mordeduras_otros character varying(50),                   -- texto libre si picaduras_mordeduras=4(Otros)
    otros_mecanismos character varying(50),                             -- otros mecanismos de trauma: texto libre (ej. 'Accidente Deportivo', 'Cuerpo Extrano', 'Aplastamiento', 'Electrocucion')
    otros_mecanismos_observaciones character varying(50),               -- observaciones sobre otros mecanismos
    -- Traslado y atencion previa
    traido_por smallint,                                             -- 1=Ambulancia SEME, 2=Ambulancia Otros, 3=Bombero, 4=Policia, 5=Particular, 6=Otros
    traido_por_observaciones character varying(50),                   -- detalle del traslado
    atencion_previa boolean,                                         -- recibio atencion medica antes de llegar
    procedimiento_prehospitalario_otros character varying(50),       -- otros procedimientos prehospitalarios (texto libre)
    miembros_inmovilizados_cantidad character varying(100),          -- descripcion de miembros inmovilizados
    reanimacion_cardiovascular_basica_minutos smallint,              -- duracion RCP basica (min)
    reanimacion_cardiovascular_avanzada_minutos smallint,            -- duracion RCP avanzada (min)
    torniquete_minutos smallint,                                     -- duracion torniquete (min)
    atencion_hospitalaria character varying(50),                     -- detalle de atencion hospitalaria previa
    trauma_observaciones_finales text,                               -- observaciones finales del caso
    is_outdated boolean,                                             -- true=version anterior
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, preconsulta_version)
);
""")

    train_ddl("""
-- Causas externas CIE-10 asociadas a una preconsulta de trauma.
-- Se une a: trauma_preconsulta via (codigo_establecimiento, codigo_asignacion, preconsulta_version)
-- Se une a: cie10 via (codigo_cie10a, codigo_cie10b)
CREATE TABLE public.trauma_preconsulta_causa (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    orden integer NOT NULL,                                 -- secuencia de causa
    preconsulta_version integer NOT NULL,                   -- version de la preconsulta
    codigo_cie10a character varying(3),                     -- categoria CIE-10 causa externa
    codigo_cie10b character varying(4),                     -- subcategoria CIE-10
    nombre_cie10 text,                                      -- nombre (desnormalizado)
    is_outdated boolean,                                    -- true=version anterior
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden, preconsulta_version)
);
""")

    train_ddl("""
-- Procedimientos prehospitalarios realizados antes de llegar al hospital.
-- Se une a: trauma_preconsulta via (codigo_establecimiento, codigo_asignacion, preconsulta_version)
-- Se une a: procedimiento_prehospitalario.id via codigo_procedimiento_prehospitalario
CREATE TABLE public.trauma_preconsulta_prehospitalario (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    orden integer NOT NULL,
    preconsulta_version smallint NOT NULL,
    codigo_procedimiento_prehospitalario smallint NOT NULL,  -- join procedimiento_prehospitalario.id
    is_outdated boolean NOT NULL,                            -- true=version anterior
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(10) NOT NULL,
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, orden, preconsulta_version)
);
""")

    # -----------------------------------------------------------------
    # Trauma catalogs
    # -----------------------------------------------------------------

    # -----------------------------------------------------------------
    # Prescriptions & dispensing
    # -----------------------------------------------------------------
    print("Adding DDLs for prescriptions & dispensing...")

    train_ddl("""
-- Prescripcion a largo plazo (medicacion cronica). Cabecera con diagnostico y medico.
-- Se une a: consulta via (codigo_establecimiento, codigo_asignacion) (detalle de la consulta)
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion) (detalle de la consulta)
-- Se une a: paciente.codigo_paciente via codigo_paciente
-- Se une a: usuario.codigo_usuario via codigo_medico (medico prescriptor)
-- Se une a: servicio.codigo_servicio via codigo_servicio
-- Se une a: cie10 via (cie10_a, cie10_b) (diagnostico asociado)
-- Referenciado por: long_term_prescription_details, long_term_dispensing_records
CREATE TABLE public.long_term_prescription (
    codigo_establecimiento character varying(20) NOT NULL,
    prescription_id character varying(20) NOT NULL,
    version integer NOT NULL DEFAULT 1,
    codigo_asignacion character varying(20),                  -- consulta donde se creo
    codigo_servicio integer,
    codigo_paciente character varying(20) NOT NULL,
    codigo_medico character varying(20) NOT NULL,             -- medico prescriptor (join usuario)
    cie10_a character varying(10),                            -- categoria CIE-10
    cie10_b character varying(10),                            -- subcategoria CIE-10
    nombre_cie10 character varying(255),                      -- nombre del diagnostico
    duracion_meses integer,                                   -- duracion en meses (2, 3, o 4)
    programada_estado integer,                                -- 1=Preparado, 2=En Progreso, 3=Completado, 4=Cancelado
    reason text,                                              -- razon/motivo
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(50) NOT NULL,
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(50),
    indicaciones text,                                        -- indicaciones generales
    PRIMARY KEY (codigo_establecimiento, prescription_id, version)
);
""")

    train_ddl("""
-- Detalle de cada medicamento en una prescripcion a largo plazo.
-- Se une a: long_term_prescription via (codigo_establecimiento, prescription_id)
-- Se une a: medicamento via (codigo_establecimiento, codigo_medicamento)
CREATE TABLE public.long_term_prescription_details (
    codigo_establecimiento character varying(20) NOT NULL,
    prescription_id character varying(20) NOT NULL,
    codigo_asignacion character varying(20),
    codigo_medicamento bigint NOT NULL,                       -- medicamento (join medicamento)
    version integer NOT NULL DEFAULT 1,
    dosis character varying(50) NOT NULL,
    forma_uso character varying(255) NOT NULL,                -- instrucciones de uso
    dias_uso integer NOT NULL,                                -- dias de tratamiento por entrega
    forma_medicamento character varying(50),                  -- via de administracion
    otro_via character varying(10),
    programada_estado integer,                                -- 1=Preparado, 2=En Progreso, 3=Completado, 4=Cancelado
    numero_total integer NOT NULL,                            -- cantidad total por entrega
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(50) NOT NULL,
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(50),
    PRIMARY KEY (codigo_establecimiento, prescription_id, codigo_medicamento, version)
);
""")

    train_ddl("""
-- Registro de cada dispensacion/retiro de medicamento cronico.
-- Se une a: long_term_prescription via (codigo_establecimiento, prescription_id)
CREATE TABLE public.long_term_dispensing_records (
    codigo_establecimiento character varying(20) NOT NULL,
    prescription_id character varying(20) NOT NULL,
    version integer NOT NULL DEFAULT 1,
    codigo_asignacion character varying(20),                  -- consulta del retiro
    codigo_medicamento character varying(20) NOT NULL,
    cantidad_recetada integer NOT NULL,                       -- cantidad recetada en total (sumando todos los meses)
    cantidad_dispensada integer NOT NULL,                     -- cantidad efectivamente dispensada
    total_retiros integer NOT NULL,                           -- numero total de retiros programados
    entrega_actual integer NOT NULL,                          -- numero de esta entrega (1..total_retiros)
    creacion_fecha date NOT NULL,
    creacion_hora time without time zone NOT NULL,
    creacion_usuario character varying(50) NOT NULL,
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(50),
    PRIMARY KEY (codigo_establecimiento, prescription_id, codigo_medicamento, version)
);
""")

    train_ddl("""
-- Registro de dispensacion de medicamentos sincronizado con SICIAP.
-- Se une a: establecimiento.codigo_establecimiento via codigo_establecimiento
CREATE TABLE public.registro_dispensadas (
    codigo_transaccion integer NOT NULL,                     -- ID de transaccion (autoincremental)
    codigo_establecimiento text NOT NULL,                    -- hospital donde se dispenso
    codigo_asignacion text NOT NULL,                         -- visita/consulta asociada
    codigo_grupo integer NOT NULL,                           -- grupo de prescripcion (mismo que en consulta_medicamento)
    codigo_medicamento integer NOT NULL,                     -- medicamento dispensado
    cantidad_dispensada integer NOT NULL,                    -- cantidad efectivamente entregada al paciente
    creacion_fecha date NOT NULL,                            -- fecha de la dispensacion
    creacion_hora time without time zone NOT NULL,           -- hora de la dispensacion
    creacion_usuario text NOT NULL,                          -- usuario que dispenso (farmaceutico)
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario text,
    sincronizacion_timestamp timestamp without time zone,    -- momento en que se sincronizo con SICIAP
    estado text,                                             -- 'HIS LOCAL FARMACIA'=pendiente sync, 'SINCRONIZADO'=OK, 'STOCK INSUFICIENTE'=error stock, 'NO PROCESADO'=error
    codigo_consumo text,                                     -- codigo de consumo devuelto por SICIAP tras sincronizar
    codigo_sucursal character varying(10),                   -- sucursal del stock de donde se dispenso
    was_retried character varying(1),                        -- 't'=se reintento la sincronizacion, 'f'=primer intento
    siciap_delivered_to character varying(20),               -- destino de la entrega en SICIAP
    es_cronica character varying(1),                         -- 't'=dispensacion de medicacion cronica (long_term)
    PRIMARY KEY (codigo_transaccion, codigo_establecimiento),
    FOREIGN KEY (codigo_establecimiento) REFERENCES establecimiento(codigo_establecimiento)
);
""")

    # -----------------------------------------------------------------
    # Clinical documents: certificado medico
    # -----------------------------------------------------------------
    print("Adding DDLs for clinical documents...")

    # -----------------------------------------------------------------
    # Scheduling: agenda, horario, turno_horario, dia_semana
    # -----------------------------------------------------------------
    print("Adding DDLs for scheduling...")

    train_ddl("""
-- Turnos programados. Cada fila es un turno agendado para un paciente.
-- Se une a: establecimiento, paciente, usuario (via codigo_doctor_asignado), servicio, horario
-- Referenciado por: paciente_asignacion via (agenda_id, codigo_establecimiento)
CREATE TABLE public.agenda (
    agenda_id integer NOT NULL,                              -- ID unico de turno (autoincremental)
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_paciente character varying(20),
    nombre_apellido text,                                     -- nombre (desnormalizado)
    fecha_asignada date,                                     -- fecha programada
    horario_asignado time without time zone,                 -- hora programada
    codigo_doctor_asignado character varying(10),             -- medico (join usuario)
    codigo_servicio numeric,
    codigo_consultorio character varying(4),
    numero_orden_espera integer,
    turno numeric,                                           -- 1=Manana, 2=Tarde, 3=Guardia, 4=Noche, 9=Solo Preconsulta
    estado text NOT NULL,                                     -- 'AGENDADO', 'ADMITIDO', 'CANCELADO', 'REAGENDADO'
    numero_telefono character varying(15),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    hora_inicio_consultorio time without time zone,
    codigo_horario integer,                                   -- (join horario)
    PRIMARY KEY (agenda_id, codigo_establecimiento)
);
""")

    train_ddl("""
-- Horario de atencion de un medico en un servicio/consultorio.
-- Se une a: establecimiento, usuario (codigo_medico), servicio, dia_semana, turno_horario
CREATE TABLE public.horario (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_medico character varying(10) NOT NULL,             -- medico (join usuario)
    codigo_servicio numeric NOT NULL,
    codigo_dia_semana numeric(1,0) NOT NULL,                  -- dia (join dia_semana)
    codigo_consultorio character varying(4) NOT NULL,
    hora_inicio time without time zone NOT NULL,
    hora_fin time without time zone,
    activo character varying(1) NOT NULL,
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    codigo_horario integer NOT NULL,                          -- PK autoincremental
    codigo_turno numeric NOT NULL,                            -- turno (join turno_horario)
    bloquea_historial boolean DEFAULT false,                  -- bloquea acceso al historial
    periodo_agenda smallint DEFAULT 10,                       -- minutos por slot de agenda
    PRIMARY KEY (codigo_horario, codigo_establecimiento)
);
""")

    train_ddl("""
-- Catalogo de dias de la semana.
-- Referenciado por: horario.codigo_dia_semana
CREATE TABLE public.dia_semana (
    codigo_dia_semana numeric(1,0) NOT NULL PRIMARY KEY,
    nombre_dia_semana text NOT NULL,
    abreviatura character varying(3),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone
);
""")

    # -----------------------------------------------------------------
    # Lab / imaging / procedure catalogs
    # -----------------------------------------------------------------
    print("Adding DDLs for lab/imaging/procedure catalogs...")

    train_ddl("""
-- Admision/agendamiento de un procedimiento.
-- Se une a: paciente_asignacion via (codigo_establecimiento, codigo_asignacion)
CREATE TABLE public.procedimiento_admision (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_procedimiento character varying(9) NOT NULL,
    secuencia_numero integer NOT NULL,
    agenda_fecha date NOT NULL,                               -- fecha agendada
    estado character varying(1),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    version integer NOT NULL DEFAULT 1,
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_procedimiento, secuencia_numero, agenda_fecha, version)
);
""")

    train_ddl("""
-- Resultado de un procedimiento (valor individual dentro de un estudio).
CREATE TABLE public.procedimiento_resultado (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_procedimiento character varying(9) NOT NULL,
    secuencia_numero integer NOT NULL,
    agenda_fecha date NOT NULL,
    order_resultado integer NOT NULL,
    valor_procedimiento text,                                 -- valor del resultado
    estado character varying(1),
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    version integer NOT NULL DEFAULT 1,
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_procedimiento, secuencia_numero, agenda_fecha, order_resultado, version)
);
""")

    train_ddl("""
-- Formulario/orden de un procedimiento.
CREATE TABLE public.procedimiento_formulario (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_asignacion character varying(10) NOT NULL,
    codigo_procedimiento character varying(9) NOT NULL,
    secuencia_numero integer NOT NULL,
    orden_estado character varying(1),                        -- estado de la orden
    creacion_fecha date,
    creacion_hora time without time zone,
    creacion_usuario character varying(10),
    modificacion_fecha date,
    modificacion_hora time without time zone,
    modificacion_usuario character varying(10),
    version integer NOT NULL DEFAULT 1,
    PRIMARY KEY (codigo_establecimiento, codigo_asignacion, codigo_procedimiento, secuencia_numero, version)
);
""")

    # -----------------------------------------------------------------
    # Clinical history: ficha clinica
    # -----------------------------------------------------------------

    train_ddl("""
-- Registros de historia clinica personal por paciente (antecedentes, alergias, etc.).
-- Se une a: ficha_clinicas_item, paciente
-- Versionada: is_outdated=true marca versiones anteriores.
CREATE TABLE public.ficha_clinicas_personal (
    codigo_establecimiento character varying(16) NOT NULL,
    codigo_paciente character varying(32) NOT NULL,
    codigo_ficha_clinicas smallint NOT NULL,                  -- tipo de ficha (join ficha_clinicas_item)
    orden integer NOT NULL,                                   -- incrementa en uno cada vez que se guarda
    descripcion text NOT NULL,                                -- contenido texto libre
    is_outdated boolean NOT NULL DEFAULT false,
    creacion_fecha date NOT NULL DEFAULT CURRENT_DATE,
    creacion_hora time without time zone NOT NULL DEFAULT CURRENT_TIME,
    creacion_usuario character varying(10) NOT NULL,
    codigo_asignacion character varying(10),                  -- visita donde se registro (opcional)
    PRIMARY KEY (codigo_establecimiento, codigo_paciente, codigo_ficha_clinicas, orden),
    FOREIGN KEY (codigo_ficha_clinicas) REFERENCES ficha_clinicas_item(codigo_ficha_clinicas)
);
""")
    print()

# =========================================================================
# Business documentation
# =========================================================================

def _populate_docs() -> None:
    """Business documentation for the ambulatoria domain."""
    print("Adding documentation for ambulatoria domain...")

    train_doc(
        "FLUJO DE UNA VISITA AMBULATORIA: "
        "1) Se crea paciente_asignacion cuando el paciente obtiene un turno (via agenda o admision directa). "
        "2) preconsulta se registra en triaje (enfermeria) con signos vitales antes de ver al medico; "
        "la PK incluye creacion_fecha, permitiendo multiples preconsultas por visita. "
        "3) consulta se crea cuando el medico abre la visita; es 1:1 con paciente_asignacion. "
        "4) consulta_diagnostico, consulta_medicamento, consulta_procedimiento "
        "se agregan durante la consulta. "
        "5) Para trauma, se usan trauma_preconsulta y trauma_consulta en vez de preconsulta/consulta normales. "
    )

    train_doc(
        "La tabla consulta contiene el registro medico de una visita ambulatoria. "
        "El campo derivar indica el destino del paciente: '0'=No aplica, '1'=Se refiere, "
        "'2'=Internacion, '3'=Domicilio, '4'=Fuga/No se realizo, '5'=Muerte, "
        "'6'=Incompleto(Re-Evaluar), '7'=Incompleto(Reasignar). "
        "tipo_observacion indica estado de procedimiento: 'S'=Solicitado, 'R'=Realizado, "
        "'H'=Solicitado+Iniciar hoy. "
        "Para datos neonatales: peso_nacimiento, edad_gestacional, fecha_nacimiento_nino."
    )

    train_doc(
        "La tabla preconsulta contiene datos de triaje registrados por enfermeria. "
        "Incluye signos vitales (presion arterial, pulso, frecuencia respiratoria, "
        "temperatura, saturacion de oxigeno), medidas antropometricas (peso, talla, IMC, "
        "circunferencia abdominal), datos pediatricos (percentiles, perimetro craneal, "
        "escala de Tanner, desarrollo madurativo), y estado nutricional. "
        "estado_nutricional: '0'=Normal, '1'=Riesgo desnutricion, '2'=Desnutricion Moderada, "
        "'3'=Desnutricion Grave, '4'=Sobrepeso, '5'=Obesidad."
    )

    train_doc(
        "SCORES DE TRAUMA en trauma_consulta: "
        "Glasgow Coma Scale (GCS): apertura_ocular (1-4) + respuesta_verbal (1-5) + respuesta_motora (1-6) = total_glassgow (3-15). "
        "Escala Revisada de Trauma (RTS): frecuencia_respiratoria_escala + presion_sistolica + escala_glasgow = total_escala_revisada. "
        "Indice Pediatrico de Trauma (IPT): peso_rts_ipt_pediatrico + via_aerea + ta + snc + heridas + fracturas. "
        "MESS (extremidad mutilada): lesion + isquemia + choque + edad = total_mess (>=7 indica amputacion probable). "
        "AIS: ais_cabeza/cara/torax/abdomen/extremidad/externa (0-6); ISS = sum of squares of 3 highest AIS. "
        "TRISS: combina RTS (triss_rts), ISS (triss_iss) y tipo_trauma (0=cerrado, 1=penetrante) "
        "para calcular prob_sobrevida_cerrado y prob_sobrevida_penetrante."
    )

    train_doc(
        "VERSIONADO EN TRAUMA: trauma_consulta, trauma_preconsulta, trauma_consulta_diagnostico, "
        "trauma_consulta_evolucion, trauma_preconsulta_causa, trauma_preconsulta_prehospitalario "
        "usan versionado con is_outdated. Cada edicion crea una nueva version; "
        "la version anterior se marca con is_outdated=true. "
        "Para obtener la version vigente: filtrar con is_outdated=false (o is_outdated IS DISTINCT FROM true)."
    )

    train_doc(
        "MODELO DE AGENDA Y HORARIOS: "
        "horario define disponibilidad de un medico por dia/servicio/consultorio con periodo_agenda (minutos por slot, default 10). "
        "agenda registra turnos: estado fluye 'AGENDADO' -> 'ADMITIDO' (paciente llego) -> 'CANCELADO'/'REAGENDADO'. "
        "turno en agenda: 1=Manana, 2=Tarde, 3=Guardia, 4=Noche, 9=Solo Preconsulta."
    )

    train_doc(
        "PRESCRIPCIONES A LARGO PLAZO — FLUJO DE ESTADOS: "
        "programada_estado fluye: 1=Preparado -> 2=En Progreso (al dispensar primer retiro) -> 3=Completado (todos los retiros hechos). "
        "Se puede cancelar en cualquier momento (4=Cancelado). "
        "long_term_dispensing_records registra cada retiro: entrega_actual (1..total_retiros). "
        "registro_dispensadas sincroniza con SICIAP; su campo estado indica si la sincronizacion fue exitosa o fallo: "
        "'HIS LOCAL FARMACIA'=pendiente, 'SINCRONIZADO'=OK, 'STOCK INSUFICIENTE'=error, 'NO PROCESADO'=error."
    )

    train_doc(
        "CATALOGOS DE PROCEDIMIENTOS — FLUJO: "
        "consulta_procedimiento.codigo_procedimiento une a examen_laboratorial (codigos numericos ej. '00101') "
        "o a cie9 (codigos con punto ej. '00.F9', '87.04') para procedimientos medicos CIE-9. "
        "reporttag='Y' indica estudio (lab/imagen), 'N' indica procedimiento. "
        "procedimiento_admision -> procedimiento_formulario -> procedimiento_resultado "
        "manejan el workflow de agendamiento, orden y resultado de estudios."
    )

    train_doc(
        "FICHA CLINICAS: ficha_clinicas_personal almacena antecedentes por paciente (no por visita). "
        "Cada registro tiene un tipo (ficha_clinicas_item): 1=Motivo Consulta, 2=Historia Actual, "
        "3=Antecedentes Medicos, 4=Quirurgicos, 5=Neonatales, 6=Familiares, 7=Historia Social, "
        "8=Habitos, 9=Alergias, 10=Medicamentos, 11=Inmunizaciones. "
        "is_outdated=true marca versiones anteriores; para datos vigentes filtrar is_outdated=false."
    )

    train_doc(
        "CERTIFICADO MEDICO: certificado_medico registra certificados de reposo medico. "
        "tipo_dolencia: 1=Comun, 2=Profesional, 3=Accidente de Trabajo. "
        "es_primer_reposo indica si es el primer certificado o una extension. "
        "Incluye diagnostico CIE-10, dias de reposo, y periodo (desde_fecha, hasta_fecha)."
    )

    train_doc(
        "FILTROS DE REGISTROS ACTIVOS — cada tabla usa una convencion distinta para marcar eliminados/inactivos: "
        "consulta_medicamento: isdc IS DISTINCT FROM 'S' AND (estado IS NULL OR estado != 'Eliminado'). "
        "consulta_procedimiento: isdc IS DISTINCT FROM 'S'. "
        "trauma_consulta, trauma_preconsulta y sus tablas hijas: is_outdated = false. "
        "ficha_clinicas_personal: is_outdated = false. "
        "long_term_prescription cancelada: programada_estado = 4. "
        "Siempre aplicar estos filtros a menos que se pida explicitamente incluir eliminados/cancelados."
    )

    print()

# =========================================================================
# Question-SQL examples
# =========================================================================

def _populate_examples() -> None:
    """Question-SQL pairs for the ambulatoria domain."""
    print("Adding question-SQL examples for ambulatoria domain...")

    # -----------------------------------------------------------------
    # Simple single-table queries
    # -----------------------------------------------------------------

    train_example(
        "Cuantas consultas hubo el mes pasado?",
        "SELECT SUM(total_consultas) FROM dbt_analytics.mart_totales_consultas_por_tipo "
        "WHERE fecha_consulta >= date_trunc('month', CURRENT_DATE - INTERVAL '1 month') "
        "AND fecha_consulta < date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantos pacientes distintos fueron atendidos este anho?",
        "SELECT COUNT(DISTINCT codigo_paciente) FROM dbt_analytics.mart_consultas "
        "WHERE fecha_consulta >= date_trunc('year', CURRENT_DATE);"
    )

    train_example(
        "Cuantas preconsultas se registraron hoy?",
        "SELECT COUNT(*) FROM dbt_analytics.mart_signos_vitales WHERE fecha_triaje = CURRENT_DATE;"
    )

    train_example(
        "Cuantos casos de trauma hubo este anho?",
        "SELECT COUNT(*) FROM trauma_consulta "
        "WHERE is_outdated = false AND creacion_fecha >= date_trunc('year', CURRENT_DATE);"
    )

    train_example(
        "Cuantas preconsultas de trauma se registraron este mes?",
        "SELECT COUNT(*) FROM trauma_preconsulta "
        "WHERE is_outdated IS DISTINCT FROM true "
        "AND creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantas prescripciones a largo plazo estan activas?",
        "SELECT COUNT(*) FROM long_term_prescription WHERE programada_estado = 2;"
    )

    train_example(
        "Cuantos certificados medicos se emitieron este mes?",
        "SELECT COUNT(*) FROM certificado_medico "
        "WHERE creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantos procedimientos activos se realizaron este mes?",
        "SELECT COUNT(*) FROM consulta_procedimiento "
        "WHERE isdc IS DISTINCT FROM 'S' "
        "AND creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    # -----------------------------------------------------------------
    # Top-N queries
    # -----------------------------------------------------------------

    train_example(
        "Cuales son los 10 diagnosticos mas frecuentes?",
        "SELECT diagnostico, COUNT(*) AS cantidad "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "GROUP BY diagnostico ORDER BY cantidad DESC LIMIT 10;"
    )

    train_example(
        "Cuales son los medicamentos mas recetados? Mostrar nombre del medicamento",
        "SELECT medicamento, COUNT(*) AS veces_recetado "
        "FROM dbt_analytics.mart_medicamentos_recetados "
        "GROUP BY medicamento ORDER BY veces_recetado DESC LIMIT 10;"
    )

    train_example(
        "Cuales son los 10 servicios con mas consultas este mes?",
        "SELECT servicio, COUNT(*) AS total "
        "FROM dbt_analytics.mart_consultas "
        "WHERE fecha_consulta >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY servicio ORDER BY total DESC LIMIT 10;"
    )

    train_example(
        "Cuales son los 5 examenes de laboratorio mas solicitados?",
        "SELECT el.nombre_examen, COUNT(*) AS cantidad "
        "FROM consulta_procedimiento cp "
        "JOIN examen_laboratorial el ON cp.codigo_procedimiento = el.codigo_examen "
        "WHERE cp.isdc IS DISTINCT FROM 'S' "
        "GROUP BY el.nombre_examen ORDER BY cantidad DESC LIMIT 5;"
    )

    train_example(
        "Cuales son los procedimientos (no laboratorio) mas realizados?",
        "SELECT c9.nombre_procedimiento, COUNT(*) AS cantidad "
        "FROM consulta_procedimiento cp "
        "JOIN cie9 c9 ON cp.codigo_procedimiento = c9.codigo_procedimiento "
        "WHERE cp.isdc IS DISTINCT FROM 'S' "
        "GROUP BY c9.nombre_procedimiento ORDER BY cantidad DESC LIMIT 10;"
    )

    # -----------------------------------------------------------------
    # JOIN queries with reference tables
    # -----------------------------------------------------------------

    train_example(
        "Cuantas consultas hizo cada medico este mes? Mostrar nombre del medico",
        "SELECT medico, COUNT(*) AS total_consultas "
        "FROM dbt_analytics.mart_consultas "
        "WHERE fecha_consulta >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY medico ORDER BY total_consultas DESC;"
    )

    train_example(
        "Cuantos pacientes por departamento fueron atendidos este anho?",
        "SELECT departamento_residencia, COUNT(DISTINCT codigo_paciente) AS total_pacientes "
        "FROM dbt_analytics.mart_consultas "
        "WHERE fecha_consulta >= date_trunc('year', CURRENT_DATE) "
        "GROUP BY departamento_residencia ORDER BY total_pacientes DESC;"
    )

    train_example(
        "Cuantos pacientes fueron atendidos hoy en el hospital regional central?",
        "SELECT COUNT(DISTINCT codigo_paciente) "
        "FROM dbt_analytics.mart_consultas "
        "WHERE fecha_consulta = CURRENT_DATE "
        "AND hospital ILIKE '%central%';"
    )

    train_example(
        "Cuantas consultas hubo este mes por establecimiento? Mostrar nombre del hospital",
        "SELECT hospital, SUM(total_consultas) AS total "
        "FROM dbt_analytics.mart_totales_consultas_por_tipo "
        "WHERE fecha_consulta >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY hospital ORDER BY total DESC;"
    )

    # -----------------------------------------------------------------
    # CIE-10 hierarchy queries
    # -----------------------------------------------------------------

    train_example(
        "Cuales son los capitulos CIE-10 con mas diagnosticos registrados?",
        "SELECT capitulo_cie10, COUNT(*) AS cantidad "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "GROUP BY capitulo_cie10 ORDER BY cantidad DESC LIMIT 10;"
    )

    train_example(
        "Cuantos casos de dengue hay desde julio de este año desglosado por region?",
        "SELECT region, COUNT(DISTINCT codigo_paciente) AS total_pacientes "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "WHERE diagnostico ILIKE '%dengue%' "
        "AND fecha_consulta >= make_date(extract(year from current_date)::int, 7, 1) "
        "GROUP BY region ORDER BY total_pacientes DESC;"
    )

    train_example(
        "Cuantos casos de dengue hay desglosado por region de residencia del paciente?",
        "SELECT region_residencia, COUNT(DISTINCT codigo_paciente) AS total_pacientes "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "WHERE diagnostico ILIKE '%dengue%' "
        "AND fecha_consulta >= make_date(extract(year from current_date)::int, 7, 1) "
        "GROUP BY region_residencia ORDER BY total_pacientes DESC;"
    )

    train_example(
        "Listar los hospitales de la region Capital que tienen pacientes con dengue desde julio de este año",
        "SELECT DISTINCT hospital "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "WHERE diagnostico ILIKE '%dengue%' "
        "AND region ILIKE '%CAPITAL%' "
        "AND fecha_consulta >= make_date(extract(year from current_date)::int, 7, 1) "
        "LIMIT 500;"
    )

    train_example(
        "Plase list out the hospitals in Capital region that has the degue patients from this year July till today",
        "SELECT DISTINCT hospital "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "WHERE diagnostico ILIKE '%dengue%' "
        "AND region ILIKE '%CAPITAL%' "
        "AND fecha_consulta >= make_date(extract(year from current_date)::int, 7, 1) "
        "LIMIT 500;"
    )


    train_example(
        "Cuales son los grupos CIE-10 mas frecuentes en diagnosticos?",
        "SELECT grupo_cie10, COUNT(*) AS cantidad "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "GROUP BY grupo_cie10 ORDER BY cantidad DESC LIMIT 10;"
    )

    # -----------------------------------------------------------------
    # Enfermedades Crónicas (Sin filtro de fecha)
    # -----------------------------------------------------------------

    train_example(
        "Cual es el porcentaje de pacientes con enfermedades cronicas a nivel nacional?",
        "SELECT ROUND((COUNT(DISTINCT d.codigo_paciente)::numeric / (SELECT COUNT(DISTINCT codigo_paciente) FROM dbt_analytics.mart_pacientes_detalle)) * 100, 2) AS porcentaje_cronicos "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios d "
        "WHERE d.tipo_diagnostico = 'Crónico' "
        "OR d.diagnostico ILIKE '%crónic%' "
        "OR d.diagnostico ILIKE '%diabetes%' "
        "OR d.diagnostico ILIKE '%hipertensi%' "
        "OR d.diagnostico ILIKE '%asma%' "
        "OR d.diagnostico ILIKE '%epoc%';"
    )

    train_example(
        "Que porcentaje de los pacientes tienen alguna enfermedad cronica?",
        "SELECT ROUND((COUNT(DISTINCT d.codigo_paciente)::numeric / (SELECT COUNT(DISTINCT codigo_paciente) FROM dbt_analytics.mart_pacientes_detalle)) * 100, 2) AS porcentaje_cronicos "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios d "
        "WHERE d.tipo_diagnostico = 'Crónico' "
        "OR d.diagnostico ILIKE '%crónic%' "
        "OR d.diagnostico ILIKE '%diabetes%' "
        "OR d.diagnostico ILIKE '%hipertensi%' "
        "OR d.diagnostico ILIKE '%asma%' "
        "OR d.diagnostico ILIKE '%epoc%';"
    )

    # -----------------------------------------------------------------
    # Patient demographics
    # -----------------------------------------------------------------

    train_example(
        "Cuantos pacientes masculinos y femeninos fueron atendidos este mes?",
        "SELECT sexo_paciente, COUNT(DISTINCT codigo_paciente) AS total "
        "FROM dbt_analytics.mart_consultas "
        "WHERE fecha_consulta >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY sexo_paciente;"
    )

    train_example(
        "Cuantos pacientes atendidos este anho tienen seguro IPS?",
        "SELECT COUNT(DISTINCT pa.codigo_paciente) "
        "FROM paciente_asignacion pa "
        "WHERE pa.consulta_fecha >= date_trunc('year', CURRENT_DATE) "
        "AND pa.status_ips = true;"
    )

    train_example(
        "Distribucion de pacientes por etnia atendidos este anho",
        "SELECT e.nombre_etnia, COUNT(DISTINCT pa.codigo_paciente) AS total "
        "FROM paciente_asignacion pa "
        "JOIN paciente p ON pa.codigo_paciente = p.codigo_paciente "
        "JOIN etnia e ON p.codigo_etnia = e.codigo_etnia "
        "WHERE pa.consulta_fecha >= date_trunc('year', CURRENT_DATE) "
        "GROUP BY e.nombre_etnia ORDER BY total DESC;"
    )

    train_example(
        "Cuantos pacientes menores de 5 anhos fueron atendidos este mes?",
        "SELECT COUNT(DISTINCT pa.codigo_paciente) "
        "FROM paciente_asignacion pa "
        "WHERE pa.consulta_fecha >= date_trunc('month', CURRENT_DATE) "
        "AND pa.tipo_edad = 1 AND pa.edad_paciente < 5;"
    )

    train_example(
        "Distribucion de pacientes atendidos este mes por rango de edad",
        "SELECT CASE "
        "WHEN pa.tipo_edad = 1 AND pa.edad_paciente < 6 THEN '0-5 anhos' "
        "WHEN pa.tipo_edad = 1 AND pa.edad_paciente BETWEEN 6 AND 17 THEN '6-17 anhos' "
        "WHEN pa.tipo_edad = 1 AND pa.edad_paciente BETWEEN 18 AND 64 THEN '18-64 anhos' "
        "WHEN pa.tipo_edad = 1 AND pa.edad_paciente >= 65 THEN '65+ anhos' "
        "ELSE 'Menor de 1 anho' END AS rango_edad, "
        "COUNT(DISTINCT pa.codigo_paciente) AS total "
        "FROM paciente_asignacion pa "
        "WHERE pa.consulta_fecha >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY rango_edad ORDER BY total DESC;"
    )

    # -----------------------------------------------------------------
    # State filters & cancellations
    # -----------------------------------------------------------------

    train_example(
        "Cuantos turnos de agenda fueron cancelados este mes?",
        "SELECT COUNT(*) FROM agenda "
        "WHERE estado = 'CANCELADO' "
        "AND fecha_asignada >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantos pacientes con diagnostico nuevo se registraron este mes?",
        "SELECT COUNT(DISTINCT codigo_asignacion) "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "WHERE diagnostico_nuevo = 'Nuevo' "
        "AND fecha_consulta >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantas consultas por tipo de consulta este anho?",
        "SELECT tipo_consulta, COUNT(*) AS cantidad "
        "FROM dbt_analytics.mart_totales_consultas_por_tipo "
        "WHERE fecha_consulta >= date_trunc('year', CURRENT_DATE) "
        "GROUP BY tipo_consulta ORDER BY cantidad DESC;"
    )

    # -----------------------------------------------------------------
    # Text search
    # -----------------------------------------------------------------

    train_example(
        "Buscar diagnosticos que contengan la palabra 'diabetes'",
        "SELECT DISTINCT nombre_cie10 FROM cie10 "
        "WHERE nombre_cie10 ILIKE '%diabetes%' LIMIT 20;"
    )

    train_example(
        "Buscar establecimientos que contengan 'regional' en el nombre",
        "SELECT codigo_establecimiento, nombre_establecimiento "
        "FROM establecimiento "
        "WHERE nombre_establecimiento ILIKE '%regional%';"
    )

    train_example(
        "Cuantas consultas tuvieron diagnostico de diabetes este anho?",
        "SELECT COUNT(DISTINCT codigo_asignacion) "
        "FROM dbt_analytics.mart_diagnosticos_ambulatorios "
        "WHERE diagnostico ILIKE '%diabetes%' "
        "AND fecha_consulta >= date_trunc('year', CURRENT_DATE);"
    )

    # -----------------------------------------------------------------
    # Trauma-specific
    # -----------------------------------------------------------------

    train_example(
        "Cual es el promedio del Glasgow Coma Scale en trauma?",
        "SELECT AVG(total_glassgow) AS promedio_glasgow "
        "FROM trauma_consulta "
        "WHERE total_glassgow IS NOT NULL AND is_outdated = false;"
    )

    train_example(
        "Cuantos casos de trauma por tipo de motivo este anho?",
        "SELECT motivo_consulta, COUNT(*) AS cantidad "
        "FROM trauma_preconsulta "
        "WHERE is_outdated IS DISTINCT FROM true "
        "AND creacion_fecha >= date_trunc('year', CURRENT_DATE) "
        "GROUP BY motivo_consulta ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuantos accidentes de transito hubo este anho?",
        "SELECT COUNT(*) FROM trauma_preconsulta "
        "WHERE motivo_consulta = 1 "
        "AND is_outdated IS DISTINCT FROM true "
        "AND creacion_fecha >= date_trunc('year', CURRENT_DATE);"
    )

    train_example(
        "Cual es el score MESS promedio en trauma de extremidades?",
        "SELECT AVG(total_mess) AS promedio_mess "
        "FROM trauma_consulta "
        "WHERE total_mess IS NOT NULL AND is_outdated = false;"
    )

    train_example(
        "Cuantos procedimientos prehospitalarios se realizaron por tipo?",
        "SELECT pp.nombre_procedimiento, COUNT(*) AS cantidad "
        "FROM trauma_preconsulta_prehospitalario tpp "
        "JOIN procedimiento_prehospitalario pp ON tpp.codigo_procedimiento_prehospitalario = pp.id "
        "WHERE tpp.is_outdated = false "
        "GROUP BY pp.nombre_procedimiento ORDER BY cantidad DESC;"
    )

    train_example(
        "Cual es el promedio de superficie corporal quemada en pacientes con quemaduras?",
        "SELECT AVG(scq_valor) AS promedio_scq, MAX(scq_valor) AS max_scq "
        "FROM trauma_consulta "
        "WHERE scq_valor IS NOT NULL AND scq_valor > 0 AND is_outdated = false;"
    )

    # -----------------------------------------------------------------
    # Prescriptions & dispensing
    # -----------------------------------------------------------------

    train_example(
        "Cuantas prescripciones a largo plazo fueron completadas vs canceladas?",
        "SELECT CASE programada_estado "
        "WHEN 1 THEN 'Preparado' WHEN 2 THEN 'En Progreso' "
        "WHEN 3 THEN 'Completado' WHEN 4 THEN 'Cancelado' END AS estado, "
        "COUNT(*) AS cantidad "
        "FROM long_term_prescription "
        "GROUP BY programada_estado ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuantos retiros de medicamentos cronicos se hicieron este mes?",
        "SELECT COUNT(*) FROM long_term_dispensing_records "
        "WHERE creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantas dispensaciones de medicamentos se sincronizaron con SICIAP?",
        "SELECT estado, COUNT(*) AS cantidad "
        "FROM registro_dispensadas "
        "GROUP BY estado ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuantos retiros de medicacion cronica se completaron vs pendientes?",
        "SELECT CASE WHEN ldr.entrega_actual >= ldr.total_retiros THEN 'Completado' "
        "ELSE 'Pendiente' END AS estado_retiro, COUNT(*) AS cantidad "
        "FROM long_term_dispensing_records ldr "
        "GROUP BY estado_retiro;"
    )

    train_example(
        "Cuales son los medicamentos mas recetados en prescripciones a largo plazo?",
        "SELECT m.nombre_producto, COUNT(*) AS cantidad "
        "FROM long_term_prescription_details ltd "
        "JOIN long_term_prescription ltp ON ltd.codigo_establecimiento = ltp.codigo_establecimiento "
        "AND ltd.prescription_id = ltp.prescription_id "
        "JOIN medicamento m ON ltd.codigo_establecimiento = m.codigo_establecimiento "
        "AND ltd.codigo_medicamento = m.codigo_medicamento "
        "WHERE ltp.programada_estado != 4 "
        "GROUP BY m.nombre_producto ORDER BY cantidad DESC LIMIT 10;"
    )

    # -----------------------------------------------------------------
    # Agenda & scheduling
    # -----------------------------------------------------------------

    train_example(
        "Cuantos turnos agendados hay para manana?",
        "SELECT COUNT(*) FROM agenda "
        "WHERE fecha_asignada = CURRENT_DATE + 1 "
        "AND estado = 'AGENDADO';"
    )

    train_example(
        "Cuantos turnos por estado de agenda este mes?",
        "SELECT estado, COUNT(*) AS cantidad FROM agenda "
        "WHERE fecha_asignada >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY estado ORDER BY cantidad DESC;"
    )

    # -----------------------------------------------------------------
    # Waiting room & procedures per visit
    # -----------------------------------------------------------------

    train_example(
        "Cuantos pacientes estan en cada estado en la sala de espera ahora?",
        "SELECT ppe.descripcion, COUNT(*) AS cantidad "
        "FROM pantalla_paciente pp "
        "JOIN pantalla_paciente_estado ppe ON pp.estado = ppe.codigo_estado "
        "JOIN paciente_asignacion pa ON pp.codigo_establecimiento = pa.codigo_establecimiento "
        "AND pp.codigo_asignacion = pa.codigo_asignacion "
        "WHERE pa.consulta_fecha = CURRENT_DATE "
        "GROUP BY ppe.descripcion ORDER BY cantidad DESC;"
    )

    train_example(
        "Cuantos procedimientos se realizaron por consulta en promedio?",
        "SELECT AVG(proc_count) AS promedio_procedimientos FROM ("
        "SELECT codigo_establecimiento, codigo_asignacion, COUNT(*) AS proc_count "
        "FROM consulta_procedimiento WHERE isdc IS DISTINCT FROM 'S' "
        "GROUP BY codigo_establecimiento, codigo_asignacion) sub;"
    )

    # -----------------------------------------------------------------
    # Vitals & clinical data
    # -----------------------------------------------------------------

    train_example(
        "Cual es el promedio de presion arterial sistolica en preconsultas de este mes?",
        "SELECT AVG(presion_arterial_sis) AS promedio_sistolica "
        "FROM preconsulta "
        "WHERE presion_arterial_sis IS NOT NULL "
        "AND creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cual es el IMC promedio de los pacientes atendidos este mes?",
        "SELECT AVG(indice_masa_corporal) AS imc_promedio "
        "FROM preconsulta "
        "WHERE indice_masa_corporal IS NOT NULL "
        "AND creacion_fecha >= date_trunc('month', CURRENT_DATE);"
    )

    train_example(
        "Cuantos pacientes fueron referidos a otro establecimiento este anho?",
        "SELECT COUNT(*) FROM paciente_asignacion "
        "WHERE referido IS NOT NULL AND referido != '0' "
        "AND consulta_fecha >= date_trunc('year', CURRENT_DATE);"
    )

    train_example(
        "Cuantas consultas por hora del dia este mes?",
        "SELECT EXTRACT(HOUR FROM c.creacion_hora) AS hora, COUNT(*) AS total "
        "FROM consulta c "
        "WHERE c.creacion_fecha >= date_trunc('month', CURRENT_DATE) "
        "GROUP BY hora ORDER BY hora;"
    )

    # -----------------------------------------------------------------
    # Certificados, ficha clinica, stock
    # -----------------------------------------------------------------

    train_example(
        "Cuantos certificados medicos se emitieron por tipo de dolencia?",
        "SELECT CASE tipo_dolencia "
        "WHEN 1 THEN 'Comun' WHEN 2 THEN 'Profesional' WHEN 3 THEN 'Accidente de Trabajo' END AS tipo, "
        "COUNT(*) AS cantidad "
        "FROM certificado_medico GROUP BY tipo_dolencia;"
    )

    train_example(
        "Cuantos registros de antecedentes medicos hay por tipo de ficha?",
        "SELECT fci.nombre_ficha_clinicas, COUNT(*) AS cantidad "
        "FROM ficha_clinicas_personal fcp "
        "JOIN ficha_clinicas_item fci ON fcp.codigo_ficha_clinicas = fci.codigo_ficha_clinicas "
        "WHERE fcp.is_outdated = false "
        "GROUP BY fci.nombre_ficha_clinicas ORDER BY cantidad DESC;"
    )

    train_example(
        "Listar profesionales activos con su especialidad y numero de registro",
        "SELECT u.nombres || ' ' || u.apellidos AS nombre, "
        "p.numero_registro, p.codigo_especialidad, p.title "
        "FROM profesional p "
        "JOIN usuario u ON p.codigo_medico = u.codigo_usuario "
        "WHERE p.activo = '1';"
    )

    train_example(
        "Cuales medicamentos tienen stock por debajo del nivel de alerta?",
        "SELECT nombre_producto, stock_actual, stock_alerta, codigo_establecimiento "
        "FROM medicamento "
        "WHERE stock_actual < stock_alerta AND stock_alerta IS NOT NULL "
        "AND codigo_estado = '1' "
        "ORDER BY (stock_alerta - stock_actual) DESC LIMIT 20;"
    )

    print()
