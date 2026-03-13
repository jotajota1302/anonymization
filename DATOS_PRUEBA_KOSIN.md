
# Datos de prueba KOSIN - POC Anonimizacion

**IMPORTANTE: Borrar todos estos tickets al finalizar las pruebas.**

## Ticket padre (volcado anonimizado)

| Key | Tipo | Descripcion |
|-----|------|-------------|
| PESESG-249 | Evolutive | [VOLCADO-ANON] Contenedor de copias anonimizadas |

## Tickets fuente (simulan incidencias de cliente con PII)

| Key | Resumen | Prioridad |
|-----|---------|-----------|
| PESESG-241 | Poliza hogar Elena Ruiz Fernandez - error tarificacion | High |
| PESESG-243 | Siniestro auto Miguel Angel Torres - danos no cubiertos A-6 | Critical |
| PESESG-245 | Certificado seguro vida Carmen Navarro Lopez - urgente | High |
| PESESG-247 | Alerta fraude poliza salud Pablo Jimenez Garcia | Critical |

## Tickets anonimizados (se crean al ingestar)

Se crearan como sub-tareas de PESESG-249 con prefijo `[ANON]`.

| Fuente | Copia anonimizada | Estado |
|--------|-------------------|--------|
| PESESG-241 | (pendiente) | - |
| PESESG-243 | (pendiente) | - |
| PESESG-245 | (pendiente) | - |
| PESESG-247 | (pendiente) | - |

## Limpieza

```bash
cd ticketing-anonymization/backend
python cleanup_tickets.py
```

O manualmente borrar: PESESG-249, PESESG-241, PESESG-243, PESESG-245, PESESG-247 y las sub-tareas creadas.
