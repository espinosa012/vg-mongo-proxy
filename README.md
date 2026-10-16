# vg-mongo-proxy

> **FastAPI MongoDB HTTP Proxy** con Data API genérica y almacenamiento de archivos mediante MongoDB GridFS. Diseñado para permitir que aplicaciones web frontend (SPAs, Jamstack, static sites, Edge workers) consulten e interactúen con MongoDB Atlas o cualquier clúster de MongoDB de forma segura y sin exponer credenciales en el cliente.

---

## 📑 Tabla de Contenidos

- [Arquitectura](#-arquitectura)
- [Gestión de Secretos y Seguridad](#-gestión-de-secretos-y-seguridad)
- [Despliegue en Render](#-despliegue-en-render)
- [Integración Frontend (JavaScript)](#-integración-frontend-javascript)
- [Referencia de la API](#-referencia-de-la-api)
- [Desarrollo Local](#-desarrollo-local)

---

## 🏛 Arquitectura

```
+------------------------------------+
|     Frontend / Web App             |
|     (Cualquier cliente web / SPA)  |
|  * Solo conoce la URL del proxy    |
|  * Envia cabecera x-api-key        |
+------------------------------------+
                 |
                 | HTTPS / Fetch (CORS configurado)
                 v
+------------------------------------+
|     vg-mongo-proxy (en Render)     |
|  * Python 3.11 + FastAPI + Motor   |
|  * Valida x-api-key y CORS         |
|  * Custodia MONGODB_URI en secreto |
|  * Mantiene pool de conexiones     |
+------------------------------------+
                 |
                 | TCP / TLS (Driver MongoDB)
                 v
+------------------------------------+
|        MongoDB Atlas               |
|  * Colecciones de datos            |
|  * Buckets GridFS (fs.files/chunks)|
+------------------------------------+
```

---

## 🔐 Gestión de Secretos y Seguridad

### ¿Dónde se guarda la cadena de conexión de MongoDB (`MONGODB_URI`)?

1. **En Producción (Render):**
   - **NUNCA en el código fuente ni en el repositorio.**
   - En el panel de **Render**, entra a tu servicio y dirígete a:  
     `Environment` ➔ `Environment Variables`.
   - Añade la variable:
     - **Key:** `MONGODB_URI`
     - **Value:** `mongodb+srv://<usuario>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
   - Render cifra esta variable en reposo y solo la expone en memoria al proceso de la aplicación en tiempo de ejecución.

2. **En Local (Desarrollo):**
   - Se guarda en un archivo `.env` en la raíz del repositorio.
   - El archivo `.env` está expresamente incluido en `.gitignore` y **jamás** se sube al control de versiones.
   - Utiliza `.env.example` como plantilla.

3. **En el Frontend / Cliente:**
   - **¡El string de conexión a MongoDB NUNCA debe estar en el cliente!**
   - El código en el navegador o cliente web únicamente necesita:
     - La URL del servicio en Render (ej. `https://tu-servicio.onrender.com`).
     - La clave de acceso `x-api-key` (la misma que defines en Render como `PROXY_API_KEY`).

---

## 🚀 Despliegue en Render

### Opción 1: Crear Web Service Manualmente
1. Entra a [Render Dashboard](https://dashboard.render.com/) y pulsa **New +** ➔ **Web Service**.
2. Conecta tu repositorio de GitHub.
3. Configura los siguientes campos:
   - **Runtime:** `Python`
   - **Build Command:** `pip install .`
   - **Start Command:** `uvicorn vg_mongo_proxy.main:app --host 0.0.0.0 --port $PORT`
4. En **Environment Variables**, añade:
   - `MONGODB_URI`: Tu cadena de conexión a MongoDB Atlas.
   - `PROXY_API_KEY`: Una clave secreta para autorizar peticiones a la API.
   - `DEFAULT_DATABASE`: Nombre de la base de datos por defecto (ej. `app_db`).
   - `CORS_ORIGINS`: Dominio(s) de tu frontend autorizados (ej. `https://tu-dominio.com,http://localhost:5173`).
5. Pulsa **Deploy Web Service**.

### Opción 2: Usar Render Blueprint (`render.yaml`)
El repositorio incluye un archivo [`render.yaml`](./render.yaml). Puedes crear un nuevo **Blueprint** en Render apuntando a este repositorio y Render detectará automáticamente toda la configuración.

---

## 💻 Integración Frontend (JavaScript)

### 1. Cliente Base y Manejo de Cold Starts (Render Free Tier)

Los servicios en la capa gratuita de Render entran en suspensión tras 15 minutos sin tráfico. Puedes usar el endpoint público `/health` para despertar el proxy y verificar conectividad:

```javascript
const PROXY_URL = "https://tu-servicio.onrender.com";
const API_KEY = "tu-clave-secreta-definida-en-render";

// Comprobar conexion / despertar servidor
async function checkServerHealth() {
  try {
    const res = await fetch(`${PROXY_URL}/health`);
    const data = await res.json();
    return data.status === "healthy";
  } catch (err) {
    console.warn("Despertando servidor en Render...", err);
    return false;
  }
}
```

### 2. Crear un Documento (`insertOne`)

```javascript
async function createDocument(collection, documentData) {
  const res = await fetch(`${PROXY_URL}/action/insertOne`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({
      collection,
      document: {
        ...documentData,
        createdAt: { "$date": new Date().toISOString() },
      },
    }),
  });
  const data = await res.json();
  return data.insertedId; // ID del documento creado
}
```

### 3. Consultar Documentos (`find`)

```javascript
async function getDocuments(collection, filter = {}, sort = { createdAt: -1 }, limit = 50) {
  const res = await fetch(`${PROXY_URL}/action/find`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({
      collection,
      filter,
      sort,
      limit,
    }),
  });
  const data = await res.json();
  return data.documents;
}
```

### 4. Subir un Fichero Adjunto (`/files/upload` vía GridFS)

```javascript
async function uploadAttachment(fileInput) {
  const file = fileInput.files[0];
  const formData = new FormData();
  formData.append("file", file);

  const res = await fetch(`${PROXY_URL}/files/upload`, {
    method: "POST",
    headers: {
      "x-api-key": API_KEY, // multipart no debe llevar Content-Type manual
    },
    body: formData,
  });

  const fileData = await res.json();
  // Devuelve: { fileId: "...", filename: "doc.pdf", contentType: "application/pdf", length: 1048576 }
  return fileData;
}
```

### 5. Mostrar o Descargar un Fichero

Puedes cargar imágenes directamente en etiquetas `<img>` o enlaces pasándoles la clave en la URL:

```html
<!-- Enlace de descarga directa -->
<a href="https://tu-servicio.onrender.com/files/60d5ec49f1b2c8b1f8e4e1a1?key=tu-clave-secreta&download=true">
  Descargar Fichero
</a>

<!-- Imagen directa en el navegador -->
<img src="https://tu-servicio.onrender.com/files/60d5ec49f1b2c8b1f8e4e1a1?key=tu-clave-secreta" alt="Vista previa" />
```

---

## 📡 Referencia de la API

### Sistema
- `GET /`: Información básica de la versión y estado.
- `GET /health`: Healthcheck público y ping de latencia con MongoDB.
- `GET /docs`: Documentación interactiva Swagger UI de FastAPI.

### Data API (`/action/*`)
*Todas las acciones requieren la cabecera `x-api-key`.*

| Endpoint | Parámetros Clave | Descripción |
| :--- | :--- | :--- |
| `POST /action/find` | `collection`, `filter`, `projection`, `sort`, `limit`, `skip` | Consultar múltiples documentos |
| `POST /action/findOne` | `collection`, `filter`, `projection` | Consultar un único documento |
| `POST /action/count` | `collection`, `filter` | Contar documentos coincidentes |
| `POST /action/aggregate` | `collection`, `pipeline` | Ejecutar pipeline de agregación |
| `POST /action/insertOne` | `collection`, `document` | Insertar un documento |
| `POST /action/insertMany` | `collection`, `documents` | Insertar lista de documentos |
| `POST /action/updateOne` | `collection`, `filter`, `update`, `upsert` | Actualizar primer documento coincidente |
| `POST /action/updateMany` | `collection`, `filter`, `update`, `upsert` | Actualizar todos los documentos coincidentes |
| `POST /action/deleteOne` | `collection`, `filter` | Eliminar un documento |
| `POST /action/deleteMany` | `collection`, `filter` | Eliminar múltiples documentos |

### Ficheros GridFS (`/files/*`)

| Endpoint | Método | Parámetros | Descripción |
| :--- | :--- | :--- | :--- |
| `/files/upload` | `POST` | `multipart/form-data`: `file`, `bucket?` | Sube un fichero por streaming a GridFS |
| `/files/{file_id}` | `GET` | `?key=...` o `x-api-key`, `?download=true` | Descarga o previsualiza el fichero en el navegador |
| `/files/{file_id}/info` | `GET` | Cabecera `x-api-key` | Obtiene metadatos del fichero sin descargar contenido |
| `/files/{file_id}` | `DELETE` | Cabecera `x-api-key` | Elimina el fichero y sus chunks de GridFS |

---

## 🛠 Desarrollo Local

```bash
# 1. Clonar repositorio
git clone <URL_DE_TU_REPOSITORIO>
cd vg-mongo-proxy

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias en modo editable con herramientas de desarrollo
pip install -e ".[dev]"

# 4. Configurar variables de entorno
cp .env.example .env
# Edita el archivo .env con tus credenciales locales

# 5. Ejecutar tests automatizados
pytest

# 6. Arrancar servidor de desarrollo
uvicorn vg_mongo_proxy.main:app --reload --port 8000
```
