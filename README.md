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
|      Clúster MongoDB / Atlas       |
|  * Colecciones de documentos       |
|  * Buckets GridFS (fs.files/chunks)|
+------------------------------------+
```

---

### Seguridad y Gestión de Credenciales

La cadena de conexión a la base de datos (`MONGODB_URI`) contiene información crítica de acceso y nunca debe ser expuesta ni almacenada en el código fuente ni en el cliente web.

### 1. Entorno de Producción (Cualquier Servidor o Plataforma Cloud)
* Las credenciales se configuran mediante variables de entorno del sistema o a través del gestor de secretos del servidor / proveedor:
  * `MONGODB_URI`: Cadena de conexión al clúster (`mongodb+srv://...` o `mongodb://...`).
  * `PROXY_API_KEY`: Clave estricta de autorización para acceder al proxy.
  * `DEFAULT_DATABASE`: Nombre de la base de datos predeterminada.
  * `CORS_ORIGINS`: Lista delimitada por comas de orígenes HTTP autorizados (o `*` para permitir todos).
* Estas variables son inyectadas en memoria durante la ejecución del proceso y no se persisten en archivos rastreados.

### 2. Entorno Local (Desarrollo)
* Se definen en un archivo `.env` local en la raíz del proyecto.
* El archivo `.env` está explícitamente excluido en `.gitignore` para evitar su inclusión accidental en el sistema de control de versiones. Se proporciona un archivo `.env.example` como plantilla referencial.

### 3. Aislamiento del Cliente
* Las aplicaciones cliente únicamente interactúan con la interfaz HTTP del proxy utilizando la URL pública del servicio y la cabecera `x-api-key`. Bajo ninguna circunstancia deben tener visibilidad de las credenciales de MongoDB.

---

## Despliegue

La aplicación es completamente agnóstica de la infraestructura y puede ejecutarse en cualquier servidor Linux/macOS/Windows, contenedor Docker, clúster de Kubernetes, máquina virtual (VPS) o plataforma de aplicaciones (PaaS).

### Opción 1: Ejecución Directa con Python y Uvicorn
Para servidores dedicados, VPS (con systemd, Supervisor o Nginx reverse proxy) o plataformas PaaS:

1. Clonar el repositorio e instalar la aplicación:
   ```bash
   pip install .
   ```
2. Establecer las variables de entorno necesarias (`MONGODB_URI`, `PROXY_API_KEY`, etc.).
3. Iniciar el servidor ASGI:
   ```bash
   uvicorn vg_mongo_proxy.main:app --host 0.0.0.0 --port ${PORT:-8000}
   ```

### Opción 2: Despliegue con Docker / Contenedores
El proyecto incluye un `Dockerfile` optimizado:

1. Construir la imagen del contenedor:
   ```bash
   docker build -t vg-mongo-proxy .
   ```
2. Ejecutar el contenedor pasando las variables de entorno:
   ```bash
   docker run -d \
     -p 8000:8000 \
     --env MONGODB_URI="mongodb+srv://..." \
     --env PROXY_API_KEY="clave-secreta" \
     --env DEFAULT_DATABASE="app_db" \
     --name vg-mongo-proxy \
     vg-mongo-proxy
   ```
   O utilizando un archivo `.env`:
   ```bash
   docker run -d -p 8000:8000 --env-file .env --name vg-mongo-proxy vg-mongo-proxy
   ```

### Opción 3: Plataformas Cloud y PaaS
La aplicación se adapta automáticamente a entornos que asignan puertos dinámicos a través de la variable `$PORT`. Para proveedores PaaS que admiten especificaciones declarativas de infraestructura, se incluye un archivo de referencia opcional `render.yaml`.

---

## Integración en Cliente

### 1. Inicialización y Comprobación de Estado (Health Check)

En entornos serverless, contenedores o servicios con arranque en frío (cold start), se recomienda consultar el endpoint `/health` al inicio del ciclo de vida de la aplicación:

```javascript
const PROXY_URL = "https://api.tu-dominio.com";
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
<a href="https://api.tu-dominio.com/files/60d5ec49f1b2c8b1f8e4e1a1?key=clave-configurada-en-el-proxy&download=true">
  Descargar documento
</a>

<!-- Visualización en línea (imágenes) -->
<img src="https://api.tu-dominio.com/files/60d5ec49f1b2c8b1f8e4e1a1?key=clave-configurada-en-el-proxy" alt="Archivo" />
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
