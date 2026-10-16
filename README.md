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

## 📡 Referencia Detallada de la API

### Cabeceras Globales
* `x-api-key` (*string, obligatorio*): Clave de autenticación para proteger todos los endpoints bajo `/action/*` y `/files/*`.
* `x-mongo-uri` (*string, opcional*): Permite sobreescribir la conexión de MongoDB para una petición específica en lugar de usar `MONGODB_URI`.

### Manejo de Tipos BSON (EJSON)
* **ObjectIds:** Puedes enviar `_id` como un string hexadecimal estándar de 24 caracteres (ej. `"60d5ec49f1b2c8b1f8e4e1a1"`) o en formato Extended JSON (`{"$oid": "..."}`). La API los normaliza automáticamente.
* **Fechas:** Utiliza la sintaxis Extended JSON: `{"$date": "2026-05-01T12:00:00Z"}`.
* **Operadores MongoDB:** Admite operadores nativos como `$set`, `$inc`, `$in`, `$gt`, `$push`, etc.

---

### 1. Endpoints de Sistema

#### `GET /health`
Comprueba el estado del servicio y mide la latencia de ping hacia MongoDB Atlas. No requiere autenticación.
* **Respuesta exitosa (200 OK):**
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "latency_ms": 14.25
  }
  ```
* **Respuesta de fallo (503 Service Unavailable):**
  ```json
  {
    "status": "unhealthy",
    "database": "disconnected",
    "error": "ServerSelectionTimeoutError: ..."
  }
  ```

#### `GET /docs`
Interfaz interactiva **Swagger UI** autogenerada por FastAPI. Permite probar y explorar todos los endpoints directamente desde el navegador.

---

### 2. Data API (`/action/*`)

#### `POST /action/find`
Consulta múltiples documentos que coincidan con un filtro.
* **Body:**
  ```json
  {
    "database": "app_db",       // Opcional (usa DEFAULT_DATABASE si se omite)
    "collection": "items",       // Obligatorio
    "filter": { "status": "active" },
    "projection": { "title": 1, "price": 1 },
    "sort": { "createdAt": -1 }, // 1 ascendente, -1 descendente
    "limit": 50,                 // Maximo: 5000 (defecto: 100)
    "skip": 0                    // Paginacion
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "documents": [
      { "_id": "60d5ec49f1b2c8b1f8e4e1a1", "title": "Item 1", "price": 25.5 }
    ]
  }
  ```

#### `POST /action/findOne`
Obtiene un único documento coincidente.
* **Body:**
  ```json
  {
    "collection": "items",
    "filter": { "_id": "60d5ec49f1b2c8b1f8e4e1a1" }
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "document": { "_id": "60d5ec49f1b2c8b1f8e4e1a1", "title": "Item 1" }
  }
  ```
  *(Devuelve `"document": null` si no se encuentra ningún registro).*

#### `POST /action/count`
Cuenta el número de documentos que cumplen una condición.
* **Body:**
  ```json
  {
    "collection": "items",
    "filter": { "status": "active" }
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "count": 42
  }
  ```

#### `POST /action/aggregate`
Ejecuta un pipeline de agregación en MongoDB.
* **Body:**
  ```json
  {
    "collection": "items",
    "pipeline": [
      { "$match": { "status": "completed" } },
      { "$group": { "_id": "$category", "total": { "$sum": "$amount" } } }
    ]
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "documents": [
      { "_id": "electronics", "total": 1540.0 }
    ]
  }
  ```

#### `POST /action/insertOne`
Inserta un único documento en la colección.
* **Body:**
  ```json
  {
    "collection": "items",
    "document": {
      "title": "Nuevo Producto",
      "stock": 10
    }
  }
  ```
* **Respuesta (201 Created):**
  ```json
  {
    "insertedId": "60d5ec49f1b2c8b1f8e4e1a2"
  }
  ```

#### `POST /action/insertMany`
Inserta una lista de documentos.
* **Body:**
  ```json
  {
    "collection": "items",
    "documents": [
      { "title": "Producto A", "stock": 5 },
      { "title": "Producto B", "stock": 8 }
    ]
  }
  ```
* **Respuesta (201 Created):**
  ```json
  {
    "insertedIds": [
      "60d5ec49f1b2c8b1f8e4e1a3",
      "60d5ec49f1b2c8b1f8e4e1a4"
    ]
  }
  ```

#### `POST /action/updateOne`
Actualiza el primer documento que cumpla el filtro.
* **Body:**
  ```json
  {
    "collection": "items",
    "filter": { "_id": "60d5ec49f1b2c8b1f8e4e1a1" },
    "update": {
      "$set": { "stock": 15 },
      "$currentDate": { "lastModified": true }
    },
    "upsert": false
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "matchedCount": 1,
    "modifiedCount": 1
  }
  ```

#### `POST /action/updateMany`
Actualiza todos los documentos que coincidan con el filtro.
* **Body:**
  ```json
  {
    "collection": "items",
    "filter": { "status": "draft" },
    "update": { "$set": { "status": "archived" } }
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "matchedCount": 8,
    "modifiedCount": 8
  }
  ```

#### `POST /action/deleteOne` / `POST /action/deleteMany`
Elimina uno o varios documentos coincidentes.
* **Body:**
  ```json
  {
    "collection": "items",
    "filter": { "_id": "60d5ec49f1b2c8b1f8e4e1a1" }
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "deletedCount": 1
  }
  ```

---

### 3. Ficheros GridFS (`/files/*`)

#### `POST /files/upload`
Sube un archivo de cualquier tamaño directamente a MongoDB GridFS mediante streaming continuo.
* **Content-Type:** `multipart/form-data`
* **Form fields:**
  * `file` (*archivo binario, obligatorio*): Fichero a subir.
  * `database` (*string, opcional*): Nombre de la base de datos destino.
  * `bucket` (*string, opcional, defecto: `"fs"`*): Nombre del bucket de GridFS.
* **Respuesta (201 Created):**
  ```json
  {
    "fileId": "60d5ec49f1b2c8b1f8e4e1a5",
    "filename": "factura.pdf",
    "contentType": "application/pdf",
    "length": 245890
  }
  ```

#### `GET /files/{file_id}`
Descarga o visualiza el archivo en el navegador en streaming.
* **Autenticación flexible:**
  * Vía cabecera: `x-api-key: tu-clave`
  * O vía query param: `?key=tu-clave` (ideal para `<img src="...">` o enlaces directos).
* **Parámetros opcionales (Query):**
  * `download=true`: Fuerza la descarga añadiendo `Content-Disposition: attachment`. Si no se incluye, usa `inline` (para ver PDFs o imágenes directamente en el navegador).
  * `database`: Nombre de la base de datos si es distinta a la predeterminada.
  * `bucket`: Nombre del bucket de GridFS (defecto: `fs`).
* **Respuesta:** Stream binario con las cabeceras `Content-Type`, `Content-Length` y `Content-Disposition` adecuadas.

#### `GET /files/{file_id}/info`
Obtiene metadatos del archivo sin descargar el contenido binario.
* **Respuesta (200 OK):**
  ```json
  {
    "fileId": "60d5ec49f1b2c8b1f8e4e1a5",
    "filename": "factura.pdf",
    "length": 245890,
    "uploadDate": "2026-10-16T22:30:00+00:00",
    "metadata": {
      "contentType": "application/pdf",
      "originalFilename": "factura.pdf"
    }
  }
  ```

#### `DELETE /files/{file_id}`
Elimina el archivo y todos sus chunks de datos en GridFS.
* **Respuesta (200 OK):**
  ```json
  {
    "deleted": true,
    "fileId": "60d5ec49f1b2c8b1f8e4e1a5"
  }
  ```


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
