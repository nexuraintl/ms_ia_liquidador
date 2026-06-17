# Reglas de negocio por impuesto (resumen)

Este documento resume la lógica tributaria que aplica el sistema. Los valores
normativos (UVT, conceptos, tarifas, rangos) se obtienen de la API de Nexura al
arranque y por solicitud; los ejemplos numéricos a continuación reflejan la
configuración de referencia en `config.py` y los liquidadores en `Liquidador/`.

## Qué impuestos aplican

Los impuestos aplicables a cada factura se determinan por el **código de negocio** y
el **NIT administrativo** (consultados en la base de datos). No todos los negocios
aplican todos los impuestos; la detección es automática
(`detectar_impuestos_aplicables_por_codigo` y las funciones `nit_aplica_*`).

## Retención en la Fuente

- Más de 43 conceptos nacionales, cada uno con su **base mínima en pesos** y su
  **tarifa**. La retención se calcula solo si la base gravable supera la base mínima
  del concepto. Ejemplos: compras generales declarantes 2.5%, servicios generales
  declarantes 4%, honorarios persona jurídica 11%, arrendamiento de bienes muebles 4%.
- **Conceptos no identificados:** si la IA no logra relacionar lo facturado con ningún
  concepto del diccionario, el concepto se marca como no identificado y no se liquida
  retención sobre él. Si **ningún** concepto mapea, el estado es `no_aplica_impuesto`.
- **Pagos al exterior:** conceptos específicos con tarifa normal y tarifa reducida si
  el país tiene convenio de doble tributación (o pertenece a la Comunidad Andina).
- **Artículo 383 (personas naturales):** para honorarios, prestación de servicios,
  comisiones y viáticos se aplica la tabla progresiva por rangos de UVT (0%, 19%, 28%,
  33%, 35%, 37%, 39%), con depuración de la base y límites de deducciones (intereses
  de vivienda, dependientes, medicina prepagada, rentas exentas).

## IVA y ReteIVA

- Análisis especializado de IVA sobre la factura.
- ReteIVA: tarifa del 15% para fuente nacional; tratamiento del 100% para fuente
  extranjera (IVA esperado del 19% para proveedores del exterior).


## ICA (Industria y Comercio)

- Se liquida por municipio y actividad económica, relacionando la actividad facturada
  (de las líneas/descripción) con las actividades registradas en la base de datos.


## Sobretasa Bomberil

- Se deriva del cálculo de ICA (porcentaje adicional sobre el ICA liquidado), según el
  municipio.

## Estampilla Pro Universidad Nacional

- Aplica a contratos (obra, interventoría y servicios conexos) de negocios que
  administran recursos públicos y cuyo código de negocio está habilitado.
- Tarifa por tabla de rangos en UVT (a partir de cierto mínimo en UVT; por debajo no
  aplica). Los rangos y tarifas se obtienen de la base de datos.

## Contribución a Obra Pública (5%)

- Tarifa fija del 5% sobre el valor de la factura sin IVA, para contratos de obra de
  negocios habilitados que administran recursos públicos. En consorcios se aplica
  según el porcentaje de participación de cada miembro.

## Estampillas Generales

- Identificación automática de varios tipos de estampillas territoriales
  (p. ej. Procultura, Adulto Mayor) extraidas directamente de los documentos.

## Impuesto al Timbre

- Se evalúa sobre documentos y contratos que cumplan las condiciones normativas.

## Tasa Prodeporte

- Cálculo con validaciones presupuestales (rubro, centro de costos, generación de
  presupuesto, número y valor del contrato) provistas como parámetros del endpoint.

## Consorcios

- Tratamiento especial de la retención en la fuente: en lugar de una retención única,
  se liquida **por consorciado** y, dentro de cada uno, **por concepto**.
- A cada consorciado se le asigna la base proporcional a su `porcentaje_participacion`,
  y la base mínima normativa de cada concepto se valida contra esa base **individual**.
  Por eso un mismo concepto puede generar retención a un consorciado y no a otro.
- Antes de calcular, se valida la **naturaleza tributaria** de cada consorciado: si es
  autorretenedor o de régimen simple, no se le aplica retención (se indica la razón).
- Si algún concepto facturado no mapea a la base de datos, se liquida con los que sí
  mapean y el no mapeado se registra como observación. La preliquidación solo queda
  **sin finalizar** si ningún concepto mapea o si falta información de un consorciado
  (por ejemplo, el porcentaje de participación).
- La forma exacta del resultado (campos por consorciado y por concepto) está en
  [03_API.md](03_API.md#detalle-de-retención-en-la-fuente).
