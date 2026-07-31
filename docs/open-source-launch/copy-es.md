# Textos de publicación en español

Los textos ya incluyen el nombre **HireSense** y sus enlaces públicos:

- Repositorio: <https://github.com/StevSant/HireSense>
- Demo pública: <https://hiresense-demo.vercel.app>
- Arquitectura: <https://github.com/StevSant/HireSense/blob/main/backend/ARCHITECTURE.md>

La demo pública funciona solo en el frontend, es de solo lectura y utiliza datos
sintéticos. No requiere una cuenta y se puede compartir públicamente.

No publiques cifras sobre rendimiento, fuentes o pruebas sin verificarlas justo antes.

## Novedades (verificadas al 2026-07-31)

Material fresco para los anuncios. Nombra funciones, nunca cantidades sin comprobar.

- **Discover de oportunidades.** Nuevo contexto `/opportunities`: conferencias, CFPs
  (convocatorias de ponencias) y programas financiados, desde confs.tech e importaciones
  curadas. Filtros por tema, país, fecha límite y “solo financiados”, orden por relevancia
  contra tu perfil y etiquetas de costo (`Gratis`, `Financiado`, `De pago`,
  `Probablemente de pago`) incluso cuando la fuente no publica el precio.
- **Fuentes nuevas automatizadas:** Dice (MCP oficial), Y Combinator Work at a Startup
  (JSON público) y CrunchBoard (RSS oficial).
- **Importación opcional y respetuosa de ToS** para Indeed, Wellfound, Glassdoor y Monster,
  que no tienen una API pública utilizable. Sin saltarse muros de bots ni logins.
- **Portales de empresa:** adaptadores para Workday, Thoughtworks y Globant, un detector
  `auto` que elige el ATS correcto desde la URL de carreras, y un scraper genérico con
  render de navegador para sitios con mucho JavaScript.
- **Transparencia de fuentes:** registro de capacidades por fuente
  (`GET /ingestion/sources`) y salud por fuente con última ejecución, conteos y errores
  (`GET /ingestion/sources/health`). La deduplicación ahora guarda qué fuentes vieron cada
  vacante y prioriza el ATS directo sobre los agregadores.
- **Ranking consciente del perfil:** la evaluación individual y por lotes usa el perfil que
  tengas seleccionado, en vez de puntuar sin contexto.
- **Ingesta más resistente:** fetches largos y revalidación de vacantes en segundo plano,
  sin bloquear la petición.

## Ganchos de apertura

Banco de primeras líneas. Usa una sola por publicación y no la repitas entre redes.

- ¿Cuántas pestañas de portales de empleo tienes abiertas ahora mismo?
- ¿Te cansaste de bucear entre cientos de anuncios para encontrar las tres vacantes que de
  verdad encajan con tu perfil?
- Tu próximo trabajo probablemente ya está publicado. El problema es que está en la
  página 40.
- Buscar trabajo hoy no es un problema de esfuerzo. Es un problema de ruido.
- Tu currículum, tu sueldo esperado y tu historial de postulaciones viven en seis
  plataformas distintas. ¿Eso te parece normal?
- Postularse es la parte fácil. Encontrar a qué vale la pena postularse es el trabajo real.

## Posicionamiento principal

### Frase principal

> Convierte el ruido de los portales de empleo en una lista corta, privada y ordenada.

### Alternativas

- Cientos de anuncios entran. Sale una lista corta que sí tiene sentido.
- Tu búsqueda laboral completa en un solo lugar, y ese lugar es tuyo.

### Descripción en una frase

> HireSense es una plataforma autoalojable para candidatos que reúne y deduplica vacantes
> de portales, ATS de empresas y ahora también conferencias, CFPs y programas financiados,
> ordena todo según tu perfil con pgvector y evaluación eficiente con LLMs, y gestiona las
> postulaciones de principio a fin.

### Descripción para GitHub

> Búsqueda laboral autoalojable: reúne y deduplica vacantes, las ordena con pgvector y
> LLMs, descubre conferencias y CFPs, y gestiona tus postulaciones de principio a fin.

### Texto para la imagen social

```text
HireSense
Cientos de anuncios entran.
Sale una lista corta que sí encaja.
Código abierto · Autoalojable
```

## LinkedIn

