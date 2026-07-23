# Textos de publicación en español

Los textos ya incluyen el nombre **HireSense** y sus enlaces públicos:

- Repositorio: <https://github.com/StevSant/HireSense>
- Demo pública: <https://hiresense-demo.vercel.app>
- Arquitectura: <https://github.com/StevSant/HireSense/blob/main/backend/ARCHITECTURE.md>

La demo pública funciona solo en el frontend, es de solo lectura y utiliza datos
sintéticos. No requiere una cuenta y se puede compartir públicamente.

No publiques cifras sobre rendimiento, fuentes o pruebas sin verificarlas justo antes.

## Posicionamiento principal

### Frase principal

> Convierte el caos de los portales de empleo en una lista privada, ordenada y relevante.

### Descripción en una frase

> HireSense es una plataforma autoalojable para candidatos que reúne y
> deduplica vacantes, ordena todas las oportunidades con pgvector y evaluación eficiente con
> LLMs, y gestiona las postulaciones de principio a fin.

### Descripción para GitHub

> Búsqueda laboral autoalojable: reúne y deduplica vacantes, las ordena con pgvector y LLMs,
> y gestiona tus postulaciones de principio a fin.

### Texto para la imagen social

```text
HireSense
Tu búsqueda laboral, privada y ordenada.
Código abierto · Autoalojable
```

## LinkedIn

### Publicación principal

> Me cansé de gestionar una búsqueda laboral con cinco herramientas distintas, así que
> construí una sola.
>
> Hoy publico **HireSense**, una plataforma de código abierto y autoalojable para
> personas que están buscando trabajo.
>
> La aplicación reúne vacantes de portales públicos y sistemas de empleo de empresas,
> elimina duplicados y ordena todas las oportunidades según su compatibilidad con tu perfil.
> Para hacerlo combina búsqueda semántica con pgvector, coincidencia de habilidades y
> evaluación con LLMs controlando el costo.
>
> Después permite gestionar todo el proceso: seguimiento de postulaciones, currículums y
> cartas de presentación personalizadas, preparación para entrevistas, contactos
> profesionales y análisis del mercado.
>
> Decidí hacerla autoalojable porque tu currículum, expectativas salariales, preferencias e
> historial de postulaciones son datos personales.
>
> Está construida con Python, FastAPI, Angular, PostgreSQL/pgvector, Docker, LangChain,
> OpenTelemetry y Grafana.
>
> Esta es la primera versión pública. Me ayudaría especialmente recibir feedback sobre dos
> cosas: ¿la instalación se entiende? ¿La forma de ordenar las vacantes te parece útil?
>
> Demo (solo lectura, datos sintéticos): https://hiresense-demo.vercel.app
>
> Repositorio: https://github.com/StevSant/HireSense
>
> Si te resulta útil, puedes guardar el repositorio con una estrella o contribuir en alguno
> de los issues para principiantes.
>
> #CodigoAbierto #OpenSource #Python #BusquedaLaboral

### Publicación de seguimiento

> Una de las decisiones más importantes de HireSense no tiene que ver con
> “ponerle IA” al producto.
>
> Tiene que ver con **cuándo** se ordenan las vacantes.
>
> Si una aplicación evalúa únicamente la página que estás viendo, una oportunidad excelente
> puede quedar escondida en la página 40. Por eso el sistema hace una preselección semántica
> sobre todo el conjunto antes de paginar.
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

> Construí una plataforma open source y autoalojable para organizar la búsqueda laboral

**Texto**

> Mi búsqueda laboral terminó repartida entre portales, hojas de cálculo, distintas versiones
> del currículum, notas de entrevistas y recordatorios. Empecé HireSense para
> reunir ese proceso en una sola aplicación.
>
> El sistema obtiene vacantes de fuentes públicas y portales ATS de empresas, elimina
> duplicados, ordena todo el conjunto con pgvector, habilidades y evaluación opcional con
> LLMs, y permite seguir las postulaciones hasta entrevista u oferta.
>
> El stack es FastAPI, Angular, PostgreSQL/pgvector y Docker. También incluye generación de
> documentos, preparación para entrevistas, analítica y observabilidad con OpenTelemetry y
> Grafana.
>
> Repositorio: https://github.com/StevSant/HireSense
>
> Me interesa recibir críticas técnicas, especialmente sobre la instalación y la forma de
> calcular y explicar la compatibilidad. ¿Qué mejorarían primero?

