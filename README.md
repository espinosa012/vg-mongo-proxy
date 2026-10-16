# vg-mongo-proxy

> **FastAPI MongoDB HTTP Proxy** con Data API genérica y almacenamiento de archivos mediante MongoDB GridFS. Diseñado para permitir que aplicaciones web frontend (como las alojadas en **GitHub Pages**) consulten e interactúen con MongoDB Atlas de forma segura y sin exponer credenciales.

---

## 📑 Tabla de Contenidos

- [Arquitectura](#-arquitectura)
- [Gestión de Secretos y Seguridad](#-gestión-de-secretos-y-seguridad)
- [Despliegue en Render](#-despliegue-en-render)
- [Integración desde GitHub Pages (JavaScript)](#-integración-desde-github-pages-javascript)
- [Referencia de la API](#-referencia-de-la-api)
- [Desarrollo Local](#-desarrollo-local)

---

## 🏛 Arquitectura

```
+------------------------------------+
|     App en GitHub Pages            |
|     https://usuario.github.io/app  |
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
|  * Colecciones (tasks, etc.)       |
|  * Buckets GridFS (fs.files/chunks)|
+------------------------------------+
```

---

## 🔐 Gestión de Secretos y Seguridad

### ¿Dónde se guarda la cadena de conexión de MongoDB Atlas (`MONGODB_URI`)?

1. **En Producción (Render):**
   - **NUNCA en el código ni en GitHub.**
   - En el dashboard de **Render**, entra a tu servicio y dirígete a:  
     `Environment` ➔ `Environment Variables`.
   - Añade la variable:
     - **Key:** `MONGODB_URI`
     - **Value:** `mongodb+srv://<usuario>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`
   - Render cifra esta variable en reposo y solo la expone en memoria al proceso de la aplicación.

2. **En Local (Desarrollo):**
   - Se guarda en un archivo `.env` en la raíz del repositorio.
   - El archivo `.env` está incluido en `.gitignore` y **jamás** se sube a GitHub.
   - Utiliza `.env.example` como plantilla.

3. **En GitHub Pages (Frontend):**
   - **¡El string de conexión a Atlas NUNCA debe estar en el frontend!**
   - Tu código en GitHub Pages solo necesita:
     - La URL de tu servicio en Render (ej. `https://vg-mongo-proxy.onrender.com`).
     - Tu clave de acceso `x-api-key` (la misma que defines en Render como `PROXY_API_KEY`).

---

## 🚀 Despliegue en Render

### Opción 1: Crear Web Service Manualmente
1. Entra a [Render Dashboard](https://dashboard.render.com/) y pulsa **New +** ➔ **Web Service**.
2. Conecta tu repositorio de GitHub: `https://github.com/espinosa012/vg-mongo-proxy`.
3. Configura los siguientes campos:
   - **Runtime:** `Python`
   - **Build Command:** `pip install .`
   - **Start Command:** `uvicorn vg_mongo_proxy.main:app --host 0.0.0.0 --port $PORT`
4. En **Environment Variables**, añade:
   - `MONGODB_URI`: Tu cadena de conexión a MongoDB Atlas.
   - `PROXY_API_KEY`: Una clave secreta para autorizar tus peticiones.
   - `DEFAULT_DATABASE`: Nombre de la base de datos (ej. `tasks_db`).
   - `CORS_ORIGINS`: Tu dominio en GitHub Pages (ej. `https://espinosa012.github.io,http://localhost:5173`).
5. Pulsa **Deploy Web Service**.

### Opción 2: Usar Render Blueprint (`render.yaml`)
El repositorio incluye un archivo [`render.yaml`](./render.yaml). Puedes crear un nuevo **Blueprint** en Render apuntando a este repositorio y Render detectará automáticamente toda la configuración.

---

## 💻 Integración desde GitHub Pages (JavaScript)

### 1. Cliente Base y Manejo de Cold Starts (Render Free Tier)

Render suspende los servicios gratuitos tras 15 minutos de inactividad. Puedes usar el endpoint `/health` para despertar el proxy y comprobar el estado:

```javascript
const PROXY_URL = "https://vg-mongo-proxy.onrender.com";
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

### 2. Crear una Tarea (`insertOne`)

```javascript
async function createTask(title, description) {
  const res = await fetch(`${PROXY_URL}/action/insertOne`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({
      collection: "tasks",
      document: {
        title,
        description,
        status: "pending",
        attachments: [],
        createdAt: { "$date": new Date().toISOString() },
      },
    }),
  });
  const data = await res.json();
  return data.insertedId; // ID del documento creado
}
```

### 3. Listar Tareas (`find`)

```javascript
async function getTasks(statusFilter = null) {
  const filter = statusFilter ? { status: statusFilter } : {};

  const res = await fetch(`${PROXY_URL}/action/find`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({
      collection: "tasks",
      filter,
      sort: { createdAt: -1 },
      limit: 50,
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
<!-- Enlace de descarga -->
<a href="https://vg-mongo-proxy.onrender.com/files/60d5ec49f1b2c8b1f8e4e1a1?key=tu-clave-secreta&download=true">
  Descargar Adjunto
</a>

<!-- Imagen directa en el navegador -->
<img src="https://vg-mongo-proxy.onrender.com/files/60d5ec49f1b2c8b1f8e4e1a1?key=tu-clave-secreta" alt="Adjunto" />
```

---

## 📡 Referencia de la API

### Sistema
- `GET /`: Información básica de la versión y estado.
- `GET /health`: Healthcheck público y ping de latencia con MongoDB Atlas.
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
git clone https://github.com/espinosa012/vg-mongo-proxy.git
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