El carrusel de 8 diapositivas que acompaña a la publicación principal está en
[`carousel/carousel-es.html`](carousel/carousel-es.html) — se exporta a PDF desde Chrome.
Ver [`carousel/README.md`](carousel/README.md).

Recuerda que LinkedIn corta el texto a ~2-3 líneas antes del "…ver más": el gancho tiene que
funcionar solo. La publicación principal lleva sus dos enlaces (demo y repositorio) en el
cuerpo, a propósito: son la acción que se pide. Cualquier enlace adicional va al primer
comentario.

### Publicación principal

> ¿Cuántas pestañas de empleo tienes abiertas ahora mismo?
>
> Yo llegué a tener siete, varias versiones de mi CV y cero claridad sobre qué estaba
> funcionando. Por eso construí **HireSense**.
>
> Es una plataforma **open source y autoalojable** que:
>
> - Reúne vacantes de portales y ATS de empresas, y elimina duplicados.
> - Las ordena según su compatibilidad con tu perfil.
> - Gestiona postulaciones, currículums, cartas y entrevistas.
> - Descubre conferencias, CFPs y programas financiados.
>
> La hice autoalojable porque tu CV, salario esperado e historial de postulaciones deberían
> permanecer bajo tu control.
>
> **Stack:** Python, FastAPI, Angular, PostgreSQL/pgvector, Docker, LangChain, OpenTelemetry
> y Grafana.
>
> Es la primera versión pública. Me interesa especialmente saber:
>
> ¿La instalación se entiende?
> ¿El ranking de vacantes te resulta útil?
>
> Demo: https://hiresense-demo.vercel.app/
> Repositorio: StevSant/HireSense
>
> Si te sirve, una estrella o un issue en el repositorio ayudan mucho.
>
> #OpenSource #Python #BusquedaLaboral #IA #Jobs

### Publicación de novedades

> Una vacante no es la única puerta que existe.
>
> Acabo de agregar **Discover** a HireSense: además de vacantes, ahora encuentra
> conferencias, CFPs (convocatorias de ponencias) y programas financiados, con filtros por
> tema, país y fecha límite, orden por relevancia contra tu perfil, y una etiqueta de costo
> que te dice si es gratis, financiado o de pago, incluso cuando la fuente no publica el
> precio.
>
> En la misma tanda entraron fuentes nuevas de empleo: Dice, Y Combinator Work at a Startup
> y CrunchBoard de forma automática, más adaptadores para portales Workday, Thoughtworks y
> Globant y un detector que reconoce solo el ATS de una empresa desde su página de carreras.
>
> Y algo menos vistoso pero que me importa igual: cada fuente ahora reporta su propia salud
> (última ejecución, cuántas vacantes trajo, qué error dio) y la deduplicación guarda qué
> fuentes vieron cada vacante, priorizando el ATS de la empresa sobre los agregadores.
>
> Todo sigue siendo código abierto y autoalojable:
> https://github.com/StevSant/HireSense
>
> ¿Qué fuente te falta a ti? Es literalmente un adaptador nuevo.
>
> #OpenSource #Python #BusquedaLaboral #DevCommunity

### Publicación de seguimiento (técnica)

> Tu mejor oportunidad está en la página 40 y nunca vas a llegar ahí.
>
> Ese es el problema real que resuelve HireSense, y no tiene que ver con “ponerle IA” al
> producto. Tiene que ver con **cuándo** se ordenan las vacantes.
>
> Si una aplicación evalúa únicamente la página que estás viendo, una oportunidad excelente
> queda enterrada por el simple hecho de haber llegado tarde al feed. Por eso el sistema hace
> una preselección semántica sobre todo el conjunto antes de paginar.
>
> El flujo combina pgvector, coincidencia de habilidades y evaluación escalonada con LLMs
> solo cuando el costo adicional aporta una señal útil.
>
> Escribí sobre la arquitectura y sus decisiones aquí:
> https://github.com/StevSant/HireSense/blob/main/backend/ARCHITECTURE.md
>
> ¿Qué priorizarías tú: calidad, explicación del resultado o costo?
>
> #PostgreSQL #pgvector #InteligenciaArtificial #OpenSource

### Primer comentario sugerido

> Una aclaración importante: es una herramienta para candidatos, no un sistema para filtrar
> personas desde el lado del reclutador. El objetivo es ayudar a una persona a convertir
> cientos de anuncios en una lista manejable y mantener sus datos bajo su control.

## Reddit