### Comunidad de autoalojamiento en español

**Título**

> Una alternativa autoalojable para mantener privados los datos de tu búsqueda laboral

**Texto**

> Construí HireSense porque el currículum, las expectativas salariales, las
> preferencias y el historial de postulaciones son demasiado personales para repartirlos
> entre varias plataformas.
>
> La aplicación corre con Docker y mantiene el flujo completo bajo tu control: ingesta y
> deduplicación de vacantes, ranking con pgvector, seguimiento, documentos, entrevistas y
> analítica. El uso de proveedores LLM es opcional para probar el flujo local.
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

> De cientos de vacantes a una lista privada y ordenada

### Descripción

> HireSense es una plataforma de código abierto y autoalojable que encuentra y
> deduplica vacantes, las ordena según tu perfil y acompaña el proceso desde los documentos
> personalizados hasta la preparación para entrevistas y la analítica.

### Anuncio para la comunidad hispanohablante

> Hoy lancé HireSense en Product Hunt.
>
> Es una plataforma open source y autoalojable que convierte cientos de anuncios laborales
> en una lista priorizada y después ayuda a gestionar todo el proceso de postulación.
>
> Si quieres revisar el proyecto y contarme qué funciona o qué falta, aquí está el repositorio:
> https://github.com/StevSant/HireSense
>
> El código está disponible en: https://github.com/StevSant/HireSense
>
> No necesito que votes por compromiso. Me sirve mucho más que la pruebes y dejes una opinión
> honesta sobre la instalación o la utilidad del ranking.

## DEV Community / Hashnode

### Artículo recomendado

**Título**

> Cómo construí un sistema eficiente de ranking laboral con pgvector y LLMs escalonados

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
- Cómo diseñar una aplicación de IA autoalojable alrededor de la privacidad del candidato
- Identidad estable, hashes de contenido y el problema de las vacantes obsoletas
- Arquitectura hexagonal en FastAPI con múltiples adaptadores externos
- Observabilidad de llamadas LLM con OpenTelemetry, Tempo, Loki y Grafana

## Publicaciones cortas

### X / Bluesky / Mastodon

> Construí HireSense: una plataforma open source y autoalojable que deduplica
> vacantes, ordena todo el conjunto con pgvector y evaluación opcional con LLMs, y gestiona
> las postulaciones de principio a fin.
>
> Código: https://github.com/StevSant/HireSense

### Título para YouTube

> Construí una plataforma de búsqueda laboral con FastAPI, Angular y pgvector

### Descripción para YouTube

> HireSense transforma cientos de vacantes en una lista deduplicada y ordenada,
> y después ayuda con el seguimiento, los documentos personalizados, la preparación para
> entrevistas, los contactos profesionales y la analítica.
>
> Código y documentación: https://github.com/StevSant/HireSense
>
> Demo pública: https://hiresense-demo.vercel.app

## Llamadas a la acción

Usa solo una por publicación:

- **Feedback:** ¿Qué te impediría probar o autoalojar esta aplicación?
- **Ranking:** ¿Qué te importa más: calidad, explicación o costo?
- **Producto:** ¿Qué parte de la búsqueda laboral debería seguir siendo manual?
- **Contribución:** ¿La guía permite hacer un primer pull request sin ayuda adicional?
- **Apoyo:** Si te resulta útil, guarda el repositorio con una estrella para encontrar las
  próximas versiones.

No combines las cinco preguntas en la misma publicación.

## Vocabulario recomendado

Usa `código abierto` u `open source`, `autoalojable`, `vacantes`, `postulaciones`, `búsqueda
laboral`, `lista priorizada`, `compatibilidad`, `control de datos` y `asistido por IA`.

Evita `revolucionario`, `garantiza entrevistas`, `vence cualquier ATS`, `postula
automáticamente a todo`, `reemplaza a los reclutadores` y cualquier afirmación de precisión
o ahorro que no tenga una medición verificable.
