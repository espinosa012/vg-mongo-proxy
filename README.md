# vg-mongo-proxy

Proxy HTTP desarrollado con FastAPI y Motor para gestionar operaciones sobre clústeres de MongoDB (incluyendo MongoDB Atlas) y almacenamiento de archivos mediante GridFS. Diseñado para permitir la integración segura desde aplicaciones cliente o arquitecturas frontend desacopladas (SPAs, Jamstack, Edge functions) sin exponer credenciales de base de datos en el cliente.

---

## Tabla de Contenidos

- [Arquitectura](#arquitectura)
- [Seguridad y Gestión de Credenciales](#seguridad-y-gestión-de-credenciales)
- [Despliegue](#despliegue)
- [Integración en Cliente](#integración-en-cliente)
- [Especificación de la API](#especificación-de-la-api)
- [Entorno de Desarrollo](#entorno-de-desarrollo)

---

## Arquitectura

```
+------------------------------------+
|        Cliente / Frontend          |
|    (SPA, Jamstack, Edge Worker)    |
|  * Comunicación exclusiva por HTTPS|
|  * Autenticación mediante cabecera |
+------------------------------------+
                 |
                 | HTTPS / Fetch (CORS)
                 | Header: x-api-key
                 v
+------------------------------------+
|          vg-mongo-proxy            |
|  * Python 3.11 + FastAPI + Motor   |
|  * Validación de API Key y CORS    |
|  * Pool de conexiones asíncrono    |
|  * Aislamiento de credenciales     |
+------------------------------------+
                 |
                 | TCP / TLS (Driver MongoDB)
                 v
+------------------------------------+
|           MongoDB Atlas            |
|  * Colecciones de documentos       |
|  * Buckets GridFS (fs.files/chunks)|
+------------------------------------+
```

---

## Seguridad y Gestión de Credenciales

La cadena de conexión a la base de datos (`MONGODB_URI`) contiene información crítica de acceso y nunca debe ser expuesta ni almacenada en el código fuente ni en el cliente web.

### 1. Entorno de Producción (Render)
* Las credenciales se configuran como variables de entorno directamente en el panel de control del servicio (`Environment` > `Environment Variables`):
  * `MONGODB_URI`: Cadena de conexión al clúster (`mongodb+srv://...`).
  * `PROXY_API_KEY`: Clave estricta de autorización para acceder al proxy.
  * `DEFAULT_DATABASE`: Nombre de la base de datos predeterminada.
  * `CORS_ORIGINS`: Lista delimitada por comas de orígenes HTTP autorizados.
* Estas variables son inyectadas en memoria durante la ejecución del proceso y permanecen cifradas en reposo.

### 2. Entorno Local (Desarrollo)
* Se definen en un archivo `.env` local en la raíz del proyecto.
* El archivo `.env` está explícitamente excluido en `.gitignore` para evitar su inclusión accidental en el sistema de control de versiones. Se proporciona un archivo `.env.example` como plantilla referencial.

### 3. Aislamiento del Cliente
* Las aplicaciones frontend únicamente interactúan con la interfaz HTTP del proxy utilizando la URL pública del servicio y la cabecera `x-api-key`. Bajo ninguna circunstancia deben tener visibilidad de las credenciales de MongoDB.

---

## Despliegue

### Despliegue Manual en Render
1. Acceder al panel de control de Render y crear un nuevo **Web Service**.
2. Vincular el repositorio del proyecto.
3. Especificar los parámetros de ejecución:
   * **Runtime:** `Python`
   * **Build Command:** `pip install .`
   * **Start Command:** `uvicorn vg_mongo_proxy.main:app --host 0.0.0.0 --port $PORT`
4. Declarar las variables de entorno requeridas:
   * `MONGODB_URI`: Cadena de conexión a MongoDB.
   * `PROXY_API_KEY`: Clave de seguridad del proxy.
   * `DEFAULT_DATABASE`: Base de datos objetivo.
   * `CORS_ORIGINS`: Orígenes autorizados (ejemplo: `https://tu-dominio.com`).

### Despliegue Automatizado (Blueprint)
El repositorio incluye el archivo de especificación `render.yaml`. Es posible inicializar el servicio seleccionando la opción **Blueprint** en Render, lo cual aprovisiona automáticamente la infraestructura y configura la ruta de healthcheck.

---

## Integración en Cliente

### 1. Inicialización y Comprobación de Estado (Health Check)

En instancias con suspensión por inactividad (como el nivel gratuito de Render), se recomienda consultar el endpoint `/health` al inicio del ciclo de vida de la aplicación:

```javascript
const PROXY_URL = "https://tu-servicio.onrender.com";
const API_KEY = "clave-configurada-en-el-proxy";

async function verifyConnection() {
  try {
    const response = await fetch(`${PROXY_URL}/health`);
    const data = await response.json();
    return data.status === "healthy";
  } catch (error) {
    console.error("Error al conectar con el proxy:", error);
    return false;
  }
}
```

### 2. Inserción de Documentos (`insertOne`)

```javascript
async function insertDocument(collection, document) {
  const response = await fetch(`${PROXY_URL}/action/insertOne`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "x-api-key": API_KEY,
    },
    body: JSON.stringify({
      collection,
      document: {
        ...document,
        createdAt: { "$date": new Date().toISOString() },
      },
    }),
  });
  const data = await response.json();
  return data.insertedId;
}
```

### 3. Consulta de Documentos (`find`)

```javascript
async function queryDocuments(collection, filter = {}, sort = { createdAt: -1 }, limit = 50) {
  const response = await fetch(`${PROXY_URL}/action/find`, {
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
  const data = await response.json();
  return data.documents;
}
```

### 4. Carga de Archivos Binarios (`/files/upload`)

```javascript
async function uploadFile(fileInstance) {
  const formData = new FormData();
  formData.append("file", fileInstance);

  const response = await fetch(`${PROXY_URL}/files/upload`, {
    method: "POST",
    headers: {
      "x-api-key": API_KEY,
    },
    body: formData,
  });

  return await response.json();
}
```

### 5. Recuperación y Visualización de Archivos

```html
<!-- Enlace de descarga directa -->
<a href="https://tu-servicio.onrender.com/files/60d5ec49f1b2c8b1f8e4e1a1?key=clave-configurada-en-el-proxy&download=true">
  Descargar documento
</a>

<!-- Visualización en línea (imágenes) -->
<img src="https://tu-servicio.onrender.com/files/60d5ec49f1b2c8b1f8e4e1a1?key=clave-configurada-en-el-proxy" alt="Archivo" />
```

---

## Especificación de la API

### Cabeceras de Solicitud
* `x-api-key` (*string, requerida en rutas protegidas*): Token de autenticación del proxy.
* `x-mongo-uri` (*string, opcional*): Cadena de conexión alternativa para redirigir dinámicamente la consulta a otro clúster.

### Convenciones de Tipos BSON (Extended JSON)
* **Identificadores (`_id`):** Se admite el formato hexadecimal estándar de 24 caracteres (`"60d5ec49f1b2c8b1f8e4e1a1"`) o el esquema canónico Extended JSON (`{"$oid": "..."}`).
* **Fechas:** Se procesan mediante el formato estándar de fecha ISO: `{"$date": "2026-05-01T12:00:00Z"}`.
* **Operadores:** Compatible con operadores estándar de MongoDB (`$set`, `$inc`, `$push`, `$in`, `$gt`, etc.).

---

### Endpoints del Sistema

#### `GET /health`
Verifica la disponibilidad del servicio y la conectividad con la instancia de MongoDB. Ruta pública.
* **Respuesta exitosa (200 OK):**
  ```json
  {
    "status": "healthy",
    "database": "connected",
    "latency_ms": 12.4
  }
  ```
* **Fallo de conectividad (503 Service Unavailable):**
  ```json
  {
    "status": "unhealthy",
    "database": "disconnected",
    "error": "ServerSelectionTimeoutError: ..."
  }
  ```

#### `GET /docs`
Documentación interactiva OpenAPI (Swagger UI) generada automáticamente por FastAPI.

---

### Endpoints de Datos (`/action/*`)

#### `POST /action/find`
Recupera un conjunto de documentos según los criterios especificados.
* **Cuerpo de la solicitud:**
  ```json
  {
    "database": "app_db",       // Opcional
    "collection": "items",       // Requerido
    "filter": { "status": "active" },
    "projection": { "title": 1, "price": 1 },
    "sort": { "createdAt": -1 },
    "limit": 50,
    "skip": 0
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "documents": [
      { "_id": "60d5ec49f1b2c8b1f8e4e1a1", "title": "Ejemplo", "price": 10.0 }
    ]
  }
  ```

#### `POST /action/findOne`
Recupera el primer documento que coincide con el filtro.
* **Cuerpo de la solicitud:**
  ```json
  {
    "collection": "items",
    "filter": { "_id": "60d5ec49f1b2c8b1f8e4e1a1" }
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "document": { "_id": "60d5ec49f1b2c8b1f8e4e1a1", "title": "Ejemplo" }
  }
  ```

#### `POST /action/count`
Devuelve el número total de documentos que coinciden con el filtro.
* **Cuerpo de la solicitud:**
  ```json
  {
    "collection": "items",
    "filter": { "status": "active" }
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "count": 128
  }
  ```

#### `POST /action/aggregate`
Ejecuta un pipeline de agregación en la colección destino.
* **Cuerpo de la solicitud:**
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
      { "_id": "categoria_a", "total": 520.0 }
    ]
  }
  ```

#### `POST /action/insertOne`
Inserta un único documento.
* **Cuerpo de la solicitud:**
  ```json
  {
    "collection": "items",
    "document": {
      "title": "Registro",
      "status": "pending"
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
Inserta múltiples documentos secuencialmente en una única operación.
* **Cuerpo de la solicitud:**
  ```json
  {
    "collection": "items",
    "documents": [
      { "title": "Registro 1" },
      { "title": "Registro 2" }
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
Actualiza el primer documento coincidente.
* **Cuerpo de la solicitud:**
  ```json
  {
    "collection": "items",
    "filter": { "_id": "60d5ec49f1b2c8b1f8e4e1a1" },
    "update": {
      "$set": { "status": "processed" }
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
Actualiza todos los documentos coincidentes.
* **Cuerpo de la solicitud:**
  ```json
  {
    "collection": "items",
    "filter": { "status": "pending" },
    "update": {
      "$set": { "status": "archived" }
    }
  }
  ```
* **Respuesta (200 OK):**
  ```json
  {
    "matchedCount": 15,
    "modifiedCount": 15
  }
  ```

#### `POST /action/deleteOne` / `POST /action/deleteMany`
Elimina uno o múltiples documentos coincidentes.
* **Cuerpo de la solicitud:**
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

### Endpoints de Almacenamiento GridFS (`/files/*`)

#### `POST /files/upload`
Transmite y almacena un archivo binario en MongoDB GridFS mediante flujo continuo sin sobrecarga de memoria.
* **Formato:** `multipart/form-data`
* **Campos del formulario:**
  * `file` (*binario, requerido*): Archivo a almacenar.
  * `database` (*string, opcional*): Base de datos destino.
  * `bucket` (*string, opcional, por defecto: `"fs"`*): Nombre del bucket GridFS.
* **Respuesta (201 Created):**
  ```json
  {
    "fileId": "60d5ec49f1b2c8b1f8e4e1a5",
    "filename": "documento.pdf",
    "contentType": "application/pdf",
    "length": 154200
  }
  ```

#### `GET /files/{file_id}`
Descarga o transmite el contenido de un archivo almacenado.
* **Mecanismos de autenticación:**
  * Cabecera HTTP: `x-api-key: <token>`
  * Parámetro de consulta: `?key=<token>` (para elementos `<img>` o enlaces directos).
* **Parámetros de consulta (opcionales):**
  * `download=true`: Establece la cabecera `Content-Disposition` en `attachment`.
  * `database`: Nombre de la base de datos si difiere de la predeterminada.
  * `bucket`: Nombre del bucket de almacenamiento.
* **Respuesta:** Flujo binario continuo con cabeceras `Content-Type`, `Content-Length` y `Content-Disposition`.

#### `GET /files/{file_id}/info`
Devuelve los metadatos asociados a un archivo sin transmitir el contenido binario.
* **Respuesta (200 OK):**
  ```json
  {
    "fileId": "60d5ec49f1b2c8b1f8e4e1a5",
    "filename": "documento.pdf",
    "length": 154200,
    "uploadDate": "2026-10-16T22:30:00+00:00",
    "metadata": {
      "contentType": "application/pdf",
      "originalFilename": "documento.pdf"
    }
  }
  ```

#### `DELETE /files/{file_id}`
Elimina el registro de metadatos del archivo y todos sus bloques (`chunks`) correspondientes en GridFS.
* **Respuesta (200 OK):**
  ```json
  {
    "deleted": true,
    "fileId": "60d5ec49f1b2c8b1f8e4e1a5"
  }
  ```

---

## Entorno de Desarrollo

### 1. Clonar el Repositorio
```bash
git clone <URL_DEL_REPOSITORIO>
cd vg-mongo-proxy
```

### 2. Configurar el Entorno Virtual
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Instalar Dependencias
```bash
pip install -e ".[dev]"
```

### 4. Configurar Variables de Entorno
```bash
cp .env.example .env
```
Editar el archivo `.env` con los valores de conexión locales correspondientes.

### 5. Ejecutar la Suite de Pruebas
```bash
pytest
```

### 6. Iniciar el Servidor de Desarrollo
```bash
uvicorn vg_mongo_proxy.main:app --reload --port 8000
```
La documentación interactiva estará disponible en `http://localhost:8000/docs`.