Lee las reglas actuales de cada comunidad y adapta el texto a tu propia voz. No publiques el
mismo anuncio en varias comunidades al mismo tiempo.

### `r/programacion`

**Título**

> Me cansé de buscar trabajo entre 7 pestañas y una hoja de cálculo, así que construí una
> plataforma open source y autoalojable

**Texto**

> Mi búsqueda laboral terminó repartida entre portales, hojas de cálculo, distintas versiones
> del currículum, notas de entrevistas y recordatorios. Empecé HireSense para reunir ese
> proceso en una sola aplicación.
>
> El problema interesante no era generar texto con un LLM. Era reducir el ruido: deduplicar
> vacantes con identidad estable, ordenar el conjunto completo en lugar de una sola página,
> controlar el costo de los modelos y detectar cuándo un anuncio ya está muerto.
>
> El sistema obtiene vacantes de fuentes públicas y portales ATS de empresas (Greenhouse,
> Lever, Ashby, Workable, SmartRecruiters, Recruitee, Workday, más un detector automático y
> un scraper genérico para los que no exponen API), elimina duplicados guardando de qué
> fuentes vino cada rol, ordena todo con pgvector + habilidades + evaluación opcional con
> LLMs, y permite seguir las postulaciones hasta entrevista u oferta.
>
> Lo más reciente: un módulo de oportunidades que no son vacantes (conferencias, CFPs,
> programas financiados) con filtros y etiquetas de costo, y salud por fuente para saber
> cuál se rompió y por qué.
>
> Stack: FastAPI, Angular, PostgreSQL/pgvector y Docker, con observabilidad vía
> OpenTelemetry y Grafana.
>
> Repositorio: https://github.com/StevSant/HireSense
>
> Me interesa recibir críticas técnicas, especialmente sobre la instalación y la forma de
> calcular y explicar la compatibilidad. ¿Qué mejorarían primero?

### Comunidad de autoalojamiento en español

**Título**

> ¿Por qué tu currículum y tu historial de postulaciones tienen que vivir en el servidor de
> otro? Alternativa autoalojable para la búsqueda laboral

**Texto**

> Construí HireSense porque el currículum, las expectativas salariales, las preferencias y el
> historial de postulaciones son demasiado personales para repartirlos entre varias
> plataformas que además te los monetizan.
>
> La aplicación corre con Docker y mantiene el flujo completo bajo tu control: ingesta y
> deduplicación de vacantes, ranking con pgvector, descubrimiento de conferencias y CFPs,
> seguimiento, documentos, entrevistas y analítica. El uso de proveedores LLM es opcional:
> hay un modo heurístico local para probar el flujo sin pagar nada.
>
> Novedades recientes: fuentes nuevas (Dice, YC, CrunchBoard), adaptadores de portales
> Workday/Thoughtworks/Globant, y un panel de salud por fuente para ver qué ingesta está
> fallando sin abrir los logs.
>
> Código: https://github.com/StevSant/HireSense
>
> Demo: https://hiresense-demo.vercel.app
>
> ¿Qué requisito de privacidad, despliegue o consumo de recursos sería imprescindible para
> que alojaras una herramienta así?

## Product Hunt

Product Hunt funciona principalmente en inglés. Usa la versión inglesa para el lanzamiento
principal y este texto para comunicarlo después a tu red hispanohablante.

### Frase corta

> De cientos de anuncios a una lista corta, privada y ordenada

### Descripción

> HireSense es una plataforma de código abierto y autoalojable que encuentra y deduplica
> vacantes, las ordena según tu perfil, descubre conferencias y CFPs relevantes, y acompaña
> el proceso desde los documentos personalizados hasta la preparación para entrevistas y la
> analítica.

### Anuncio para la comunidad hispanohablante

> ¿Cuánto de tu búsqueda laboral es buscar, y cuánto es solo administrar pestañas?
>
> Hoy lancé HireSense en Product Hunt: una plataforma open source y autoalojable que
> convierte cientos de anuncios en una lista priorizada y después ayuda a gestionar todo el
> proceso de postulación. Y ahora también encuentra conferencias, CFPs y programas
> financiados relacionados con tu perfil.
>
> Repositorio: https://github.com/StevSant/HireSense
>
> No necesito que votes por compromiso. Me sirve mucho más que la pruebes y dejes una
> opinión honesta sobre la instalación o la utilidad del ranking.

## DEV Community / Hashnode

