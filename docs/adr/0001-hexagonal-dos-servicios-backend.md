# ADR-0001 — Arquitectura hexagonal con dos servicios backend (API e IA)

| | |
|---|---|
| **Estado** | Aceptada |
| **Fecha** | 2026-10-03 |
| **Decide** | Silva Vega, Héctor (Project Manager) |

## Contexto

Necesitamos una estructura de carpetas real y defendible antes de escribir lógica de negocio.
El sistema tiene dos cargas de trabajo muy distintas: por un lado peticiones cortas y frecuentes
(registrar eventos, listar, decidir), y por otro análisis de audio y rostro que consumen CPU
durante segundos. Además el equipo son cuatro personas que trabajan en paralelo y necesitan tocar
archivos distintos sin pisarse.

## Decisión

Monolito modular con **arquitectura hexagonal (puertos y adaptadores)** en la API principal, y
un **servicio de IA separado**, también hexagonal.

- `domain/` tiene entidades y reglas puras, sin ningún framework.
- `application/ports/` declara interfaces (`Protocol`) y `application/use_cases/` un caso de uso
  por archivo.
- `adapters/inbound/http/` son los routers de FastAPI y `adapters/outbound/` las implementaciones
  concretas (`memory/`, `supabase/`, `redis_queue/`).
- La regla de dependencias es `adapters -> application -> domain`, nunca al revés, y se **verifica
  en el CI** con `import-linter`.

Se separa la IA en su propio servicio porque escala distinto (CPU pesada) y se consume por cola, no
por petición síncrona.

## Alternativas consideradas

- **Monolito en capas tradicional (controller/service/repository).** Más rápido de arrancar, pero
  la lógica de negocio termina mezclada con el framework y no se puede probar sin levantar la app.
- **Microservicios desde el inicio.** Demasiada infraestructura para un equipo de cuatro personas
  en un semestre, y con presupuesto cero de despliegue.
- **Clean Architecture.** Prácticamente equivalente para nuestro tamaño; elegimos hexagonal porque
  la metáfora de puerto/adaptador hace obvio dónde va cada archivo, que es justo lo que el equipo
  necesita para no pisarse.

## Consecuencias

**A favor:** los casos de uso se prueban con adaptadores en memoria, sin Supabase ni Redis, así
que las pruebas corren en milisegundos y el CI no necesita servicios externos. Cambiar de memoria a
Supabase es una variable de entorno. Cada integrante tiene su carpeta.

**En contra:** más archivos y más indirección para operaciones simples; hay que escribir el puerto y
los dos adaptadores aunque el caso de uso sea de tres líneas. Asumimos ese costo porque la prueba de
arquitectura del CI es lo que evita que la deuda se acumule sin que nos demos cuenta.
