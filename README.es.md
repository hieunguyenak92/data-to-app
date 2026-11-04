# Data to App

### Tus archivos se convierten en software. Tus decisiones sobreviven al próximo import.

[English](README.md) · [Tiếng Việt](README.vi.md) · [한국어](README.ko.md) · [日本語](README.ja.md) · [Español](README.es.md) · [Português](README.pt-BR.md) · [简体中文](README.zh-CN.md) · [ไทย](README.th.md) · [Français](README.fr.md)

**Entrega a Claude o Codex tus archivos y un trabajo real. Recibe una aplicación que puedes ejecutar, inspeccionar y hacer tuya.**

Data to App convierte CSV y Excel en software operativo que distingue el origen de sus datos: registros consultables, vistas útiles, ediciones permitidas e importaciones repetibles. El agente da forma al flujo; un motor determinista de Python/SQLite separa los registros de origen, las ediciones locales y las nuevas instantáneas. Recibes la app funcional, su código y sus datos locales.

**[Crea tu primer espacio de trabajo](#ejecuta-el-espacio-de-inventario)** · **[Instalar para Claude o Codex](docs/INSTALL.md)** · **[Explorar el contrato de datos](docs/DATA-CONTRACT.md)** · **[Explora la demostración guiada](https://hieunguyenak92.github.io/data-to-app/)**

![Espacio de inventario sintético generado con Data to App](docs/assets/workspace.jpg)

*Runtime local real con datos sintéticos. La siguiente instantánea se ha conciliado conservando una decisión local.*

> **El próximo import, explícito.** El valor de origen es `12`. Lo cambias a `20`. El nuevo archivo dice `14`. Data to App conserva tu `20` y presenta el conflicto entre origen, local y entrada para que decidas. Los cambios coincidentes convergen; las decisiones distintas siguen visibles.

## Empieza con un trabajo real

Tras [instalar la skill](docs/INSTALL.md), pide al agente:

> Usa Data to App con `./exports`. Crea una herramienta local de inventario con búsqueda, una vista de existencias bajo el umbral y edición de niveles de reposición y notas. Conserva esas ediciones al importar el siguiente archivo y muestra los cambios que requieren una decisión. Inicia la aplicación y verifica las acciones principales.

La skill guía al agente para inspeccionar archivos, elegir identidades y operaciones, construir la aplicación y utilizarla. Tú describes el trabajo; el agente configura el modelo técnico. Una ambigüedad importante en claves, unidades o reglas de negocio puede necesitar una respuesta clara por tu parte.

Buenos puntos de partida son los archivos de inventario y pedidos, contactos que necesitan correcciones continuas y registros de proyectos o servicios recibidos periódicamente. La primera versión se centra en tablas locales con claves independientes y en los flujos solicitados.

## Diseñada para la segunda importación

| Capacidad | Qué aporta |
| --- | --- |
| **Perfilado consciente de la identidad** | Evidencia sobre claves candidatas, valores ausentes, duplicados e identificadores con ceros iniciales. |
| **Comprobación previa de uniones** | Detecta claves sin correspondencia y multiplicación de filas antes de combinar datos. |
| **Conciliación en tres vías** | Separa origen, cambios locales y valores entrantes, con decisiones por campo ante conflictos. |
| **Vista previa de importación** | Revisa altas, actualizaciones, registros ausentes y conflictos antes de aplicar la instantánea. |
| **Interfaz operativa** | Búsqueda, vistas configuradas, edición permitida, resolución de conflictos, historial y exportación CSV. |
| **Código de aplicación portable** | Genera una app Python/SQLite con recursos locales que funciona independientemente de la skill instalada. |

Estas herramientas aportan evidencia para decidir. Una columna única es candidata a clave, pero no demuestra una identidad de negocio estable. Una unión correcta técnicamente tampoco garantiza que sus totales tengan el significado esperado.

## Ejecuta el espacio de inventario

Requiere **Python 3.10+**. La lectura CSV y el entorno generado utilizan la biblioteca estándar. Los datos incluidos son sintéticos.

```bash
git clone https://github.com/hieunguyenak92/data-to-app.git
cd data-to-app
python3 skills/data-to-app/scripts/dta.py demo --out ./inventory-app
python3 inventory-app/app.py --port 8765
```

Abre **http://127.0.0.1:8765**. Busca un producto, abre su editor, cambia un campo permitido y exporta el resultado. El estado se guarda en la base SQLite del espacio y se conserva al reiniciar la aplicación.

Para previsualizar la siguiente instantánea de productos, usa otra terminal en el directorio del repositorio:

```bash
python3 skills/data-to-app/scripts/dta.py import ./inventory-app --table products --file skills/data-to-app/assets/examples/inventory/next/products.csv
```

Añade `--apply` para aplicarla o utiliza la vista previa y confirmación de la app. Edita un campo que también cambie en el nuevo archivo para probar la resolución de conflictos.

Una importación representa una **instantánea completa de una tabla**. Los registros ausentes se marcan y se retienen. Un archivo parcial marcará como ausentes los registros omitidos. Los cambios de esquema y las claves duplicadas con valores distintos se rechazan antes de modificar datos.

## Utiliza tus archivos

CSV es una tabla de texto; XLSX es un libro de Excel. Para XLSX, instala el lector opcional en el entorno Python que ejecuta las herramientas:

```bash
python3 -m pip install openpyxl==3.1.5 defusedxml==0.7.1 et-xmlfile==2.0.0
```

Límites de entrada: **10 MiB por archivo, 50,000 filas por tabla, 200 columnas y 1,000,000 celdas**. XLSX usa la primera hoja de forma predeterminada y avisa si hay otras. No se recalculan las fórmulas.

Empieza con el prompt anterior o inspecciona los archivos directamente:

```bash
python3 skills/data-to-app/scripts/dta.py inspect ./exports
```

El agente puede usar el perfil para configurar el modelo y construir el espacio. Los detalles técnicos están en la [guía de instalación y CLI en inglés](docs/INSTALL.md).

## Exportación, propiedad y límites

La exportación CSV contiene los valores efectivos de los registros activos, incluidas las ediciones locales aceptadas. La protección frente a fórmulas puede anteponer un apóstrofo a celdas exportadas de riesgo; los valores almacenados no cambian. Los registros ausentes se mantienen localmente.

El servidor generado escucha en `127.0.0.1`, utiliza recursos locales y no necesita un servicio alojado para sus operaciones centrales. Durante la creación, siguen aplicándose las políticas de acceso y datos del entorno de IA. Bases, entradas y exportaciones pueden contener información sensible. [Privacidad, en inglés](docs/PRIVACY.md).

Esta versión es un espacio local, sin autenticación multiusuario ni garantía de despliegue en la nube. No ejecuta fórmulas de hojas de cálculo, deduce todas las reglas de negocio, admite migraciones arbitrarias de esquema ni garantiza recuperación universal. Revisa los resultados importantes antes de usarlos en tu operación.

**Empieza con el espacio sintético. Después, encarga al agente un trabajo real.**