### Artículo recomendado

**Título**

> Tu mejor vacante está en la página 40: cómo construí un ranking laboral eficiente con
> pgvector y LLMs escalonados

**Subtítulo**

> Por qué ordenar todo el conjunto antes de paginar produce mejores resultados y cómo evitar
> llamadas costosas cuando la señal no las justifica.

**Estructura**

1. El problema de evaluar solamente la página visible.
2. Identidad estable y deduplicación antes del ranking.
3. Preselección semántica global con pgvector.
4. Coincidencia estructurada de habilidades.
5. Evaluación escalonada con LLMs y caché.
6. Explicación de resultados y ausencia de señales.
7. Medición de costo y calidad.
8. Casos que todavía fallan y próximos experimentos.
9. Repositorio e instalación reproducible.

**Etiquetas sugeridas para DEV**

```text
#python #postgres #machinelearning #opensource
```

### Otros títulos

- Por qué mi aplicación laboral ordena todas las vacantes antes de mostrar la primera página
- Cuando la fuente no dice el precio: cómo inferir si una conferencia es gratis, financiada
  o de pago
- Siete portales de empleo, siete formas de decir “no”: qué se puede integrar de verdad y
  qué toca importar a mano
- Cómo diseñar una aplicación de IA autoalojable alrededor de la privacidad del candidato
- Identidad estable, hashes de contenido y el problema de las vacantes obsoletas
- Arquitectura hexagonal en FastAPI con múltiples adaptadores externos
- Observabilidad de llamadas LLM con OpenTelemetry, Tempo, Loki y Grafana

## Publicaciones cortas

### X / Bluesky / Mastodon

> Tu próximo trabajo ya está publicado. Está en la página 40 y nunca vas a llegar ahí.
>
> Por eso construí HireSense: open source y autoalojable, deduplica vacantes, ordena **todo**
> el conjunto con pgvector antes de paginar, encuentra conferencias y CFPs, y gestiona tus
> postulaciones de principio a fin.
>
> Código: https://github.com/StevSant/HireSense

### Variante corta (novedades)

> Nuevo en HireSense: Discover para conferencias, CFPs y programas financiados, con filtros
> por tema, país y deadline, y etiqueta de costo aunque la fuente no publique el precio.
>
> Más fuentes de empleo: Dice, YC y CrunchBoard.
>
> https://github.com/StevSant/HireSense

### Título para YouTube

> Construí la app que me hubiera gustado tener buscando trabajo (FastAPI + Angular +
> pgvector)

### Descripción para YouTube

> ¿Te cansaste de revisar cientos de anuncios para encontrar tres que encajen? HireSense
> transforma esa avalancha en una lista deduplicada y ordenada según tu perfil, y después
> ayuda con el seguimiento, los documentos personalizados, la preparación para entrevistas,
> los contactos profesionales y la analítica. También descubre conferencias, CFPs y
> programas financiados.
>
> Código y documentación: https://github.com/StevSant/HireSense
>
> Demo pública: https://hiresense-demo.vercel.app

## Llamadas a la acción

Usa solo una por publicación:

- **Feedback:** ¿Qué te impediría probar o autoalojar esta aplicación?
- **Ranking:** ¿Qué te importa más: calidad, explicación o costo?
- **Producto:** ¿Qué parte de la búsqueda laboral debería seguir siendo manual?
- **Fuentes:** ¿Qué portal de empleo te falta? Agregarlo es un adaptador nuevo.
- **Contribución:** ¿La guía permite hacer un primer pull request sin ayuda adicional?
- **Apoyo:** Si te resulta útil, guarda el repositorio con una estrella para encontrar las
  próximas versiones.

No combines todas las preguntas en la misma publicación.

## Vocabulario recomendado

Usa `código abierto` u `open source`, `autoalojable`, `vacantes`, `postulaciones`, `búsqueda
laboral`, `lista priorizada`, `compatibilidad`, `control de datos` y `asistido por IA`.

Evita `revolucionario`, `garantiza entrevistas`, `vence cualquier ATS`, `postula
automáticamente a todo`, `reemplaza a los reclutadores` y cualquier afirmación de precisión
o ahorro que no tenga una medición verificable.

Los ganchos pueden ser directos y con personalidad, pero la promesa debe seguir siendo
comprobable: describe lo que la herramienta hace, no lo que garantiza que vas a conseguir.
