# Despliegue en Kubernetes (namespace Alicante)

## Prerrequisitos

- Acceso al cluster de Kubernetes con `kubectl` configurado
- Namespace `alicante` existente (se crea automáticamente con el YAML)
- GitHub PAT con permiso `read:packages` para pull de imágenes desde GHCR

---

## Paso 1: Crear el secret del registry GHCR

Necesario para que Kubernetes pueda hacer pull de las imágenes desde `ghcr.io`.

```bash
kubectl create secret docker-registry ghcr-docker-registry-secret \
  --namespace=alicante \
  --docker-server=ghcr.io \
  --docker-username=jotajota1302 \
  --docker-password=<GITHUB_PAT>
```

> El `<GITHUB_PAT>` se genera en: GitHub > Settings > Developer settings > Personal access tokens.
> Debe tener el permiso `read:packages`.

---

## Paso 2: Crear el secret de la aplicacion

Contiene las variables de entorno del backend (LLM, KOSIN, cifrado).

```bash
kubectl create secret generic ticketing-anonymization-secret \
  --namespace=alicante \
  --from-literal=ENCRYPTION_KEY="" \
  --from-literal=LLM_PROVIDER="openai" \
  --from-literal=OPENAI_API_KEY="<TU_OPENAI_API_KEY>" \
  --from-literal=OPENAI_MODEL="gpt-4o-mini" \
  --from-literal=KOSIN_URL="https://umane.emeal.nttdata.com/jiraito" \
  --from-literal=KOSIN_TOKEN="<TU_KOSIN_TOKEN>" \
  --from-literal=KOSIN_EMAIL="<TU_EMAIL>@emeal.nttdata.com" \
  --from-literal=KOSIN_PROJECT_KEY="GDNESPAIN"
```

> Si `ENCRYPTION_KEY` se deja vacio, el backend genera una clave efimera automaticamente.

---

## Paso 3: Aplicar los manifiestos

```bash
kubectl apply -f 01-ticketing-anonymization-deployment.yaml
kubectl apply -f 00-ticketing-anonymization-virtual-service.yaml
```

---

## Paso 4: Verificar el despliegue

```bash
# Ver estado de los pods
kubectl get pods -n alicante -l app=ticketing-anonymization

# Ver logs del backend
kubectl logs -n alicante -l name=ticketing-anonymization-backend

# Ver logs del frontend
kubectl logs -n alicante -l name=ticketing-anonymization-frontend

# Comprobar health del backend
kubectl exec -n alicante deploy/ticketing-anonymization-backend -- curl -s http://localhost:8000/health
```

Ambos pods deben estar en estado `Running`.

---

## Acceso a la aplicacion

Una vez desplegado, la app es accesible en:

```
https://ticketing-anonymization.alicante.deptapps.everis.cloud
```

- Frontend: `/`
- API Backend: `/api/*`
- WebSocket chat: `/ws/*`
- Health check: `/health`

---

## Actualizar imagenes

Cuando se hace push a `main`, GitHub Actions construye y publica nuevas imagenes automaticamente.
Para que el cluster tire de la version nueva:

```bash
kubectl rollout restart deployment/ticketing-anonymization-backend -n alicante
kubectl rollout restart deployment/ticketing-anonymization-frontend -n alicante
```

---

## Troubleshooting

### Pod en ImagePullBackOff
El secret del registry no existe o el token ha expirado:
```bash
kubectl get secret ghcr-docker-registry-secret -n alicante
# Si no existe, volver al Paso 1
```

### Pod en CrashLoopBackOff
Revisar logs:
```bash
kubectl logs -n alicante -l name=ticketing-anonymization-backend --tail=50
```

### Recrear secrets (si hay que cambiar valores)
```bash
kubectl delete secret ticketing-anonymization-secret -n alicante
# Repetir Paso 2 con los nuevos valores
kubectl rollout restart deployment/ticketing-anonymization-backend -n alicante
```
