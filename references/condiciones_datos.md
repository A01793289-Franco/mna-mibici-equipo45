# Fuentes, condiciones de uso y privacidad

Consulta: 18 de octubre de 2026.

## Fuentes públicas revisadas

- [Datos abiertos de MiBici](https://www.mibici.net/es/datos-abiertos/): publica descargas CSV por mes/año e invita a explorar y compartir los datos de uso.
- [Términos y condiciones](https://www.mibici.net/es/termino-y-condiciones/): regula suscripciones y operación del servicio; no se identificó allí una licencia específica para redistribuir los CSV.
- [Aviso de privacidad](https://www.mibici.net/es/aviso-de-privacidad/): describe al responsable del tratamiento y los derechos de las personas titulares.

No se encontró una licencia de datos nombrada (por ejemplo, Creative Commons) en las páginas revisadas. Esto se documenta como condición no especificada; no se atribuye a los datos la licencia MIT del código ni se afirma una autorización comercial. Antes de redistribuir los archivos o darles otro uso se deberá confirmar la autorización aplicable con el proveedor. Este reporte describe lo publicado; no es una interpretación jurídica.

## Uso en el proyecto

Los CSV se descargan localmente desde el portal oficial, se conservan fuera de Git y se identifican por SHA-256. La entrega publica código, manifiestos, estadísticas y figuras agregadas. No incluye los CSV, tablas por viaje, inventarios de usuarios, modelos serializados ni la base local de MLflow.

Antes de guardar los datos limpios se excluyen identificadores de usuario, género y año de nacimiento. El ID del viaje se conserva únicamente en el Parquet local para deduplicación. P1/P2 utilizan estación-hora y P3 perfiles por estación. Los ejemplos del notebook muestran tipos y agregados, no viajes individuales.

La página de términos describe un horario de liberación de bicicletas y disponibilidad de devolución diferente. No se utilizó esa descripción actual para borrar retrospectivamente horas de 2026: no se dispone de un historial de cambios operativos. La interpretación de horas cero queda sujeta al supuesto de cobertura documentado en la propuesta.

## Referencias

MiBici. (s. f.-a). *Aviso de privacidad*. https://www.mibici.net/es/aviso-de-privacidad/

MiBici. (s. f.-b). *Datos abiertos* [Conjunto de datos]. https://www.mibici.net/es/datos-abiertos/

MiBici. (s. f.-c). *Términos y condiciones*. https://www.mibici.net/es/termino-y-condiciones/
